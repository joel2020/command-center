"""Golden-file tests for the render path.

Every other suite tests pure functions. This one tests the wiring — build against
fixtures and assert on the HTML that comes out. Both dashboard bugs found so far
were caught by eyeballing a screenshot, which doesn't scale and doesn't run in CI.

The rule under test throughout: **"nothing to do" and "couldn't look" must never
render the same way.**
"""

import datetime
import json
import os
import re
import sys
import tempfile
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB)

import build_dashboard  # noqa: E402
import feed as feedmod  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 9, 30, tzinfo=datetime.timezone.utc)


def extract_data(html):
    m = re.search(r'<script id="cc-data" type="application/json">(.*?)</script>',
                  html, re.S)
    assert m, "no embedded data block in output"
    return json.loads(m.group(1).replace("<\\/", "</"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "index.html")
        # Point the module's paths at fixtures.
        self._saved = {k: getattr(feedmod, k) for k in
                       ("FEED", "HEARTBEAT", "AUTOMATION_LOG", "NEEDS_ME", "PROJECTS_MD")}
        for k in self._saved:
            setattr(feedmod, k, os.path.join(self.tmp, k.lower() + ".dat"))

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(feedmod, k, v)

    def write(self, attr, content):
        path = getattr(feedmod, attr)
        with open(path, "w") as f:
            f.write(content)

    def build(self):
        data, _ = build_dashboard.build(want_calendar=False, out=self.out, now=NOW)
        with open(self.out) as f:
            return data, f.read()


class TestOutputIntegrity(Base):
    def test_placeholder_is_always_replaced(self):
        _, html = self.build()
        self.assertNotIn("__CC_DATA__", html)

    def test_embedded_json_is_parseable(self):
        _, html = self.build()
        self.assertIsInstance(extract_data(html), dict)

    def test_script_close_tag_in_data_cannot_break_out(self):
        """A project named with a </script> tag must not escape the data block."""
        self.write("PROJECTS_MD",
                   "## Active\n\n### Evil </script><script>alert(1)</script>\n"
                   "- status: x\n- last movement: 2026-07-26\n")
        _, html = self.build()
        # Exactly one closing tag for the data block, and the payload is escaped.
        self.assertIn("<\\/script>", html)
        data = extract_data(html)
        self.assertIn("Evil", data["projects"]["items"][0]["name"])

    def test_html_is_self_contained_no_external_requests(self):
        """The page must fetch nothing. It must still be able to CONTAIN a URL.

        This asserted "no http:// anywhere in the file", which was right when
        the page held only local state. It is wrong now that the AGENTS panel
        embeds what each session last did: an agent whose last action was
        `Bash: open "https://github.com/..."` puts a URL in the data block as
        inert text and turned this red at random.

        A flaky test in a pre-commit gate is worse than no test — it eventually
        blocks a legitimate commit, and people learn to pass --no-verify, which
        disables every other check too. So this now asserts the actual intent:
        nothing in a position the browser would FETCH.
        """
        _, html = self.build()
        markup = re.sub(r'<script id="cc-data".*?</script>', "", html, flags=re.S)

        fetching = [
            (r'src\s*=\s*["\']?(?!data:)[^"\'>\s]*//', "a src= that loads off-origin"),
            (r'<link[^>]+href\s*=\s*["\']?(?!data:)[^"\'>\s]*//', "a stylesheet link"),
            (r'url\(\s*["\']?(?!data:)[^)"\']*//', "a CSS url() off-origin"),
            (r'@import\s+', "a CSS @import"),
            (r'<iframe', "an iframe"),
        ]
        for pattern, why in fetching:
            m = re.search(pattern, markup, re.I)
            self.assertIsNone(m, f"page would fetch something external: {why} "
                                 f"-> {m.group(0) if m else ''}")

    def test_embedded_data_may_contain_urls_without_fetching_them(self):
        """Guards the fix above: a URL as DATA is fine and must stay fine."""
        self.write("PROJECTS_MD",
                   "## Active\n\n### Site\n- status: see https://example.com/x\n"
                   "- last movement: 2026-07-26\n")
        _, html = self.build()
        data = extract_data(html)
        self.assertIn("https://example.com/x", data["projects"]["items"][0]["status"])
        markup = re.sub(r'<script id="cc-data".*?</script>', "", html, flags=re.S)
        self.assertNotIn("example.com", markup,
                         "a URL from data must never reach a fetchable position")


class TestMissingVsEmpty(Base):
    """The central rule. These are the tests that would have caught both real bugs."""

    def test_missing_projects_file_is_unavailable_not_zero(self):
        data, _ = self.build()
        self.assertFalse(data["projects"]["available"])
        self.assertIn("missing", data["projects"]["reason"])

    def test_present_but_empty_projects_is_available(self):
        self.write("PROJECTS_MD", "# Projects\n\n## Active\n\n## Dormant\n\n## Done\n")
        data, _ = self.build()
        self.assertTrue(data["projects"]["available"])
        self.assertEqual(data["projects"]["items"], [])

    def test_missing_feed_is_flagged_not_silently_empty(self):
        data, _ = self.build()
        self.assertFalse(data["feed"]["present"])
        self.assertIn("does not exist", data["feed"]["reason"])

    def test_stale_feed_is_marked_stale(self):
        old = (NOW - datetime.timedelta(hours=6)).isoformat()
        self.write("FEED", json.dumps({"generated_at": old}))
        data, _ = self.build()
        self.assertTrue(data["feed"]["stale"])

    def test_fresh_feed_is_not_stale(self):
        self.write("FEED", json.dumps(
            {"generated_at": (NOW - datetime.timedelta(minutes=5)).isoformat()}))
        data, _ = self.build()
        self.assertFalse(data["feed"]["stale"])

    def test_feed_without_timestamp_is_unknown_age_not_fresh(self):
        self.write("FEED", json.dumps({"gmail": {"available": True}}))
        data, _ = self.build()
        self.assertTrue(data["feed"]["unknown_age"])
        self.assertFalse(data["feed"].get("stale"))

    def test_corrupt_feed_is_reported_not_swallowed(self):
        self.write("FEED", "{not json at all")
        data, _ = self.build()
        self.assertFalse(data["feed"]["present"])
        self.assertIn("unreadable", data["feed"]["reason"])

    def test_calendar_skipped_is_unavailable_with_reason(self):
        data, _ = self.build()
        cal = data["today"]["calendar"]
        self.assertFalse(cal["available"])
        self.assertTrue(cal["reason"])

    def test_template_distinguishes_the_two_empty_messages(self):
        """The bug: TODAY said 'genuinely empty' while also saying 'unavailable'."""
        with open(os.path.join(os.path.dirname(LIB), "..", "dashboard",
                               "template.html")) as f:
            tpl = f.read()
        self.assertIn("cal.available", tpl)
        self.assertIn("not a complete picture", tpl)


class TestNeedsMeCap(Base):
    def test_caps_at_ten_and_reports_overflow(self):
        self.write("NEEDS_ME", "\n".join(f"- item {i}" for i in range(15)))
        data, _ = self.build()
        self.assertEqual(len(data["needs_me"]["items"]), 10)
        self.assertGreaterEqual(data["needs_me"]["overflow"], 5)

    def test_blocked_projects_reach_needs_me(self):
        self.write("PROJECTS_MD",
                   "## Active\n\n### RLTRS\n- status: live\n- blocked by: Steve\n"
                   "- last movement: 2026-07-26\n")
        data, _ = self.build()
        self.assertTrue(any("Steve" in i["text"] for i in data["needs_me"]["items"]))

    def test_high_severity_sorts_first(self):
        self.write("NEEDS_ME", "\n".join(f"- flagged {i}" for i in range(3)))
        self.write("HEARTBEAT", json.dumps(
            {"tasks": {"email-triage": {"last_run": None, "max_age_hours": 2}}}))
        data, _ = self.build()
        self.assertEqual(data["needs_me"]["items"][0]["severity"], "high")


class TestHeartbeatRendering(Base):
    def test_never_run_is_a_miss(self):
        self.write("HEARTBEAT", json.dumps(
            {"tasks": {"morning-brief": {"last_run": None, "max_age_hours": 26}}}))
        data, _ = self.build()
        t = data["in_flight"]["heartbeat"]["tasks"][0]
        self.assertTrue(t["never_run"])
        self.assertTrue(t["missed"])

    def test_recent_run_is_not_a_miss(self):
        self.write("HEARTBEAT", json.dumps({"tasks": {"morning-brief": {
            "last_run": (NOW - datetime.timedelta(hours=1)).isoformat(),
            "max_age_hours": 26}}}))
        data, _ = self.build()
        self.assertFalse(data["in_flight"]["heartbeat"]["tasks"][0]["missed"])

    def test_unparseable_timestamp_counts_as_missed(self):
        self.write("HEARTBEAT", json.dumps(
            {"tasks": {"morning-brief": {"last_run": "yesterday", "max_age_hours": 26}}}))
        data, _ = self.build()
        self.assertTrue(data["in_flight"]["heartbeat"]["tasks"][0]["missed"])

    def test_missing_heartbeat_is_unavailable(self):
        data, _ = self.build()
        self.assertFalse(data["in_flight"]["heartbeat"]["available"])


class TestLinearDueDates(Base):
    def test_overdue_issue_is_flagged_overdue(self):
        self.write("FEED", json.dumps({
            "generated_at": NOW.isoformat(),
            "linear": {"available": True, "issues": [
                {"id": "ALI-32", "title": "Week 2", "dueDate": "2026-07-15",
                 "statusType": "unstarted", "project": "RLTRS"}]}}))
        data, _ = self.build()
        due = data["today"]["due"]
        self.assertEqual(len(due), 1)
        self.assertTrue(due[0]["overdue"])
        self.assertIn("11d", due[0]["due_human"])

    def test_completed_issues_are_not_due(self):
        self.write("FEED", json.dumps({
            "generated_at": NOW.isoformat(),
            "linear": {"available": True, "issues": [
                {"id": "X-1", "title": "done", "dueDate": "2026-07-15",
                 "statusType": "completed"}]}}))
        data, _ = self.build()
        self.assertEqual(data["today"]["due"], [])

    def test_far_future_is_not_shown(self):
        self.write("FEED", json.dumps({
            "generated_at": NOW.isoformat(),
            "linear": {"available": True, "issues": [
                {"id": "X-1", "title": "later", "dueDate": "2026-12-01",
                 "statusType": "unstarted"}]}}))
        data, _ = self.build()
        self.assertEqual(data["today"]["due"], [])

    def test_garbage_due_date_does_not_crash(self):
        self.write("FEED", json.dumps({
            "generated_at": NOW.isoformat(),
            "linear": {"available": True, "issues": [
                {"id": "X-1", "title": "bad", "dueDate": "soon",
                 "statusType": "unstarted"}]}}))
        data, _ = self.build()
        self.assertEqual(data["today"]["due"], [])


class TestMalformedProjects(Base):
    def test_malformed_entry_is_surfaced_not_dropped(self):
        self.write("PROJECTS_MD",
                   "## Active\n\n### Broken\nthis is not a field\n")
        data, _ = self.build()
        items = data["projects"]["items"]
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["malformed"])
        self.assertIn("not a field", items[0]["raw"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

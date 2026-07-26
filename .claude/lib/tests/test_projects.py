import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import projects  # noqa: E402


SAMPLE = """# Projects

<!-- a comment that should vanish
     across multiple lines -->

## Active

### RLTRS
- status: active client build
- next action: get Steve to state the $4,000 basis in writing
- blocked by: Steve
- last movement: 2026-07-25

### Clara
- status: live
- next action: open items in HANDOFF.md
- blocked by: nothing
- last movement: 2026-07-23

## Dormant

### Elite Funding Solutions
- status: production CRM, quiet
- next action:
- blocked by:
- last movement: 2026-06-13

## Done
"""


class TestParse(unittest.TestCase):
    def test_parses_all_projects(self):
        ps = projects.parse(SAMPLE)
        self.assertEqual([p.name for p in ps], ["RLTRS", "Clara", "Elite Funding Solutions"])

    def test_assigns_sections(self):
        ps = {p.name: p.section for p in projects.parse(SAMPLE)}
        self.assertEqual(ps["RLTRS"], "Active")
        self.assertEqual(ps["Elite Funding Solutions"], "Dormant")

    def test_reads_fields(self):
        p = projects.parse(SAMPLE)[0]
        self.assertEqual(p.status, "active client build")
        self.assertEqual(p.blocked_by, "Steve")
        self.assertEqual(p.last_movement, "2026-07-25")

    def test_comments_are_stripped(self):
        self.assertNotIn("vanish", projects.render(projects.parse(SAMPLE)))

    def test_empty_file(self):
        self.assertEqual(projects.parse(""), [])

    def test_missing_file_returns_empty(self):
        self.assertEqual(projects.load("/nonexistent/projects.md"), [])


class TestStaleness(unittest.TestCase):
    today = datetime.date(2026, 7, 25)

    def test_days_stale(self):
        p = projects.parse(SAMPLE)[0]
        self.assertEqual(p.days_stale(self.today), 0)
        self.assertFalse(p.is_stale(self.today))

    def test_stale_at_seven_days(self):
        p = projects.Project("X", "Active", {"last movement": "2026-07-18"})
        self.assertEqual(p.days_stale(self.today), 7)
        self.assertTrue(p.is_stale(self.today))

    def test_six_days_is_not_stale(self):
        p = projects.Project("X", "Active", {"last movement": "2026-07-19"})
        self.assertFalse(p.is_stale(self.today))

    def test_missing_date_is_not_stale(self):
        # Unknown must not masquerade as fresh OR as stale — it's None.
        p = projects.Project("X", "Active", {})
        self.assertIsNone(p.days_stale(self.today))
        self.assertFalse(p.is_stale(self.today))

    def test_garbage_date_is_not_stale(self):
        p = projects.Project("X", "Active", {"last movement": "last tuesday"})
        self.assertIsNone(p.days_stale(self.today))

    def test_impossible_date_does_not_crash(self):
        p = projects.Project("X", "Active", {"last movement": "2026-02-31"})
        self.assertIsNone(p.days_stale(self.today))


class TestBlocked(unittest.TestCase):
    def test_blocked_detected(self):
        self.assertTrue(projects.Project("X", "Active", {"blocked by": "Steve"}).is_blocked())

    def test_nothing_is_not_blocked(self):
        for v in ["nothing", "none", "", "  ", "-", "N/A"]:
            self.assertFalse(
                projects.Project("X", "Active", {"blocked by": v}).is_blocked(), v
            )


class TestRoundTrip(unittest.TestCase):
    def test_parse_render_parse_is_identity(self):
        once = projects.parse(SAMPLE)
        twice = projects.parse(projects.render(once))
        self.assertEqual(
            [p.to_dict() for p in once], [p.to_dict() for p in twice]
        )

    def test_malformed_entry_survives(self):
        text = "## Active\n\n### Weird One\nthis is not a field at all\n"
        ps = projects.parse(text)
        self.assertEqual(len(ps), 1)
        self.assertTrue(ps[0].malformed)
        # The raw text must survive a round trip — never silently dropped.
        again = projects.parse(projects.render(ps))
        self.assertEqual(len(again), 1)
        self.assertIn("not a field at all", again[0].raw)


class TestUpsert(unittest.TestCase):
    def test_creates_new(self):
        ps, created = projects.upsert([], "New Thing", status="just started")
        self.assertTrue(created)
        self.assertEqual(ps[0].status, "just started")

    def test_updates_existing_without_duplicating(self):
        ps = projects.parse(SAMPLE)
        ps, created = projects.upsert(ps, "clara", status="paused")
        self.assertFalse(created)
        self.assertEqual(len([p for p in ps if p.name.lower() == "clara"]), 1)
        self.assertEqual([p for p in ps if p.name == "Clara"][0].status, "paused")

    def test_underscore_keys_map_to_spaces(self):
        ps, _ = projects.upsert([], "X", next_action="do the thing")
        self.assertEqual(ps[0].next_action, "do the thing")


if __name__ == "__main__":
    unittest.main(verbosity=2)

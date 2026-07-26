import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import runs  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 12, 0, tzinfo=datetime.timezone.utc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "run-log.jsonl")

    def add(self, task, code, when=NOW):
        runs.record(task, code, path=self.log, now=when)


class TestRecord(Base):
    def test_records_ok_flag(self):
        rec = runs.record("email-triage", 0, path=self.log, now=NOW)
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["task"], "email-triage")

    def test_nonzero_exit_is_not_ok(self):
        self.assertFalse(runs.record("email-triage", 1, path=self.log, now=NOW)["ok"])

    def test_appends_rather_than_overwrites(self):
        self.add("email-triage", 0)
        self.add("email-triage", 0)
        self.assertEqual(len(runs.read(self.log)), 2)


class TestConsecutiveFailures(Base):
    def test_counts_back_from_latest(self):
        self.add("email-triage", 1)
        self.add("email-triage", 1)
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 2)

    def test_a_success_resets_the_streak(self):
        self.add("email-triage", 1)
        self.add("email-triage", 1)
        self.add("email-triage", 0)
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 0)

    def test_only_counts_the_named_task(self):
        self.add("email-triage", 1)
        self.add("morning-brief", 1)
        self.add("email-triage", 1)
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 2)
        self.assertEqual(runs.consecutive_failures("morning-brief", self.log), 1)

    def test_no_history_is_zero_not_a_failure(self):
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 0)

    def test_success_after_failures_then_failure_is_one(self):
        for code in (1, 1, 0, 1):
            self.add("email-triage", code)
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 1)


class TestHealth(Base):
    def test_escalates_at_two_consecutive(self):
        self.add("email-triage", 1)
        self.add("email-triage", 1)
        h = {x["task"]: x for x in runs.health(self.log)}
        self.assertTrue(h["email-triage"]["needs_escalation"])

    def test_one_failure_does_not_escalate(self):
        self.add("email-triage", 1)
        h = {x["task"]: x for x in runs.health(self.log)}
        self.assertFalse(h["email-triage"]["needs_escalation"])

    def test_reports_every_known_task_even_with_no_runs(self):
        names = {x["task"] for x in runs.health(self.log)}
        self.assertEqual(names, set(runs.TASKS))

    def test_never_run_task_has_null_last(self):
        h = {x["task"]: x for x in runs.health(self.log)}
        self.assertIsNone(h["weekly-review"]["last"])


class TestPrune(Base):
    def test_drops_records_older_than_window(self):
        self.add("email-triage", 0, NOW - datetime.timedelta(days=100))
        self.add("email-triage", 0, NOW)
        removed = runs.prune(self.log, keep_days=90, now=NOW)
        self.assertEqual(removed, 1)
        self.assertEqual(len(runs.read(self.log)), 1)

    def test_keeps_everything_inside_window(self):
        self.add("email-triage", 0, NOW - datetime.timedelta(days=10))
        self.assertEqual(runs.prune(self.log, keep_days=90, now=NOW), 0)

    def test_missing_file_is_a_noop(self):
        self.assertEqual(runs.prune(os.path.join(self.tmp, "nope.jsonl")), 0)


class TestRobustness(Base):
    def test_corrupt_lines_are_skipped_not_fatal(self):
        with open(self.log, "w") as f:
            f.write('{"ts":"' + NOW.isoformat() + '","task":"email-triage","ok":false}\n')
            f.write("{not json\n")
            f.write("\n")
        self.assertEqual(len(runs.read(self.log)), 1)
        self.assertEqual(runs.consecutive_failures("email-triage", self.log), 1)

    def test_record_missing_ts_does_not_break_prune(self):
        with open(self.log, "w") as f:
            f.write(json.dumps({"task": "email-triage", "ok": True}) + "\n")
        runs.prune(self.log, keep_days=90, now=NOW)  # must not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""The feedback loop: does the system know whether it helped?"""

import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import outcomes  # noqa: E402

T0 = datetime.datetime(2026, 7, 1, 9, 0).astimezone()


def at(days=0, hours=0):
    return T0 + datetime.timedelta(days=days, hours=hours)


def item(text, label="act", severity="normal"):
    return {"text": text, "label": label, "severity": severity, "source": "test"}


class TestKeys(unittest.TestCase):

    def test_key_is_stable_across_reordering(self):
        a, b = item("pay the invoice"), item("pay the invoice")
        self.assertEqual(outcomes.item_key(a), outcomes.item_key(b))

    def test_key_distinguishes_label(self):
        self.assertNotEqual(outcomes.item_key(item("x", label="act")),
                            outcomes.item_key(item("x", label="stale")))

    def test_key_ignores_case_and_padding(self):
        self.assertEqual(outcomes.item_key(item("Pay The Invoice")),
                         outcomes.item_key(item("  pay the invoice  ")))


class TestSnapshot(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "outcomes.jsonl")

    def tearDown(self):
        self.d.cleanup()

    def test_first_build_surfaces_everything(self):
        r = outcomes.snapshot([item("a"), item("b")], self.p, at(0))
        self.assertEqual((r["surfaced"], r["cleared"]), (2, 0))

    def test_repeat_build_does_not_resurface(self):
        outcomes.snapshot([item("a"), item("b")], self.p, at(0))
        r = outcomes.snapshot([item("a"), item("b")], self.p, at(0, 1))
        self.assertEqual((r["surfaced"], r["cleared"]), (0, 0),
                         "log must grow with change, not with build count")

    def test_disappearance_is_recorded_as_cleared(self):
        outcomes.snapshot([item("a"), item("b")], self.p, at(0))
        r = outcomes.snapshot([item("a")], self.p, at(1))
        self.assertEqual((r["surfaced"], r["cleared"]), (0, 1))

    def test_an_item_can_come_back(self):
        outcomes.snapshot([item("a")], self.p, at(0))
        outcomes.snapshot([], self.p, at(1))
        r = outcomes.snapshot([item("a")], self.p, at(2))
        self.assertEqual(r["surfaced"], 1, "a recurring problem is a new problem")

    def test_empty_snapshot_clears_all(self):
        outcomes.snapshot([item("a"), item("b")], self.p, at(0))
        r = outcomes.snapshot([], self.p, at(1))
        self.assertEqual(r["cleared"], 2)


class TestMark(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "outcomes.jsonl")

    def tearDown(self):
        self.d.cleanup()

    def test_rejects_an_unknown_outcome(self):
        with self.assertRaises(ValueError):
            outcomes.mark("k", "sort-of-did-it", path=self.p)

    def test_marked_item_leaves_the_open_list(self):
        outcomes.snapshot([item("a")], self.p, at(0))
        k = outcomes.item_key(item("a"))
        outcomes.mark(k, "acted", path=self.p, now=at(0, 1))
        self.assertEqual(outcomes.open_items(self.p), [])

    def test_explicit_acted_counts_toward_the_rate(self):
        outcomes.snapshot([item("a")], self.p, at(0))
        outcomes.mark(outcomes.item_key(item("a")), "acted",
                      path=self.p, now=at(0, 1))
        m = outcomes.needs_me_metrics(days=7, path=self.p, now=at(1))
        self.assertEqual(m["explicit_acted"], 1)
        self.assertEqual(m["clear_rate"], 1.0)


class TestNeedsMeMetrics(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "outcomes.jsonl")

    def tearDown(self):
        self.d.cleanup()

    def test_no_data_yields_none_not_zero(self):
        """A rate of 0.0 means 'you ignored everything'. An empty week doesn't."""
        m = outcomes.needs_me_metrics(days=7, path=self.p, now=at(0))
        self.assertIsNone(m["clear_rate"])
        self.assertFalse(m["over_surfacing"])

    def test_everything_cleared_is_a_perfect_rate(self):
        outcomes.snapshot([item("a"), item("b")], self.p, at(0))
        outcomes.snapshot([], self.p, at(1))
        m = outcomes.needs_me_metrics(days=7, path=self.p, now=at(1, 1))
        self.assertEqual(m["clear_rate"], 1.0)
        self.assertFalse(m["over_surfacing"])

    def test_items_left_open_past_the_threshold_count_as_passed_over(self):
        outcomes.snapshot([item("a"), item("b"), item("c")], self.p, at(0))
        outcomes.snapshot([item("a"), item("b"), item("c")], self.p,
                          at(outcomes.IGNORED_AFTER_DAYS + 1))
        m = outcomes.needs_me_metrics(days=30, path=self.p,
                                      now=at(outcomes.IGNORED_AFTER_DAYS + 1))
        self.assertEqual(m["still_open_past_threshold"], 3)
        self.assertEqual(m["clear_rate"], 0.0)
        self.assertTrue(m["over_surfacing"], "PHASES.md: below 50% is over-surfacing")

    def test_the_fifty_percent_line(self):
        outcomes.snapshot([item(x) for x in "abcd"], self.p, at(0))
        outcomes.snapshot([item("a"), item("b")], self.p,
                          at(outcomes.IGNORED_AFTER_DAYS + 1))
        m = outcomes.needs_me_metrics(days=30, path=self.p,
                                      now=at(outcomes.IGNORED_AFTER_DAYS + 1))
        self.assertEqual(m["clear_rate"], 0.5)
        self.assertFalse(m["over_surfacing"], "exactly 50% is not below 50%")

    def test_window_excludes_older_records(self):
        outcomes.snapshot([item("old")], self.p, at(0))
        m = outcomes.needs_me_metrics(days=7, path=self.p, now=at(40))
        self.assertEqual(m["surfaced"], 0)


class TestArchiveRecovery(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "outcomes.jsonl")

    def tearDown(self):
        self.d.cleanup()

    def test_clean_week(self):
        outcomes.record_archived(["t1", "t2"], "NOISE", self.p, at(0))
        m = outcomes.archive_recovery_metrics(7, self.p, at(1))
        self.assertEqual(m["archived"], 2)
        self.assertEqual(m["recovered"], 0)
        self.assertTrue(m["clean"])

    def test_a_recovered_thread_is_a_miss(self):
        outcomes.record_archived(["t1", "t2"], "NOISE", self.p, at(0))
        outcomes.record_recovered(["t1"], self.p, at(1))
        m = outcomes.archive_recovery_metrics(7, self.p, at(2))
        self.assertEqual(m["recovered"], 1)
        self.assertEqual(m["recovered_from_this_window"], 1)
        self.assertFalse(m["clean"], "above zero is a miss owed a correction")
        self.assertEqual(m["recovered_ids"], ["t1"])


class TestLogRobustness(unittest.TestCase):

    def test_missing_log_reads_as_empty(self):
        self.assertEqual(outcomes.read("/nope/outcomes.jsonl"), [])

    def test_malformed_lines_are_skipped_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.jsonl")
            with open(p, "w") as f:
                f.write('{"ts":"2026-07-01T09:00:00+00:00","kind":"surfaced","key":"a"}\n')
                f.write("this is not json\n")
                f.write("\n")
                f.write('{"ts":"2026-07-01T10:00:00+00:00","kind":"cleared","key":"a"}\n')
            self.assertEqual(len(outcomes.read(p)), 2)

    def test_records_without_a_timestamp_do_not_crash_the_window(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.jsonl")
            with open(p, "w") as f:
                f.write('{"kind":"surfaced","key":"a"}\n')
            m = outcomes.needs_me_metrics(days=7, path=p, now=at(0))
            self.assertEqual(m["surfaced"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

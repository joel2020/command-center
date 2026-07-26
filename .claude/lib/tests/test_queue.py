import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import queue as q  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 12, 0, tzinfo=datetime.timezone.utc)


def ago(days):
    return NOW - datetime.timedelta(days=days)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rej = os.path.join(self.tmp, "rejected.md")
        self.d = {"items": []}


class TestConfidenceThreshold(Base):
    def test_below_forty_percent_never_queues(self):
        out, item = q.propose(self.d, "file", "move thing", 0.39, now=NOW,
                              rejected_path=self.rej)
        self.assertEqual(out, "rejected_low_confidence")
        self.assertEqual(self.d["items"], [])

    def test_exactly_forty_percent_queues(self):
        out, _ = q.propose(self.d, "file", "move thing", 0.40, now=NOW,
                           rejected_path=self.rej)
        self.assertEqual(out, "queued")

    def test_rejected_items_are_written_to_file(self):
        q.propose(self.d, "file", "move thing", 0.2, detail="why", now=NOW,
                  rejected_path=self.rej)
        with open(self.rej) as f:
            body = f.read()
        self.assertIn("20%", body)
        self.assertIn("move thing", body)


class TestCap(Base):
    def test_visible_caps_at_ten_and_reports_overflow(self):
        for i in range(14):
            q.propose(self.d, "task", f"item {i}", 0.9, now=NOW, rejected_path=self.rej)
        items, overflow = q.visible(self.d, now=NOW)
        self.assertEqual(len(items), 10)
        self.assertEqual(overflow, 4)

    def test_highest_confidence_surfaces_first(self):
        q.propose(self.d, "task", "low", 0.5, now=NOW, rejected_path=self.rej)
        q.propose(self.d, "task", "high", 0.95, now=NOW, rejected_path=self.rej)
        items, _ = q.visible(self.d, now=NOW)
        self.assertEqual(items[0]["subject"], "high")


class TestDedupe(Base):
    def test_same_proposal_is_not_queued_twice(self):
        q.propose(self.d, "task", "call Steve", 0.8, now=NOW, rejected_path=self.rej)
        out, _ = q.propose(self.d, "task", "call Steve", 0.8, now=NOW,
                           rejected_path=self.rej)
        self.assertEqual(out, "duplicate")
        self.assertEqual(len(self.d["items"]), 1)

    def test_dedupe_is_case_and_whitespace_insensitive(self):
        q.propose(self.d, "task", "Call  Steve", 0.8, now=NOW, rejected_path=self.rej)
        out, _ = q.propose(self.d, "task", "call steve", 0.8, now=NOW,
                           rejected_path=self.rej)
        self.assertEqual(out, "duplicate")

    def test_declined_item_does_not_reappear_within_thirty_days(self):
        _, item = q.propose(self.d, "task", "call Steve", 0.8, now=ago(20),
                            rejected_path=self.rej)
        q.resolve(self.d, item["id"], q.DECLINED, now=ago(20))
        out, _ = q.propose(self.d, "task", "call Steve", 0.8, now=NOW,
                           rejected_path=self.rej)
        self.assertEqual(out, "duplicate")

    def test_can_reappear_after_thirty_days(self):
        _, item = q.propose(self.d, "task", "call Steve", 0.8, now=ago(40),
                            rejected_path=self.rej)
        q.resolve(self.d, item["id"], q.DECLINED, now=ago(40))
        out, _ = q.propose(self.d, "task", "call Steve", 0.8, now=NOW,
                           rejected_path=self.rej)
        self.assertEqual(out, "queued")


class TestExpiry(Base):
    def test_expires_after_seven_days(self):
        q.propose(self.d, "task", "old thing", 0.8, now=ago(7), rejected_path=self.rej)
        expired = q.expire(self.d, now=NOW)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["resolution"], "expired unreviewed")

    def test_six_days_still_pending(self):
        q.propose(self.d, "task", "recent", 0.8, now=ago(6), rejected_path=self.rej)
        self.assertEqual(q.expire(self.d, now=NOW), [])

    def test_expired_items_leave_the_visible_queue(self):
        q.propose(self.d, "task", "old", 0.8, now=ago(9), rejected_path=self.rej)
        items, overflow = q.visible(self.d, now=NOW)
        self.assertEqual((len(items), overflow), (0, 0))

    def test_approved_items_do_not_expire(self):
        _, item = q.propose(self.d, "task", "x", 0.8, now=ago(30), rejected_path=self.rej)
        q.resolve(self.d, item["id"], q.APPROVED, now=ago(29))
        self.assertEqual(q.expire(self.d, now=NOW), [])


class TestManualActions(Base):
    def test_flags_sending(self):
        _, item = q.propose(self.d, "email", "send follow-up to Jason", 0.9, now=NOW,
                            rejected_path=self.rej)
        self.assertIn("sending to a human", item["manual_action"])

    def test_flags_deleting(self):
        _, item = q.propose(self.d, "cleanup", "delete the old Supabase project", 0.9,
                            now=NOW, rejected_path=self.rej)
        self.assertIn("deleting", item["manual_action"])

    def test_flags_spending(self):
        _, item = q.propose(self.d, "ops", "pay the invoice", 0.9, now=NOW,
                            rejected_path=self.rej)
        self.assertIn("spending money", item["manual_action"])

    def test_flags_credentials(self):
        _, item = q.propose(self.d, "ops", "rotate the API key", 0.9, now=NOW,
                            rejected_path=self.rej)
        self.assertIn("credentials or permissions", item["manual_action"])

    def test_benign_item_is_not_flagged(self):
        _, item = q.propose(self.d, "report", "regenerate the weekly summary", 0.9,
                            now=NOW, rejected_path=self.rej)
        self.assertEqual(item["manual_action"], [])


class TestPromotion(Base):
    def test_five_clean_approvals_becomes_a_candidate(self):
        for i in range(5):
            _, item = q.propose(self.d, "file-move", f"file {i}", 0.9, now=NOW,
                                rejected_path=self.rej)
            q.resolve(self.d, item["id"], q.APPROVED, now=NOW)
        self.assertIn("file-move", q.promotion_candidates(self.d))

    def test_four_is_not_enough(self):
        for i in range(4):
            _, item = q.propose(self.d, "file-move", f"file {i}", 0.9, now=NOW,
                                rejected_path=self.rej)
            q.resolve(self.d, item["id"], q.APPROVED, now=NOW)
        self.assertEqual(q.promotion_candidates(self.d), [])

    def test_edited_approvals_do_not_count(self):
        for i in range(6):
            _, item = q.propose(self.d, "file-move", f"file {i}", 0.9, now=NOW,
                                rejected_path=self.rej)
            q.resolve(self.d, item["id"], q.APPROVED, note="changed the folder", now=NOW)
        self.assertEqual(q.promotion_candidates(self.d), [])

    def test_manual_actions_have_no_promotion_path_ever(self):
        for i in range(20):
            _, item = q.propose(self.d, "send-email", f"send update {i}", 0.99, now=NOW,
                                rejected_path=self.rej)
            item["fingerprint"] = item["id"] = f"unique{i}"  # bypass dedupe
            q.resolve(self.d, f"unique{i}", q.APPROVED, now=NOW)
        self.assertEqual(q.promotion_candidates(self.d), [])


class TestResolve(Base):
    def test_cannot_resolve_to_arbitrary_status(self):
        _, item = q.propose(self.d, "task", "x", 0.9, now=NOW, rejected_path=self.rej)
        with self.assertRaises(ValueError):
            q.resolve(self.d, item["id"], "executed")

    def test_unknown_id_returns_none(self):
        self.assertIsNone(q.resolve(self.d, "nope", q.APPROVED))


class TestMetrics(Base):
    def test_counts_and_rate(self):
        for i, st in enumerate([q.APPROVED, q.APPROVED, q.DECLINED]):
            _, item = q.propose(self.d, "task", f"t{i}", 0.9, now=NOW,
                                rejected_path=self.rej)
            q.resolve(self.d, item["id"], st, now=NOW)
        m = q.metrics(self.d, now=NOW)
        self.assertEqual((m["approved"], m["declined"]), (2, 1))
        self.assertAlmostEqual(m["approval_rate"], 0.667, places=2)

    def test_rate_is_none_when_nothing_decided(self):
        self.assertIsNone(q.metrics(self.d, now=NOW)["approval_rate"])


class TestPersistence(Base):
    def test_round_trips_through_disk(self):
        path = os.path.join(self.tmp, "queue.json")
        q.propose(self.d, "task", "persist me", 0.9, now=NOW, rejected_path=self.rej)
        q.save(self.d, path)
        self.assertEqual(q.load(path)["items"][0]["subject"], "persist me")

    def test_missing_file_loads_empty(self):
        self.assertEqual(q.load(os.path.join(self.tmp, "nope.json")), {"items": []})

    def test_corrupt_file_loads_empty_rather_than_crashing(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w") as f:
            f.write("{not json")
        self.assertEqual(q.load(path), {"items": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)

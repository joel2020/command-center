import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import push  # noqa: E402

NOW = datetime.datetime(2026, 7, 26, 12, 0, tzinfo=datetime.timezone.utc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "push-log.jsonl")
        self.cfg = os.path.join(self.tmp, "push-config.json")

    def write_cfg(self, **kw):
        with open(self.cfg, "w") as f:
            json.dump(kw, f)

    def write_log(self, records):
        with open(self.log, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")


class TestNotifyPredicates(Base):
    def test_deadline_inside_four_hours_fires(self):
        ok, _ = push.should_notify_deadline(3.5)
        self.assertTrue(ok)

    def test_deadline_outside_window_does_not(self):
        ok, why = push.should_notify_deadline(9)
        self.assertFalse(ok)
        self.assertIn("outside", why)

    def test_passed_deadline_fires(self):
        ok, _ = push.should_notify_deadline(-2)
        self.assertTrue(ok)

    def test_no_deadline_never_fires(self):
        self.assertFalse(push.should_notify_deadline(None)[0])
        self.assertFalse(push.should_notify_deadline(1, has_deadline=False)[0])

    def test_one_failure_is_noise_two_is_signal(self):
        self.assertFalse(push.should_notify_task_failure(1)[0])
        self.assertTrue(push.should_notify_task_failure(2)[0])

    def test_zero_and_none_failures_do_not_fire(self):
        self.assertFalse(push.should_notify_task_failure(0)[0])
        self.assertFalse(push.should_notify_task_failure(None)[0])

    def test_expiring_requires_time_sensitivity(self):
        self.assertFalse(push.should_notify_expiring(1, time_sensitive=False)[0])
        self.assertTrue(push.should_notify_expiring(1, time_sensitive=True)[0])

    def test_unknown_expiry_does_not_fire(self):
        self.assertFalse(push.should_notify_expiring(None, True)[0])


class TestSmsJustification(Base):
    def test_no_reason_is_not_justified(self):
        ok, reasons = push.sms_justified()
        self.assertFalse(ok)
        self.assertEqual(reasons, [])

    def test_each_reason_justifies(self):
        self.assertTrue(push.sms_justified(same_day_money_or_legal=True)[0])
        self.assertTrue(push.sms_justified(client_escalating=True)[0])
        self.assertTrue(push.sms_justified(consequences_outlast_today=True)[0])


class TestSmsBudget(Base):
    def test_counts_only_sent_sms_in_window(self):
        self.write_log([
            {"ts": NOW.isoformat(), "channel": "sms", "sent": True},
            {"ts": NOW.isoformat(), "channel": "macos", "sent": True},
            {"ts": NOW.isoformat(), "channel": "sms", "sent": False},
            {"ts": (NOW - datetime.timedelta(days=9)).isoformat(),
             "channel": "sms", "sent": True},
        ])
        b = push.sms_budget(NOW, self.log)
        self.assertEqual(b["sent_this_week"], 1)
        self.assertEqual(b["remaining"], 1)

    def test_cap_reached_carries_the_threshold_warning(self):
        self.write_log([{"ts": NOW.isoformat(), "channel": "sms", "sent": True}] * 2)
        b = push.sms_budget(NOW, self.log)
        self.assertTrue(b["cap_reached"])
        self.assertIn("threshold is wrong", b["note"])

    def test_empty_log_is_full_budget(self):
        self.assertEqual(push.sms_budget(NOW, self.log)["remaining"], 2)


class TestSmsRefusals(Base):
    """Every path must refuse loudly rather than send quietly."""

    def test_refuses_when_unjustified(self):
        self.write_cfg(sms_enabled=True, account_sid="a", auth_token="b",
                       from_number="c", to_number="d")
        r = push.send_sms("hi", push.sms_justified(), NOW, self.cfg, self.log)
        self.assertFalse(r["sent"])
        self.assertIn("isn't", r["reason"])

    def test_refuses_when_disabled(self):
        self.write_cfg(sms_enabled=False)
        r = push.send_sms("hi", push.sms_justified(client_escalating=True),
                          NOW, self.cfg, self.log)
        self.assertFalse(r["sent"])
        self.assertIn("sms_enabled", r["reason"])

    def test_refuses_when_unconfigured(self):
        self.write_cfg(sms_enabled=True)
        r = push.send_sms("hi", push.sms_justified(client_escalating=True),
                          NOW, self.cfg, self.log)
        self.assertFalse(r["sent"])
        self.assertIn("not configured", r["reason"])

    def test_refuses_at_cap(self):
        self.write_cfg(sms_enabled=True, account_sid="a", auth_token="b",
                       from_number="c", to_number="d")
        self.write_log([{"ts": NOW.isoformat(), "channel": "sms", "sent": True}] * 2)
        r = push.send_sms("hi", push.sms_justified(client_escalating=True),
                          NOW, self.cfg, self.log)
        self.assertFalse(r["sent"])
        self.assertIn("threshold is wrong", r["reason"])

    def test_missing_config_file_refuses_without_crashing(self):
        r = push.send_sms("hi", push.sms_justified(client_escalating=True),
                          NOW, os.path.join(self.tmp, "nope.json"), self.log)
        self.assertFalse(r["sent"])

    def test_dry_run_does_not_send(self):
        self.write_cfg(sms_enabled=True, account_sid="a", auth_token="b",
                       from_number="c", to_number="d")
        r = push.send_sms("hi", push.sms_justified(client_escalating=True),
                          NOW, self.cfg, self.log, dry_run=True)
        self.assertFalse(r["sent"])
        self.assertIn("dry run", r["reason"])

    def test_every_attempt_is_logged(self):
        self.write_cfg(sms_enabled=False)
        push.send_sms("hi", push.sms_justified(client_escalating=True),
                      NOW, self.cfg, self.log)
        self.assertEqual(len(push._read_log(self.log)), 1)


class TestNotify(Base):
    def test_dry_run_logs_without_sending(self):
        r = push.notify("t", "m", dry_run=True, log_path=self.log)
        self.assertFalse(r["sent"])
        self.assertEqual(len(push._read_log(self.log)), 1)

    def test_quotes_do_not_break_the_applescript(self):
        r = push.notify('say "hi"', 'it\'s a "test"', dry_run=True, log_path=self.log)
        self.assertIn("sent", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)

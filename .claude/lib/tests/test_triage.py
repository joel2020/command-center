import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import triage  # noqa: E402


def msg(sender, subject="", snippet=""):
    return {"sender": sender, "subject": subject, "snippet": snippet}


# Real senders observed in Joel's inbox on 2026-07-25.
KNOWN = {"steve@example.com", "jason@example.com"}


class TestOverrides(unittest.TestCase):
    def test_bank_is_act_even_from_noreply(self):
        b, why = triage.classify(msg("noreply@chase.com", "Your statement"), [], KNOWN)
        self.assertEqual(b, triage.ACT, why)

    def test_lawyer_is_act(self):
        b, _ = triage.classify(msg("attorney@firm.com", "Re: contract"), [], KNOWN)
        self.assertEqual(b, triage.ACT)

    def test_accountant_is_act(self):
        b, _ = triage.classify(msg("cpa@books.com", "Q3"), [], KNOWN)
        self.assertEqual(b, triage.ACT)

    def test_first_time_human_is_act(self):
        b, why = triage.classify(msg("brandnew@person.com", "hey"), [], KNOWN)
        self.assertEqual(b, triage.ACT)
        self.assertIn("first-time", why)

    def test_known_human_is_not_auto_act(self):
        b, _ = triage.classify(msg("steve@example.com", "hey"), [], KNOWN)
        self.assertEqual(b, triage.UNSURE)


class TestNoise(unittest.TestCase):
    def test_job_alerts_are_noise(self):
        b, _ = triage.classify(
            msg("donotreply@jobalert.indeed.com", "20 new jobs"), [], KNOWN)
        self.assertEqual(b, triage.NOISE)

    def test_linkedin_is_noise(self):
        b, _ = triage.classify(
            msg("notifications-noreply@linkedin.com", "You have 5 new invitations"),
            [], KNOWN)
        self.assertEqual(b, triage.NOISE)

    def test_newsletter_is_noise(self):
        b, _ = triage.classify(
            msg("newyorker@newsletter.newyorker.com", "Plus: the press corps"),
            [], KNOWN)
        self.assertEqual(b, triage.NOISE)

    def test_generated_address_is_bulk(self):
        self.assertTrue(triage.looks_like_bulk(
            "sunriseseniorliving+email+gdtkr-597be8868d@talent.icims.com"))


class TestActionableBulk(unittest.TestCase):
    """Bulk senders still carry real emergencies. This is the case that matters."""

    def test_gmail_quota_cutoff_is_act(self):
        b, why = triage.classify(msg(
            "googleone-out-of-quota-noreply@one.google.com",
            "You can no longer send and receive emails on Gmail",
            "Take action to restore service"), [], KNOWN)
        self.assertEqual(b, triage.ACT, why)

    def test_expiring_token_is_act(self):
        b, _ = triage.classify(msg(
            "noreply@github.com",
            "Your fine-grained personal access token is about to expire"), [], KNOWN)
        self.assertEqual(b, triage.ACT)

    def test_signature_request_is_act(self):
        b, _ = triage.classify(msg(
            "mail@signnow.com", "Reminder that roman@ Needs Your Signature"),
            [], KNOWN)
        self.assertEqual(b, triage.ACT)

    def test_security_alert_is_fyi_not_act(self):
        b, _ = triage.classify(msg(
            "no-reply@accounts.google.com", "Security alert",
            "A new sign-in on Mac"), [], KNOWN)
        self.assertEqual(b, triage.FYI)


class TestCorrections(unittest.TestCase):
    def test_correction_beats_heuristic(self):
        rules = triage.parse_rules(
            "- 2026-07-26 | domain:github.com | NOISE | I read these on GitHub")
        b, why = triage.classify(msg(
            "noreply@github.com", "token is about to expire"), rules, KNOWN)
        self.assertEqual(b, triage.NOISE)
        self.assertIn("correction", why)

    def test_correction_beats_always_act(self):
        # Joel's explicit word outranks even the bank override.
        rules = triage.parse_rules("- 2026-07-26 | sender:noreply@chase.com | NOISE | ads")
        b, _ = triage.classify(msg("noreply@chase.com", "bank offer"), rules, KNOWN)
        self.assertEqual(b, triage.NOISE)

    def test_parses_all_matcher_kinds(self):
        text = """
- 2026-07-26 | sender:a@b.com | ACT | x
- 2026-07-26 | domain:c.com | FYI | y
- 2026-07-26 | subject:invoice | ACT | z
- 2026-07-26 | contains:rltrs | ACT | w
"""
        self.assertEqual(len(triage.parse_rules(text)), 4)

    def test_malformed_correction_is_skipped_not_guessed(self):
        text = "- this is prose someone wrote in the corrections section\n"
        self.assertEqual(triage.parse_rules(text), [])

    def test_bad_bucket_is_skipped(self):
        self.assertEqual(triage.parse_rules("- 2026-07-26 | sender:a@b.com | MAYBE | x"), [])

    def test_prose_in_real_rules_file_does_not_crash(self):
        rules = triage.load_rules()
        self.assertIsInstance(rules, list)


class TestFormatCorrection(unittest.TestCase):
    def test_round_trips(self):
        line = triage.format_correction("domain", "skool.com", "NOISE", "community", "2026-07-26")
        parsed = triage.parse_rules(line)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].bucket, "NOISE")
        self.assertEqual(parsed[0].value, "skool.com")

    def test_rejects_unknown_bucket(self):
        with self.assertRaises(ValueError):
            triage.format_correction("domain", "x.com", "NOPE", "", "2026-07-26")

    def test_rejects_unknown_matcher(self):
        with self.assertRaises(ValueError):
            triage.format_correction("vibes", "x", "NOISE", "", "2026-07-26")


class TestBatch(unittest.TestCase):
    def test_summarize_counts_every_bucket(self):
        res = triage.triage([
            msg("donotreply@jobalert.indeed.com", "jobs"),
            msg("steve@example.com", "hey"),
        ], rules=[], known_senders=KNOWN)
        counts = triage.summarize(res)
        self.assertEqual(set(counts), set(triage.BUCKETS))
        self.assertEqual(counts["NOISE"], 1)
        self.assertEqual(counts["UNSURE"], 1)

    def test_every_message_gets_a_valid_bucket(self):
        res = triage.triage([
            msg("a@b.com"), msg(""), msg("weird"), msg("x@y.com", "invoice"),
        ], rules=[], known_senders=set())
        for r in res:
            self.assertIn(r["bucket"], triage.BUCKETS)
            self.assertTrue(r["reason"])

    def test_empty_sender_does_not_crash(self):
        b, _ = triage.classify(msg(""), [], set())
        self.assertIn(b, triage.BUCKETS)


class TestNoDestructiveSurface(unittest.TestCase):
    """The hard limits are structural: this module cannot send or delete."""

    def test_module_exposes_no_mutating_functions(self):
        forbidden = ("send", "reply", "delete", "unsubscribe", "archive", "trash")
        for name in dir(triage):
            if name.startswith("_"):
                continue
            if not callable(getattr(triage, name)):
                continue  # constants like KNOWN_SENDERS are data, not actions
            words = name.lower().split("_")
            self.assertFalse(
                any(w in forbidden for w in words),
                f"triage.py must not expose a {name}() function",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

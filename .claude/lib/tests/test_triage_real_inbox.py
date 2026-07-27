"""Measure the classifier against a real inbox instead of invented examples.

The unit tests in test_triage.py check each rule in isolation and all passed
while the classifier was, on real mail, filing newsletters as ACT and burying
an account-takeover warning under "confirmation". Isolated rules can all be
right and the composition still wrong. This file is the composition test.

The numbers asserted here are floors, not targets. Raise them when the
classifier earns it; never lower them to make a change pass.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import triage  # noqa: E402
from fixtures import inbox_2026_07_26 as fx  # noqa: E402

# Everyone Joel has actually corresponded with, as at 2026-07-26. Seeded from
# `in:sent` so that "first-time human sender" means what it says.
KNOWN = {
    "katarina@murraylegalfirm.com", "eddie@murraylegalfirm.com",
    "support@meetava.com", "reyna@acquisitionreps.com",
    "josephdakuras@aol.com", "developer@githubsupport.com",
    "nysleepgroup@aol.com", "ravsingh@eteaminc.com",
    "tadebnath@eteaminc.com", "rnegi@eteaminc.com",
    "fusionhr@fusionbds.com", "stevie.andrade@angi.com",
    "haley.pearl@neighborsbank.com", "tracy.bland@neighborsbank.com",
    "access-support@x.com", "careers@freedomdebtresolutions.com",
    "roosverth.arias@migracioncolombia.gov.co", "ebrandonmurray@gmail.com",
    "servicioalcliente@bodytechcorp.com", "assistant@perplexity.com",
    "joelcarias@icloud.com", "joelcarias23@gmail.com",
}


def run():
    msgs = fx.messages()
    got = [triage.classify(m, rules=[], known_senders=KNOWN) for m in msgs]
    return msgs, [b for b, _ in got], [r for _, r in got], fx.expected()


class TestRealInboxPrecision(unittest.TestCase):
    """ACT is the expensive bucket. It has a hard cap of 10 slots on the
    dashboard, so a false ACT evicts real work."""

    def test_no_newsletter_is_act(self):
        msgs, buckets, reasons, exp = run()
        wrong = [(m["sender"], m["subject"][:44], r)
                 for m, b, r, e in zip(msgs, buckets, reasons, exp)
                 if b == "ACT" and e == "NOISE"]
        self.assertEqual(wrong, [], f"{len(wrong)} newsletters classified ACT")

    def test_act_precision_is_total(self):
        _, buckets, _, exp = run()
        act = [(b, e) for b, e in zip(buckets, exp) if b == "ACT"]
        if not act:
            self.fail("classifier produced no ACT at all")
        good = sum(1 for _, e in act if e == "ACT")
        self.assertEqual(good, len(act),
                         f"ACT precision {good}/{len(act)} — a false ACT evicts real work")

    def test_all_three_real_act_items_are_found(self):
        msgs, buckets, _, exp = run()
        missed = [m["subject"][:60]
                  for m, b, e in zip(msgs, buckets, exp) if e == "ACT" and b != "ACT"]
        self.assertEqual(missed, [], f"missed genuinely actionable mail: {missed}")

    def test_account_takeover_warning_is_not_downgraded(self):
        """'confirmation' used to win over 'if this was not you'."""
        msg = next(m for m in fx.messages() if "voicemail" in m["subject"].lower())
        bucket, reason = triage.classify(msg, rules=[], known_senders=KNOWN)
        self.assertEqual(bucket, "ACT", reason)
        self.assertEqual(triage.severity(msg), "security", "should escalate as security")

    def test_appointment_with_a_date_is_actionable(self):
        msg = next(m for m in fx.messages() if "Appointment" in m["subject"])
        bucket, reason = triage.classify(msg, rules=[], known_senders=KNOWN)
        self.assertEqual(bucket, "ACT", reason)

    def test_storage_quota_warning_is_actionable(self):
        msg = next(m for m in fx.messages() if "storage" in m["subject"].lower())
        bucket, reason = triage.classify(msg, rules=[], known_senders=KNOWN)
        self.assertEqual(bucket, "ACT", reason)


class TestRealInboxBulkDetection(unittest.TestCase):

    def test_brand_at_own_domain_is_bulk(self):
        for s in ("adidas@us-news.comms.adidas.com", "ebay@ebay.com",
                  "Coursera@m.learn.coursera.org", "suracomunicaciones@sura.com.co"):
            self.assertTrue(triage.looks_like_bulk(s), s)

    def test_mail_subdomains_are_bulk(self):
        for s in ("inspiration@mp1.tripadvisor.com", "x@e.upgrade.com",
                  "x@savings.lendingtree.com", "x@m.learn.coursera.org"):
            self.assertTrue(triage.looks_like_bulk(s), s)

    def test_real_people_are_not_bulk(self):
        """The bulk rules must not swallow humans. This is the regression that
        matters most — a misfiled human is a missed client."""
        for s in ("katarina@murraylegalfirm.com", "tracy.bland@neighborsbank.com",
                  "stevie.andrade@angi.com", "pd@patrickdang.com",
                  "josephdakuras@aol.com", "joel@aliviosearchpartners.com",
                  "jason@rltrs.co", "sura.rodriguez@sura.com.co"):
            self.assertFalse(triage.looks_like_bulk(s), s)


class TestAlwaysActSurvives(unittest.TestCase):
    """email-rules.md: accountant, lawyer, bank are ACT regardless. Tightening
    bulk detection must not break that."""

    def test_lawyer_and_bank_still_act(self):
        for s in ("katarina@murraylegalfirm.com", "tracy.bland@neighborsbank.com"):
            b, r = triage.classify({"sender": s, "subject": "following up",
                                    "snippet": ""}, rules=[], known_senders=KNOWN)
            self.assertEqual(b, "ACT", f"{s}: {r}")


class TestFullInboxScore(unittest.TestCase):

    def test_overall_agreement(self):
        """Exact-match agreement across all 42. Floor, not a target."""
        _, buckets, _, exp = run()
        agree = sum(1 for b, e in zip(buckets, exp) if b == e)
        self.assertGreaterEqual(
            agree, 42, f"agreement {agree}/{len(exp)} — regression")


if __name__ == "__main__":
    unittest.main(verbosity=2)

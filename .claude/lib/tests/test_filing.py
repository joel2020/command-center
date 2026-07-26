import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import filing  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.docs = os.path.join(self.tmp, "Documents")
        os.makedirs(self.docs)

    def touch(self, rel, content="x"):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        return p


class TestForbidden(Base):
    def test_photos_library_is_forbidden(self):
        p = "/Users/joel/Pictures/Photos Library.photoslibrary/database/Photos.sqlite"
        self.assertTrue(filing.is_forbidden(p))

    def test_library_is_forbidden(self):
        self.assertTrue(filing.is_forbidden("/Users/joel/Library/Mobile Documents/x.pdf"))

    def test_node_modules_is_forbidden(self):
        self.assertTrue(filing.is_forbidden("/Users/joel/x/node_modules/pkg/index.js"))

    def test_git_internals_forbidden(self):
        self.assertTrue(filing.is_forbidden("/Users/joel/repo/.git/config"))

    def test_quarantine_is_forbidden(self):
        self.assertTrue(filing.is_forbidden("/Users/joel/_QUARANTINE_2026-07-26/x.pdf"))

    def test_ordinary_file_is_not_forbidden(self):
        self.assertFalse(filing.is_forbidden("/Users/joel/Downloads/invoice.pdf"))

    def test_symlink_is_forbidden(self):
        target = self.touch("Downloads/real.pdf")
        link = os.path.join(self.tmp, "Downloads", "link.pdf")
        os.symlink(target, link)
        self.assertTrue(filing.is_forbidden(link))


class TestProjectRoots(Base):
    def test_file_inside_git_repo_is_refused(self):
        self.touch("proj/.git/HEAD")
        f = self.touch("proj/src/main.py")
        pl = filing.plan_one(f, self.docs)
        self.assertEqual(pl["action"], "refuse")
        self.assertIn("project root", pl["reason"])

    def test_file_inside_package_json_dir_is_refused(self):
        self.touch("proj/package.json")
        f = self.touch("proj/index.js")
        self.assertEqual(filing.plan_one(f, self.docs)["action"], "refuse")

    def test_plain_folder_is_not_a_project(self):
        f = self.touch("Downloads/rltrs-invoice.pdf")
        self.assertNotEqual(filing.plan_one(f, self.docs)["action"], "refuse")


class TestClassify(Base):
    def test_client_names_route_correctly(self):
        cases = [
            ("260716-RLTRSRevisedPaymentSchedule.pdf", "Clients/RLTRS"),
            ("bravo-audit.pdf", "Clients/Bravo Mechanical"),
            ("Alivio_Recruitment_Agreement.pdf", "Ventures/Alivio"),
            ("clara-curriculum.md", "Ventures/Clara"),
        ]
        for name, want in cases:
            self.assertEqual(filing.classify(name), want, name)

    def test_media_by_extension(self):
        self.assertEqual(filing.classify("track.mp3"), "Media/Music")
        self.assertEqual(filing.classify("clip.mov"), "Media/Video")
        self.assertEqual(filing.classify("photo.HEIC"), "Media/Photos")

    def test_identity_documents(self):
        self.assertEqual(filing.classify("daniel vargas utility bill.pdf"),
                         "Personal/Identity")

    def test_unknown_returns_none(self):
        self.assertIsNone(filing.classify("asdfqwer.xyz"))


class TestNaming(Base):
    def test_six_digit_date_prefix_expands(self):
        name, src = filing.target_name("260716-RLTRSRevisedPaymentSchedule.pdf")
        self.assertTrue(name.startswith("2026-07-16_"), name)
        self.assertEqual(src, "filename")

    def test_iso_date_in_name_is_used(self):
        name, src = filing.target_name("Screen Recording 2022-05-18 at 11.42.06 AM.mov")
        self.assertTrue(name.startswith("2022-05-18_"), name)
        self.assertEqual(src, "filename")

    def test_falls_back_to_mtime(self):
        name, src = filing.target_name(
            "notes.pdf", mtime=datetime.datetime(2026, 3, 4).timestamp())
        self.assertTrue(name.startswith("2026-03-04_"), name)
        self.assertEqual(src, "mtime")

    def test_no_date_available_is_not_invented(self):
        name, src = filing.target_name("notes.pdf", mtime=None)
        self.assertIsNone(src)
        self.assertEqual(name, "notes.pdf")

    def test_slug_is_lowercase_and_hyphenated(self):
        name, _ = filing.target_name("Some File (1) FINAL!!.PDF",
                                     mtime=datetime.datetime(2026, 1, 2).timestamp())
        self.assertEqual(name, "2026-01-02_some-file-1-final.pdf")

    def test_impossible_date_in_name_falls_through(self):
        name, src = filing.target_name(
            "2026-13-45-report.pdf", mtime=datetime.datetime(2026, 1, 2).timestamp())
        self.assertEqual(src, "mtime")


class TestPlan(Base):
    def test_unclassifiable_goes_to_queue_not_move(self):
        f = self.touch("Downloads/asdfqwer.xyz")
        pl = filing.plan_one(f, self.docs)
        self.assertEqual(pl["action"], "queue")
        self.assertIn("To Review", pl["dest"])

    def test_classified_file_is_a_move(self):
        f = self.touch("Downloads/rltrs-payment.pdf")
        pl = filing.plan_one(f, self.docs)
        self.assertEqual(pl["action"], "move")
        self.assertIn("Clients/RLTRS", pl["dest"])

    def test_existing_destination_queues_instead_of_overwriting(self):
        f = self.touch("Downloads/rltrs-payment.pdf")
        pl = filing.plan_one(f, self.docs)
        os.makedirs(os.path.dirname(pl["dest"]), exist_ok=True)
        with open(pl["dest"], "w") as fh:
            fh.write("existing")
        pl2 = filing.plan_one(f, self.docs)
        self.assertEqual(pl2["action"], "queue")
        self.assertIn("already exists", pl2["reason"])

    def test_missing_file_is_refused(self):
        pl = filing.plan_one(os.path.join(self.tmp, "nope.pdf"), self.docs)
        self.assertEqual(pl["action"], "refuse")


class TestApply(Base):
    def test_dry_run_moves_nothing(self):
        f = self.touch("Downloads/rltrs-payment.pdf")
        res = filing.apply(filing.plan([f], self.docs), dry_run=True, docs=self.docs)
        self.assertTrue(os.path.exists(f))
        self.assertFalse(res[0]["executed"])

    def test_apply_moves_and_records_undo(self):
        f = self.touch("Downloads/rltrs-payment.pdf")
        plans = filing.plan([f], self.docs)
        res = filing.apply(plans, dry_run=False, docs=self.docs)
        self.assertTrue(res[0]["executed"])
        self.assertFalse(os.path.exists(f))
        self.assertTrue(os.path.exists(plans[0]["dest"]))
        self.assertIn("mv ", res[0]["undo"])

    def test_apply_refuses_non_move_actions(self):
        f = self.touch("Downloads/asdfqwer.xyz")
        res = filing.apply(filing.plan([f], self.docs), dry_run=False, docs=self.docs)
        self.assertFalse(res[0]["executed"])
        self.assertTrue(os.path.exists(f))

    def test_apply_cannot_be_tricked_by_a_forged_plan(self):
        """The executor re-checks. A hand-made plan must not bypass the guards."""
        f = self.touch("Downloads/secret.pdf")
        forged = [{"path": f, "action": "move",
                   "dest": os.path.join(self.tmp, "Library", "stolen.pdf")}]
        res = filing.apply(forged, dry_run=False, docs=self.docs)
        self.assertFalse(res[0]["executed"])
        self.assertEqual(res[0]["skipped"], "failed re-check")
        self.assertTrue(os.path.exists(f))

    def test_apply_refuses_forged_move_out_of_taxonomy(self):
        f = self.touch("Downloads/x.pdf")
        forged = [{"path": f, "action": "move", "dest": os.path.join(self.tmp, "elsewhere.pdf")}]
        res = filing.apply(forged, dry_run=False, docs=self.docs)
        self.assertFalse(res[0]["executed"])


class TestQuarantine(Base):
    def test_preserves_original_path_under_quarantine_root(self):
        q = filing.quarantine_path("/Users/joel/Desktop/personal/x.mov",
                                   when=datetime.date(2026, 7, 26), home="/Users/joel")
        self.assertIn("_QUARANTINE_2026-07-26", q)
        self.assertTrue(q.endswith("Desktop/personal/x.mov"))


class TestNoDeleteSurface(Base):
    def test_module_exposes_no_delete_function(self):
        for name in dir(filing):
            if name.startswith("_") or not callable(getattr(filing, name)):
                continue
            words = name.lower().split("_")
            self.assertFalse(
                any(w in ("delete", "remove", "rm", "unlink", "rmtree") for w in words),
                f"filing.py must not expose {name}()",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

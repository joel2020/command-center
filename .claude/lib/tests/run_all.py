#!/usr/bin/env python3
"""Run every Command Center test suite.

    python3 .claude/lib/tests/run_all.py

Exits non-zero if anything fails, so it works as a pre-commit check.
"""

import glob
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # .claude/lib
sys.path.insert(0, HERE)

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    name = os.path.splitext(os.path.basename(path))[0]
    suite.addTests(loader.loadTestsFromName(name))

result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)

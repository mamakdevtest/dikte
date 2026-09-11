"""The fast half of the suite: everything the settings window does not.

`python -m unittest discover` is the contract command and runs everything, but
`tests.test_ui` is 68 of its 82 seconds: 131 tests that each build the whole
settings window and tear it down, twice over for the two platforms. Iteration
does not need them, so this runs the rest in about fifteen seconds and says
what it left out. Run the full command before calling the work done.

    python tools/quick_tests.py            # everything but the windows
    python tools/quick_tests.py --all      # the contract command's set
    python tools/quick_tests.py tests.test_worker tests.test_vad
                                           # the modules you touched
"""

import glob
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFERRED = ("tests.test_ui",)


def modules():
    return ["tests." + os.path.basename(path)[:-3]
            for path in sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))]


def suite_for(loader, names):
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


def main(argv):
    sys.path.insert(0, ROOT)
    names = [arg for arg in argv if not arg.startswith("-")]
    everything = "--all" in argv
    if names:
        targets, deferred = names, []
    elif everything:
        targets, deferred = modules(), []
    else:
        targets = [name for name in modules() if name not in DEFERRED]
        deferred = list(DEFERRED)
    loader = unittest.TestLoader()
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(suite_for(loader, targets))
    elapsed = time.perf_counter() - started
    ran = result.testsRun
    print(f"\n{ran} tests in {elapsed:.1f}s")
    if deferred:
        print("Left out: " + ", ".join(deferred) + " (the settings-window round trips).")
        print("Full suite before calling it done: python -m unittest discover")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

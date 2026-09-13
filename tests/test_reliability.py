"""Reliability properties that only hold while somebody checks them.

Phase 4's rule is that a failure is either reported or explicitly explained, never
silently swallowed. These are the properties behind that rule which are about the
*process* rather than a single `except`: measured, PyQt6 aborts the whole app when an
exception escapes a slot, and a systray app that dies has no trace and no dialogue to
show the user. The hook that prevents it is one line, which is exactly why it needs a
test — nothing about it looks load-bearing.
"""

import os
import pathlib
import subprocess
import sys
import textwrap
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent

SLOT_CRASH = textwrap.dedent(
    """
    import sys

    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication

    if "--hook" in sys.argv:
        import dikte
        dikte.install_crash_reporting()

    app = QApplication([])


    class Slot(QObject):
        fired = pyqtSignal()


    slot = Slot()
    slot.fired.connect(lambda: 1 / 0)
    slot.fired.emit()
    print("STILL RUNNING")
    """
)


class ASlotThatRaises(unittest.TestCase):
    """What happens to the process when a slot handler throws."""

    def run_crash(self, hook):
        argv = [sys.executable, "-c", SLOT_CRASH]
        if hook:
            argv.append("--hook")
        return subprocess.run(
            argv, cwd=str(REPO),
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True, text=True, timeout=120)

    def test_without_the_hook_pyqt_takes_the_process_down(self):
        """The half that makes the hook matter.

        Asserted deliberately: if a future PyQt stops aborting on a slot exception,
        this fails, and that is information — the comment in `dikte.report_crash`
        would then be describing a hazard that no longer exists.
        """
        result = self.run_crash(hook=False)
        self.assertNotEqual(0, result.returncode,
                            "PyQt6 no longer aborts on a slot exception; "
                            "re-check what dikte.report_crash is for")
        self.assertNotIn("STILL RUNNING", result.stdout)

    def test_the_hook_keeps_the_app_alive_and_shows_the_cause(self):
        result = self.run_crash(hook=True)
        self.assertEqual(0, result.returncode,
                         f"the app died anyway:\n{result.stderr[-600:]}")
        self.assertIn("STILL RUNNING", result.stdout)
        self.assertIn("ZeroDivisionError", result.stderr,
                      "the user must never get 'the app closed' and nothing else")


if __name__ == "__main__":
    unittest.main()

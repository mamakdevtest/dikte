"""Reliability properties that only hold while somebody checks them.

Phase 4's rule is that a failure is either reported or explicitly explained, never
silently swallowed. These are the properties behind that rule which are about the
*process* rather than a single `except`: measured, PyQt6 aborts the whole app when an
exception escapes a slot, and a systray app that dies has no trace and no dialogue to
show the user. The hook that prevents it is one line, which is exactly why it needs a
test — nothing about it looks load-bearing.
"""

import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
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


class AMessageWithNowhereToGo(unittest.TestCase):
    """N9: a bundle started from a desktop entry has no terminal to print to.

    Found by packaging, and not only about bundles — `install.sh` writes a desktop entry
    that runs a source checkout with the same problem. What the file must be is *in
    addition to* the stream, never instead of it: a person who did start the app from a
    terminal has to keep seeing exactly what they saw before.
    """

    def setUp(self):
        import dikte

        self.dikte = dikte
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dikte-log-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._stdout, self._stderr = sys.stdout, sys.stderr
        # The application's own "writing to <path>" line belongs to the test's output
        # otherwise, and stderr is restored by the cleanup before unittest reports, so a
        # real failure still shows up.
        sys.stdout, sys.stderr = self.out, self.err = io.StringIO(), io.StringIO()
        self.addCleanup(self._restore)

    def _restore(self):
        # The tee holds an open file for the life of the process by design; a test that
        # leaves one open is a test that looks like a leak.
        for stream in (sys.stdout, sys.stderr):
            handle = getattr(stream, "_handle", None)
            if handle is not None and not handle.closed:
                handle.close()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def test_a_terminal_is_left_alone(self):
        class ATty(io.StringIO):
            def isatty(self):
                return True

        sys.stdout = ATty()
        self.assertIsNone(self.dikte.keep_a_log(self.tmp / "dikte.log"))
        self.assertFalse((self.tmp / "dikte.log").exists(),
                         "a terminal that is right there is not a reason to write a file")

    def test_without_a_terminal_it_writes_to_both_places(self):
        captured = io.StringIO()
        sys.stdout = captured
        target = self.tmp / "dikte.log"
        self.assertEqual(target, self.dikte.keep_a_log(target))
        print("something went wrong")
        self.assertIn("something went wrong", captured.getvalue(),
                      "the stream must keep working: this is a tee, not a redirect")
        self.assertIn("something went wrong", target.read_text(encoding="utf-8"))

    def test_it_says_where_it_is_writing(self):
        """A log nobody can find is the same failure as no log."""
        target = self.tmp / "dikte.log"
        self.dikte.keep_a_log(target)
        self.assertIn(str(target), target.read_text(encoding="utf-8"))

    def test_a_log_that_has_grown_is_started_again(self):
        target = self.tmp / "dikte.log"
        target.write_text("old" * (self.dikte.LOG_LIMIT // 3 + 10), encoding="utf-8")
        self.dikte.keep_a_log(target)
        print("after the restart")
        body = target.read_text(encoding="utf-8")
        self.assertNotIn("oldold", body, "an unbounded log is its own failure")
        self.assertIn("after the restart", body)

    def test_a_path_it_cannot_open_does_not_break_the_app(self):
        blocker = self.tmp / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        self.assertIsNone(self.dikte.keep_a_log(blocker / "dikte.log"))
        self.assertIn("could not open a log file", self.err.getvalue())


class ALogWhenNobodyIsWatching(unittest.TestCase):
    """The same thing where it matters: a process with no terminal at all."""

    def test_a_process_without_a_tty_writes_the_log(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="dikte-log-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        target = tmp / "dikte.log"
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(REPO)!r})
            import dikte
            path = dikte.keep_a_log({str(target)!r})
            print("dikte: the provider refused the request")
            print("PATH", path is not None, file=sys.stderr)
        """)
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=str(REPO), capture_output=True, text=True,
            timeout=120, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        self.assertEqual(0, result.returncode, msg=result.stderr[-600:])
        self.assertIn("PATH True", result.stderr)
        self.assertIn("the provider refused the request", result.stdout,
                      "the pipe still gets it")
        self.assertIn("the provider refused the request", target.read_text(encoding="utf-8"),
                      "and so does the file, which is the half N9 was missing")


if __name__ == "__main__":
    unittest.main()

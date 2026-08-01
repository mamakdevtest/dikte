"""The clipboard and the key press, which is where a dictation actually lands.

Everything here shells out, so the tools are faked. What the tests hold onto is
the command line: a paste that presses the wrong codes, or in the wrong order,
types nothing and looks like a hang.
"""

import subprocess
import unittest
from unittest import mock

import paste
from tests.support import DikteTest, FakeCompleted, linux_only, only_these_tools


@linux_only
class ReadClipboard(DikteTest):
    def test_no_wl_paste_installed(self):
        with only_these_tools():
            self.assertIsNone(paste.read_clipboard())

    def test_what_is_on_the_clipboard_comes_back_as_bytes(self):
        with only_these_tools("wl-paste"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted(stdout=b"hello")) as run:
            self.assertEqual(paste.read_clipboard(), b"hello")
        self.assertEqual(run.call_args.args[0], ["wl-paste", "--no-newline"])

    def test_an_empty_clipboard_is_not_an_error(self):
        with only_these_tools("wl-paste"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted(returncode=1)):
            self.assertIsNone(paste.read_clipboard())

    def test_a_tool_that_will_not_run(self):
        with only_these_tools("wl-paste"), \
                mock.patch.object(subprocess, "run", side_effect=OSError("nope")):
            self.assertIsNone(paste.read_clipboard())


@linux_only
class Copy(DikteTest):
    def test_no_wl_copy_installed(self):
        with only_these_tools(), self.assertRaises(paste.PasteError) as caught:
            paste.copy("hello")
        self.assertIn("wl-clipboard", str(caught.exception))

    def test_the_text_goes_in_as_utf8(self):
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted()) as run:
            paste.copy("günaydın")
        self.assertEqual(run.call_args.kwargs["input"], "günaydın".encode())

    def test_the_pipes_are_closed_so_the_call_can_return(self):
        """wl-copy forks and holds the selection; a pipe nobody drains hangs."""
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted()) as run:
            paste.copy("hello")
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_a_non_zero_exit_is_reported(self):
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted(returncode=1)), \
                self.assertRaises(paste.PasteError):
            paste.copy("hello")

    def test_a_tool_that_will_not_run(self):
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run", side_effect=OSError("nope")), \
                self.assertRaises(paste.PasteError):
            paste.copy("hello")


@linux_only
class CopyBytes(DikteTest):
    def test_nothing_to_restore(self):
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run") as run:
            paste.copy_bytes(None)
        run.assert_not_called()

    def test_restoring_never_raises(self):
        """It runs after the paste went in; failing here must not undo that."""
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run", side_effect=OSError("nope")):
            paste.copy_bytes(b"whatever was there before")

    def test_the_bytes_go_back_untouched(self):
        with only_these_tools("wl-copy"), \
                mock.patch.object(subprocess, "run",
                                  return_value=FakeCompleted()) as run:
            paste.copy_bytes(b"\x89PNG\r\n")
        self.assertEqual(run.call_args.kwargs["input"], b"\x89PNG\r\n")


@linux_only
class Press(DikteTest):
    def setUp(self):
        super().setUp()
        # The settle delay is real time nobody needs to spend in a test.
        self.patch_attr(paste.time, "sleep", lambda seconds: None)

    def run_press(self, shortcut, result=None):
        with only_these_tools("ydotool"), \
                mock.patch.object(subprocess, "run",
                                  return_value=result or FakeCompleted()) as run:
            paste.press(shortcut)
        return run.call_args.args[0]

    def test_no_ydotool_installed(self):
        with only_these_tools():
            self.assertFalse(paste.ydotool_ready())
            with self.assertRaises(paste.PasteError):
                paste.press()

    def test_ctrl_v_presses_down_then_lets_go_in_reverse(self):
        self.assertEqual(self.run_press("ctrl+v"),
                         ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])

    def test_three_keys(self):
        self.assertEqual(self.run_press("ctrl+shift+v"),
                         ["ydotool", "key", "29:1", "42:1", "47:1",
                          "47:0", "42:0", "29:0"])

    def test_case_and_spacing_do_not_matter(self):
        self.assertEqual(self.run_press(" Ctrl + V "), self.run_press("ctrl+v"))

    def test_the_synonyms_land_on_the_same_codes(self):
        self.assertEqual(self.run_press("control+insert"),
                         ["ydotool", "key", "29:1", "110:1", "110:0", "29:0"])
        self.assertEqual(self.run_press("super+enter"), self.run_press("meta+return"))

    def test_a_key_nobody_mapped(self):
        with only_these_tools("ydotool"), mock.patch.object(subprocess, "run"), \
                self.assertRaises(paste.PasteError) as caught:
            paste.press("ctrl+f13")
        self.assertIn("f13", str(caught.exception))

    def test_ydotoold_not_running_says_so(self):
        with self.assertRaises(paste.PasteError) as caught:
            self.run_press("ctrl+v", FakeCompleted(returncode=1, stderr="no socket"))
        self.assertIn("ydotoold", str(caught.exception))

    def test_a_tool_that_will_not_run(self):
        with only_these_tools("ydotool"), \
                mock.patch.object(subprocess, "run", side_effect=OSError("nope")), \
                self.assertRaises(paste.PasteError):
            paste.press("ctrl+v")


if __name__ == "__main__":
    unittest.main()

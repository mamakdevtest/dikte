"""Parsing a shortcut, and the KDE entry it is installed as."""

import subprocess
import unittest
from unittest import mock

import hotkey
from tests.support import DikteTest, FakeCompleted, linux_only

SHORTCUTS_RC = """[services][dikte-toggle.desktop]
_launch=Ctrl+Space

[services][org.kde.spectacle.desktop]
RectangularRegionScreenShot=Meta+Shift+Print\tMeta+Shift+Print\t

[kwin]
Overview=Meta+W,Meta+W,Toggle Overview
Switch Window Down=Meta+Alt+Down,Meta+Alt+Down,Switch to Window Below
"""


class ParseShortcut(unittest.TestCase):
    def test_the_default(self):
        self.assertEqual(hotkey.parse_shortcut("Ctrl+Space"), ({"ctrl"}, 57))

    def test_case_and_spacing_do_not_matter(self):
        self.assertEqual(hotkey.parse_shortcut(" ctrl + SPACE "), ({"ctrl"}, 57))

    def test_several_modifiers(self):
        mods, key = hotkey.parse_shortcut("Ctrl+Alt+Shift+D")
        self.assertEqual(mods, {"ctrl", "alt", "shift"})
        self.assertEqual(key, 32)

    def test_the_synonyms_land_on_one_name(self):
        self.assertEqual(hotkey.parse_shortcut("Control+Space"),
                         hotkey.parse_shortcut("Ctrl+Space"))
        self.assertEqual(hotkey.parse_shortcut("Meta+Space"),
                         hotkey.parse_shortcut("Super+Space"))

    def test_a_key_on_its_own(self):
        self.assertEqual(hotkey.parse_shortcut("F9"), (set(), 67))

    def test_modifiers_with_no_key(self):
        self.assertEqual(hotkey.parse_shortcut("Ctrl+Alt"), (None, None))

    def test_a_key_nobody_mapped(self):
        self.assertEqual(hotkey.parse_shortcut("Ctrl+F13"), (None, None))

    def test_nothing(self):
        self.assertEqual(hotkey.parse_shortcut(""), (None, None))
        self.assertEqual(hotkey.parse_shortcut("+++"), (None, None))

    def test_something_that_is_not_even_a_string(self):
        self.assertEqual(hotkey.parse_shortcut(None), (None, None))


class ModsMatch(unittest.TestCase):
    """The combination has to be exact, or Ctrl+Space fires on Ctrl+Shift+Space."""

    def match(self, held, wanted):
        return hotkey.EvdevHotkey._mods_match(set(held), set(wanted))

    def test_the_wanted_modifier_is_down(self):
        self.assertTrue(self.match({29}, {"ctrl"}))

    def test_either_side_of_the_keyboard_counts(self):
        self.assertTrue(self.match({97}, {"ctrl"}))

    def test_nothing_held_and_nothing_wanted(self):
        self.assertTrue(self.match(set(), set()))

    def test_a_modifier_too_many(self):
        self.assertFalse(self.match({29, 42}, {"ctrl"}))

    def test_a_modifier_missing(self):
        self.assertFalse(self.match(set(), {"ctrl"}))

    def test_the_wrong_modifier(self):
        self.assertFalse(self.match({56}, {"ctrl"}))


@linux_only
class Bindings(DikteTest):
    """start() before it reaches /dev/input, which a test may not read."""

    def test_a_binding_with_no_shortcut_is_skipped(self):
        listener = hotkey.EvdevHotkey()
        with mock.patch.object(listener, "_open_devices", return_value=[]):
            self.assertFalse(listener.start({"toggle": "", "ask": ""}))

    def test_an_unparsable_shortcut_is_reported_and_the_rest_go_on(self):
        listener = hotkey.EvdevHotkey()
        self.addCleanup(listener.stop)
        failures = []
        listener.failed.connect(failures.append)
        with mock.patch.object(listener, "_open_devices", return_value=[99]), \
                mock.patch.object(hotkey.threading, "Thread"):
            self.assertTrue(listener.start({"toggle": "Ctrl+F13",
                                            "ask": "Ctrl+Space"}))
        self.assertEqual(len(failures), 1)
        self.assertIn("Ctrl+F13", failures[0])
        self.assertEqual(list(listener._bindings), [57])

    def test_no_readable_devices_says_what_to_do_about_it(self):
        listener = hotkey.EvdevHotkey()
        failures = []
        listener.failed.connect(failures.append)
        with mock.patch.object(listener, "_open_devices", return_value=[]):
            self.assertFalse(listener.start({"toggle": "Ctrl+Space"}))
        self.assertIn("input", failures[0])

    def test_two_shortcuts_on_one_key_are_both_kept(self):
        listener = hotkey.EvdevHotkey()
        self.addCleanup(listener.stop)
        with mock.patch.object(listener, "_open_devices", return_value=[]), \
                mock.patch.object(hotkey.threading, "Thread") as thread:
            listener._open_devices.return_value = [99]
            self.assertTrue(listener.start({"toggle": "Ctrl+Space",
                                            "ask": "Ctrl+Alt+Space"}))
            thread.assert_called_once()
        self.assertEqual(len(listener._bindings[57]), 2)


@linux_only
class KdeShortcut(DikteTest):
    def setUp(self):
        super().setUp()
        self.apps = self.path("applications")
        self.apps.mkdir(parents=True)
        self.rc = self.path("kglobalshortcutsrc")
        self.patch_attr(hotkey, "APPLICATIONS_DIR", self.apps)
        self.patch_attr(hotkey, "SHORTCUTS_FILE", self.rc)

    def test_installing_writes_a_desktop_file_kwin_will_launch(self):
        with mock.patch.object(subprocess, "run", return_value=FakeCompleted()):
            ok, message = hotkey.install_kde_shortcut("Ctrl+Space", "dikte toggle")
        self.assertTrue(ok)
        text = (self.apps / hotkey.DESKTOP_ID).read_text(encoding="utf-8")
        self.assertIn("Exec=dikte toggle", text)
        self.assertIn("X-KDE-GlobalAccel-CommandShortcut=true", text)
        self.assertIn("log out", message)

    def test_the_shortcut_is_registered_under_the_desktop_id(self):
        with mock.patch.object(subprocess, "run",
                               return_value=FakeCompleted()) as run:
            hotkey.install_kde_shortcut("Meta+D", "dikte ask",
                                        desktop_id=hotkey.ASK_DESKTOP_ID)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "kwriteconfig6")
        self.assertIn(hotkey.ASK_DESKTOP_ID, cmd)
        self.assertEqual(cmd[-1], "Meta+D")

    def test_each_verb_gets_its_own_entry(self):
        with mock.patch.object(subprocess, "run", return_value=FakeCompleted()):
            hotkey.install_kde_shortcut("Ctrl+Space", "dikte toggle")
            hotkey.install_kde_shortcut("Meta+M", "dikte meeting",
                                        desktop_id=hotkey.MEETING_DESKTOP_ID)
        self.assertTrue((self.apps / hotkey.DESKTOP_ID).exists())
        self.assertTrue((self.apps / hotkey.MEETING_DESKTOP_ID).exists())

    def test_no_kwriteconfig_installed(self):
        with mock.patch.object(subprocess, "run", side_effect=OSError("nope")):
            ok, message = hotkey.install_kde_shortcut("Ctrl+Space", "dikte toggle")
        self.assertFalse(ok)
        self.assertIn("kglobalshortcutsrc", message)

    def test_removing_takes_the_desktop_file_with_it(self):
        (self.apps / hotkey.DESKTOP_ID).write_text("[Desktop Entry]", encoding="utf-8")
        with mock.patch.object(subprocess, "run", return_value=FakeCompleted()) as run:
            hotkey.remove_kde_shortcut()
        self.assertFalse((self.apps / hotkey.DESKTOP_ID).exists())
        self.assertIn("--delete", run.call_args.args[0])

    def test_removing_one_that_was_never_installed(self):
        with mock.patch.object(subprocess, "run", side_effect=OSError("nope")):
            hotkey.remove_kde_shortcut()   # must not raise

    def test_the_registered_shortcut_is_read_back(self):
        (self.apps / hotkey.DESKTOP_ID).write_text("[Desktop Entry]", encoding="utf-8")
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        self.assertEqual(hotkey.kde_shortcut_status(), "Ctrl+Space")

    def test_no_desktop_file_means_nothing_is_installed(self):
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        self.assertIsNone(hotkey.kde_shortcut_status())

    def test_a_desktop_file_with_no_entry_beside_it(self):
        (self.apps / hotkey.DESKTOP_ID).write_text("[Desktop Entry]", encoding="utf-8")
        self.rc.write_text("[kwin]\nOverview=Meta+W\n", encoding="utf-8")
        self.assertIsNone(hotkey.kde_shortcut_status())

    def test_no_shortcuts_file_at_all(self):
        (self.apps / hotkey.DESKTOP_ID).write_text("[Desktop Entry]", encoding="utf-8")
        self.assertIsNone(hotkey.kde_shortcut_status())

    def test_a_combination_somebody_else_already_took(self):
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        hits = hotkey.conflicting_shortcuts("Meta+W")
        self.assertEqual(len(hits), 1)
        self.assertIn("kwin", hits[0])
        self.assertIn("Overview", hits[0])

    def test_our_own_entry_is_not_a_conflict(self):
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        self.assertEqual(hotkey.conflicting_shortcuts("Ctrl+Space"), [])

    def test_a_free_combination(self):
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        self.assertEqual(hotkey.conflicting_shortcuts("Ctrl+Alt+J"), [])

    def test_a_tab_separated_entry_is_read_too(self):
        self.rc.write_text(SHORTCUTS_RC, encoding="utf-8")
        hits = hotkey.conflicting_shortcuts("Meta+Shift+Print")
        self.assertEqual(len(hits), 1)
        self.assertIn("spectacle", hits[0])

    def test_no_shortcuts_file_means_no_conflicts(self):
        self.assertEqual(hotkey.conflicting_shortcuts("Ctrl+Space"), [])


if __name__ == "__main__":
    unittest.main()

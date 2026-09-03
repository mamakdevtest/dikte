"""Custom-prompt opt-in gate: single flag contract."""

import config as cfg
from tests.support import DikteTest, only_these_tools


class CustomPromptGate(DikteTest):
    def test_default_is_off(self):
        conf = cfg.Config()
        self.assertIn("cleanup_custom_enabled", cfg.DEFAULTS)
        self.assertFalse(conf["cleanup_custom_enabled"])

    def test_off_ignores_stored_custom_dictation(self):
        conf = self.config(
            cleanup_custom_enabled=False,
            cleanup_prompt="MY CUSTOM PROMPT",
            transcribe_prompt="",
        )
        prompt = conf.cleanup_prompt()
        self.assertNotIn("MY CUSTOM PROMPT", prompt)
        # default still builds (contains policy header)
        self.assertIn("Editing Level", prompt)

    def test_off_ignores_stored_custom_file(self):
        conf = self.config(
            cleanup_custom_enabled=False,
            file_cleanup_prompt="MY FILE CUSTOM",
            transcribe_prompt="",
        )
        prompt = conf.cleanup_prompt(subtitles=True)
        self.assertNotIn("MY FILE CUSTOM", prompt)

    def test_on_uses_custom_dictation(self):
        conf = self.config(
            cleanup_custom_enabled=True,
            cleanup_prompt="MY CUSTOM PROMPT",
            transcribe_prompt="",
        )
        self.assertIn("MY CUSTOM PROMPT", conf.cleanup_prompt())

    def test_on_uses_custom_file(self):
        conf = self.config(
            cleanup_custom_enabled=True,
            file_cleanup_prompt="MY FILE CUSTOM",
            transcribe_prompt="",
        )
        self.assertIn("MY FILE CUSTOM", conf.cleanup_prompt(subtitles=True))

    def test_migration_preserves_existing_custom(self):
        self.write_config({"cleanup_prompt": "my own words"})
        conf = cfg.Config()
        self.assertTrue(conf["cleanup_custom_enabled"])
        self.assertEqual(conf["cleanup_prompt"], "my own words")

    def test_migration_empty_stays_off(self):
        self.write_config({})
        conf = cfg.Config()
        self.assertFalse(conf["cleanup_custom_enabled"])

    def test_glossary_still_applies_when_off(self):
        conf = self.config(
            cleanup_custom_enabled=False,
            cleanup_prompt="SHOULD BE IGNORED",
            transcribe_prompt="Zeynep",
        )
        prompt = conf.cleanup_prompt()
        self.assertNotIn("SHOULD BE IGNORED", prompt)
        self.assertIn("Zeynep", prompt)


class CustomPromptGateUI(DikteTest):
    def _window(self, conf):
        import sys
        from unittest import mock
        from PyQt6.QtWidgets import QMessageBox
        import providers
        import settings_ui
        from tests.test_ui import release
        self.enterContext(mock.patch.object(sys, "platform", "linux"))
        self.enterContext(only_these_tools())
        self.enterContext(mock.patch.object(QMessageBox, "information"))
        self.enterContext(mock.patch.object(
            settings_ui.SettingsWindow, "_load_models"))
        self.enterContext(mock.patch.object(
            settings_ui.SettingsWindow, "_load_transcribe_models"))
        self.enterContext(mock.patch.object(
            providers, "executable_version", return_value=None))
        self.enterContext(mock.patch.object(
            settings_ui.SettingsWindow, "_fetch_cli_versions"))
        window = settings_ui.SettingsWindow(conf)
        self.addCleanup(release, window)
        return window

    def test_toggle_exists_and_gates_tabs(self):
        import config as cfg
        conf = cfg.Config()
        window = self._window(conf)
        self.assertTrue(hasattr(window, "cleanup_custom_enabled"))
        self.assertTrue(hasattr(window, "cleanup_prompt_tabs"))
        # default off -> tabs disabled
        self.assertFalse(window.cleanup_custom_enabled.isChecked())
        self.assertFalse(window.cleanup_prompt_tabs.isEnabled())
        # on -> tabs enabled
        window.cleanup_custom_enabled.setChecked(True)
        self.assertTrue(window.cleanup_prompt_tabs.isEnabled())

    def test_save_off_clears_customs(self):
        import config as cfg
        conf = self.config(cleanup_custom_enabled=True,
                           cleanup_prompt="mine",
                           file_cleanup_prompt="mine file")
        window = self._window(conf)
        self.assertTrue(window.cleanup_custom_enabled.isChecked())
        window.cleanup_custom_enabled.setChecked(False)
        window._save()
        self.assertFalse(conf["cleanup_custom_enabled"])
        self.assertEqual(conf["cleanup_prompt"], "")
        self.assertEqual(conf["file_cleanup_prompt"], "")

    def test_save_on_preserves_customs(self):
        import config as cfg
        conf = cfg.Config()
        window = self._window(conf)
        window.cleanup_custom_enabled.setChecked(True)
        window.cleanup_prompt.setPlainText("my dictation rules")
        window.file_cleanup_prompt.setPlainText("my file rules")
        window._save()
        self.assertTrue(conf["cleanup_custom_enabled"])
        self.assertEqual(conf["cleanup_prompt"], "my dictation rules")
        self.assertEqual(conf["file_cleanup_prompt"], "my file rules")


if __name__ == "__main__":
    import unittest
    unittest.main()

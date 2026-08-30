"""The single Editing Level policy's legacy-config migration contract."""

import config as cfg
from tests.support import DikteTest


class ShorteningFreedomMigration(DikteTest):
    def test_legacy_shortening_value_is_ignored_and_not_retained_in_runtime_settings(self):
        self.write_config({"ai_edit_level": 2, "ai_shortening_freedom": 100})

        conf = cfg.Config()

        self.assertEqual(conf["ai_edit_level"], 2)
        self.assertNotIn("ai_shortening_freedom", conf.data)
        self.assertEqual(
            conf.ai_policy(language="en"),
            self.config(ai_edit_level=2).ai_policy(language="en"),
        )
        conf.save()
        self.assertNotIn("ai_shortening_freedom", self.read_config_file())


if __name__ == "__main__":
    import unittest
    unittest.main()

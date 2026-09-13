"""The diagnostics bundle: what it promises is what the tests check.

This file leaves the machine, so the promises are the whole feature: no secret value, no
audio, no transcript text, and a README that says all of that so the person attaching the
bundle to a bug report can check the claim instead of trusting it.
"""

import json
import unittest
import zipfile
from unittest import mock

import config as cfg
import diagnostics
from tests.support import DikteTest

# The kind of thing that must not survive: a fake key, a fake token, a fake gateway secret.
KEY = "sk-live-abcdefghijklmnopqrstuvwxyz012345"
TOKEN = "hf_QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ"
GATEWAY = "gw-9f8e7d6c5b4a"


class DiagnosticsTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(
            openai_api_key=KEY,
            openai_base_url="https://api.openai.com/v1",
            local_model="ggml-tiny.en.bin",
            providers=[{"id": "user/acme", "name": "Acme", "api_key": GATEWAY,
                        "base_url": "https://acme.example/v1", "models": ["x"]}],
            hf_token=TOKEN,
            cleanup_enabled=True,
        )
        self.bundle_path = self.path("dikte-diagnostics.zip")

    def write_log(self, text):
        cfg.log_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.log_path().write_text(text, encoding="utf-8")

    def build(self):
        target, sizes = diagnostics.bundle(self.conf, self.bundle_path,
                                           checks={"transcription": {"provider": "openai"}})
        self.assertTrue(sizes, "the bundle should have said what went into it")
        return target

    def members(self, target):
        with zipfile.ZipFile(target) as archive:
            return {name: archive.read(name).decode("utf-8", "replace")
                    for name in archive.namelist()}


class NoSecretLeavesTheMachine(DiagnosticsTest):
    def test_the_settings_summary_masks_them_by_name(self):
        piece = self.members(self.build())["settings.json"]
        settings = json.loads(piece)
        self.assertEqual(diagnostics.MASK, settings["openai_api_key"])
        self.assertEqual(diagnostics.MASK, settings["hf_token"])
        self.assertEqual(diagnostics.MASK, settings["providers"][0]["api_key"])
        # Everything that is not secret is still there: a bundle that hides the settings it
        # is meant to explain would be useless.
        self.assertEqual("ggml-tiny.en.bin", settings["local_model"])
        self.assertEqual("https://acme.example/v1", settings["providers"][0]["base_url"])

    def test_a_key_echoed_into_the_log_comes_out_masked(self):
        self.write_log(f"dikte: request failed with {KEY}\n"
                       f"dikte: gateway said {GATEWAY}\n"
                       "dikte: and this line is nothing to do with any of it\n")
        piece = self.members(self.build())["log.txt"]
        self.assertNotIn(KEY, piece)
        self.assertNotIn(GATEWAY, piece)
        self.assertIn(diagnostics.MASK, piece)
        self.assertIn("nothing to do with any of it", piece,
                      "the rest of the log is why the log is in the bundle at all")

    def test_no_member_of_the_archive_carries_a_secret(self):
        self.write_log(f"dikte: {KEY} and {TOKEN} and {GATEWAY}\n")
        pieces = self.members(self.build())
        self.assertEqual(["README.txt", "doctor.json", "environment.json", "history.json",
                          "log.txt", "settings.json"], sorted(pieces))
        for name, text in pieces.items():
            for secret in (KEY, TOKEN, GATEWAY):
                self.assertNotIn(secret, text, f"{name} carries a secret")

    def test_a_secret_too_short_to_scrub_is_still_masked_by_name(self):
        """Scrubbing is for values; masking by name is the belt to its braces."""
        self.conf.data["groq_api_key"] = "abc"
        settings = json.loads(self.members(self.build())["settings.json"])
        self.assertEqual(diagnostics.MASK, settings["groq_api_key"])


class NothingSaidIsCopied(DiagnosticsTest):
    def test_the_history_is_counted_and_not_quoted(self):
        cfg.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"text": "the other thing I said", "error": "no engine"},
                {"text": "my bank password is hunter2", "ts": "2026-09-13 10:00:00"}]
        cfg.HISTORY_FILE.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        pieces = self.members(self.build())
        counts = json.loads(pieces["history.json"])
        self.assertEqual({"dictations": 2, "failed": 1, "last": "2026-09-13 10:00:00"}, counts)
        self.assertNotIn("hunter2", pieces["history.json"])
        self.assertNotIn("hunter2", pieces["README.txt"])

    def test_an_unreadable_history_is_reported_rather_than_counted_as_empty(self):
        with mock.patch.object(cfg, "read_history", side_effect=OSError("locked")):
            counts = diagnostics.history_counts()
        self.assertIsNone(counts["dictations"])
        self.assertIn("locked", counts["error"])


class ItSaysWhatItIs(DiagnosticsTest):
    def test_the_readme_lists_the_files_and_the_promises(self):
        readme = self.members(self.build())["README.txt"]
        for name in ("doctor.json", "environment.json", "settings.json", "history.json",
                     "log.txt"):
            self.assertIn(name, readme)
        self.assertIn("no API keys or tokens", readme)
        self.assertIn("no audio, and no transcript text", readme)
        self.assertIn("nothing was sent anywhere", readme)

    def test_an_environment_without_a_log_says_nothing_rather_than_failing(self):
        pieces = self.members(self.build())
        self.assertEqual("", pieces["log.txt"])
        self.assertIn("README.txt", pieces)

    def test_the_environment_names_the_platform_and_the_dirs(self):
        environment = json.loads(self.members(self.build())["environment.json"])
        for field in ("dikte", "python", "frozen", "platform", "session", "config_dir",
                      "data_dir", "log"):
            self.assertIn(field, environment)
        self.assertEqual({"transcription": {"provider": "openai"}}, environment["checks"])


if __name__ == "__main__":
    unittest.main()

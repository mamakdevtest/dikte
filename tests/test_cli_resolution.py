"""agy off the PATH on Windows still runs from its install folder.

The Antigravity installer drops agy.exe under %LOCALAPPDATA% and the PATH
entry is the documented #1 Windows install issue, so every road that shells
out to a CLI — version check, model fetch, Test button, cleanup, agent ask —
must resolve the binary beyond shutil.which.
"""

import os
import subprocess
import sys
from unittest import mock

import assistant
import cleanup
import providers
from tests.support import DikteTest, FakeCompleted, only_these_tools


def windows(env_root, present):
    """Pretend to be Windows: no PATH hit, agy.exe under %LOCALAPPDATA%."""
    stack = [
        only_these_tools(),
        mock.patch.object(os, "name", "nt"),
        mock.patch.dict(os.environ, {"LOCALAPPDATA": env_root}),
        mock.patch("os.path.isfile", side_effect=lambda p: p in present),
    ]
    return stack


class ResolveBinary(DikteTest):
    def test_a_path_hit_runs_by_name(self):
        with only_these_tools("agy"):
            self.assertEqual(providers.resolve_binary("agy"), "agy")

    def test_a_path_miss_off_windows_is_none(self):
        with only_these_tools():
            self.assertIsNone(providers.resolve_binary("agy"))

    def test_windows_falls_back_to_the_installer_folder(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "agy", "bin", "agy.exe")
        for ctx in windows(root, {wanted}):
            self.enterContext(ctx)
        self.assertEqual(providers.resolve_binary("agy"), wanted)

    def test_windows_tries_the_alternate_install_folder(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "Antigravity", "agy.exe")
        for ctx in windows(root, {wanted}):
            self.enterContext(ctx)
        self.assertEqual(providers.resolve_binary("agy"), wanted)

    def test_windows_miss_is_still_none(self):
        root = str(self.path("localappdata"))
        for ctx in windows(root, set()):
            self.enterContext(ctx)
        self.assertIsNone(providers.resolve_binary("agy"))

    def test_posix_ignores_the_install_folders(self):
        root = str(self.path("localappdata"))
        with only_these_tools(), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": root}), \
                mock.patch("os.path.isfile", return_value=True):
            self.assertIsNone(providers.resolve_binary("agy"))

    def test_only_agy_has_a_fallback(self):
        root = str(self.path("localappdata"))
        for ctx in windows(root, {os.path.join(root, "agy", "bin", "agy.exe")}):
            self.enterContext(ctx)
        self.assertIsNone(providers.resolve_binary("codex"))

    def test_empty_name_is_none(self):
        with only_these_tools("agy"):
            self.assertIsNone(providers.resolve_binary(""))

    def test_env_override_wins_over_path(self):
        override = str(self.path("custom", "agy.exe"))
        with only_these_tools("agy"), \
                mock.patch.dict(os.environ, {"AGY_BINARY": override}), \
                mock.patch("os.path.isfile", return_value=True):
            self.assertEqual(providers.resolve_binary("agy"), override)

    def test_env_override_missing_file_falls_through(self):
        with only_these_tools("agy"), \
                mock.patch.dict(os.environ, {"AGY_BINARY": str(self.path("nope", "agy.exe"))}), \
                mock.patch("os.path.isfile", return_value=False):
            self.assertEqual(providers.resolve_binary("agy"), "agy")

    def test_registry_app_paths_found(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "agy", "bin", "agy.exe")
        fake = mock.MagicMock()
        fake.QueryValueEx.return_value = (wanted, 1)
        with only_these_tools(), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.dict(sys.modules, {"winreg": fake}), \
                mock.patch("os.path.isfile",
                           side_effect=lambda p: p == wanted):
            self.assertEqual(providers.resolve_binary("agy"), wanted)

    def test_conf_cache_hit_runs(self):
        cached = str(self.path("cache", "agy.exe"))
        conf = self.config(cli_binary_cache={"agy": cached})
        with only_these_tools(), \
                mock.patch("os.path.isfile",
                           side_effect=lambda p: p == cached):
            self.assertEqual(providers.resolve_binary("agy", conf), cached)

    def test_stale_conf_cache_is_ignored(self):
        conf = self.config(
            cli_binary_cache={"agy": str(self.path("gone", "agy.exe"))})
        with only_these_tools(), \
                mock.patch("os.path.isfile", return_value=False):
            self.assertIsNone(providers.resolve_binary("agy", conf))


class WindowsRoads(DikteTest):
    def test_agent_ask_runs_the_fallback_binary(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "agy", "bin", "agy.exe")
        for ctx in windows(root, {wanted}):
            self.enterContext(ctx)
        conf = self.config(assistant_provider="antigravity")
        result = FakeCompleted(stdout="  done  \n", returncode=0)
        with mock.patch.object(subprocess, "run",
                               return_value=result) as run:
            answer, warning = assistant.ask("book it", conf, None)
        self.assertEqual(answer, "done")
        self.assertEqual(run.call_args.args[0][0], wanted)

    def test_cleanup_runs_the_fallback_binary(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "agy", "bin", "agy.exe")
        for ctx in windows(root, {wanted}):
            self.enterContext(ctx)
        conf = self.config(cleanup_provider="antigravity")
        result = FakeCompleted(stdout="  cleaned  \n", returncode=0)
        with mock.patch.object(subprocess, "run",
                               return_value=result) as run:
            self.assertEqual(
                cleanup.run("raw words", conf, "rules").strip(), "cleaned")
        self.assertEqual(run.call_args.args[0][0], wanted)

    def test_version_check_sees_the_fallback_binary(self):
        root = str(self.path("localappdata"))
        wanted = os.path.join(root, "agy", "bin", "agy.exe")
        for ctx in windows(root, {wanted}):
            self.enterContext(ctx)
        self.assertEqual(providers.executable("antigravity"), wanted)


class DeepSearch(DikteTest):
    def tree(self):
        root = self.path("drive")
        (root / "tools" / "agy").mkdir(parents=True)
        (root / "tools" / "agy" / "agy.exe").write_text("x")
        (root / "tools" / "other.exe").write_text("x")
        (root / "Windows").mkdir(parents=True, exist_ok=True)
        (root / "Windows" / "agy.exe").write_text("trap")
        return root

    def test_finds_the_binary_anywhere_under_the_roots(self):
        root = self.tree()
        self.assertEqual(
            providers.deep_search_binary("agy", roots=[str(root)]),
            str(root / "tools" / "agy" / "agy.exe"))

    def test_system_folders_are_not_entered(self):
        root = self.tree()
        found = providers.deep_search_binary("agy", roots=[str(root)])
        self.assertNotIn("Windows", found)

    def test_miss_is_none(self):
        root = self.path("empty")
        root.mkdir(parents=True, exist_ok=True)
        self.assertIsNone(
            providers.deep_search_binary("agy", roots=[str(root)]))

    def test_no_roots_off_windows_is_none(self):
        self.assertIsNone(providers.deep_search_binary("agy"))

    def test_locate_remembers_the_hit_in_conf(self):
        root = self.tree()
        conf = self.config()
        with only_these_tools():
            found = providers.locate_binary("agy", conf,
                                            roots=[str(root)])
        self.assertEqual(found, str(root / "tools" / "agy" / "agy.exe"))
        self.assertEqual(conf["cli_binary_cache"]["agy"], found)

    def test_locate_miss_leaves_conf_alone(self):
        root = self.path("empty")
        root.mkdir(parents=True, exist_ok=True)
        conf = self.config()
        with only_these_tools():
            self.assertIsNone(
                providers.locate_binary("agy", conf, roots=[str(root)]))
        self.assertEqual(conf["cli_binary_cache"], {})

    def test_models_fetch_walks_when_needed(self):
        root = self.tree()
        conf = self.config()
        exe = str(root / "tools" / "agy" / "agy.exe")
        reply = FakeCompleted(stdout="gemini-3.6-flash-medium\tGemini\n",
                              returncode=0)
        with only_these_tools(), \
                mock.patch.object(subprocess, "run",
                                  return_value=reply) as run:
            models = providers.agy_models(conf=conf, roots=[str(root)])
        self.assertEqual(models, ["gemini-3.6-flash-medium"])
        self.assertEqual(run.call_args.args[0][0], exe)
        self.assertEqual(conf["cli_binary_cache"]["agy"], exe)


if __name__ == "__main__":
    import unittest
    unittest.main()

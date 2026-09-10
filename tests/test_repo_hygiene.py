"""Repository hygiene: no tracked files may carry real-looking secrets."""

import re
import subprocess
import unittest

REPO = __import__("pathlib").Path(__file__).resolve().parent.parent

_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")

_SKIP_PREFIXES = ("tests/", "tools/")
_SKIP_FILES = {"repomix-output.xml", ".codex/config.example.toml"}


def _tracked_files():
    out = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if out.returncode != 0:
        self_skip = unittest.SkipTest("not a git checkout")
        raise self_skip
    return out.stdout.splitlines()


class TestRepoHygiene(unittest.TestCase):
    def test_codex_config_not_tracked(self):
        self.assertNotIn(".codex/config.toml", _tracked_files())

    def test_no_real_looking_tokens_in_tracked_files(self):
        offenders = []
        for rel in _tracked_files():
            if rel in _SKIP_FILES or rel.startswith(_SKIP_PREFIXES):
                continue
            path = REPO / rel
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if _TOKEN_RE.search(text):
                offenders.append(rel)
        self.assertEqual([], offenders, f"tracked files with token-like values: {offenders}")


if __name__ == "__main__":
    unittest.main()

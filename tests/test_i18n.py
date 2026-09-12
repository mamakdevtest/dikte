"""Translation lookup, and the table itself.

The table test is the one that matters for a pull request: a Turkish string
whose placeholder was renamed raises KeyError at the moment the message is
shown, which is exactly when nobody is watching a terminal.
"""

import ast
import json
import pathlib
import string
import unittest
from unittest import mock

import i18n
from tests.support import DikteTest

REPO = pathlib.Path(__file__).resolve().parent.parent
GAPS_FILE = pathlib.Path(__file__).resolve().parent / "i18n_untranslated.json"

# What a module calls the translator. `ui/shell.py` imports it as `_t`, and the
# alias was invisible to this scan until 2026-09-12 — which is how the sidebar
# chips "Local" and "Ready" stayed English in a Turkish window.
ALIASES = ("t", "_t")


def untranslated_strings(repo=None):
    """{string: [where it is asked for]} for every t() literal with no entry.

    Product code only: the tests and the tools speak to a developer, not to the
    person using Dikte, and `i18n.py` is the table itself.
    """
    root = pathlib.Path(repo) if repo else REPO
    paths = [path for path in
             sorted(root.glob("*.py")) + sorted(root.glob("ui/**/*.py"))
             if path.name != "i18n.py" and "__pycache__" not in path.parts]
    found = {}
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name not in ALIASES:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            if first.value and first.value not in i18n.TR:
                where = found.setdefault(first.value, [])
                site = f"{path.relative_to(root)}:{node.lineno}"
                if site not in where:
                    where.append(site)
    return {key: sorted(value) for key, value in sorted(found.items())}


def recorded_gaps():
    """The gaps the repository accepts today, as {string: [where]}."""
    payload = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
    return payload["gaps"]


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class Resolve(unittest.TestCase):
    def test_an_explicit_language_wins(self):
        with mock.patch.dict("os.environ", {"LANG": "tr_TR.UTF-8"}):
            self.assertEqual(i18n.resolve("en"), "en")
            self.assertEqual(i18n.resolve("tr"), "tr")

    def test_auto_reads_the_locale(self):
        with mock.patch.dict("os.environ", {"LANG": "tr_TR.UTF-8"}, clear=True):
            self.assertEqual(i18n.resolve("auto"), "tr")
        with mock.patch.dict("os.environ", {"LANG": "en_GB.UTF-8"}, clear=True):
            self.assertEqual(i18n.resolve("auto"), "en")

    def test_lc_all_outranks_lang(self):
        with mock.patch.dict("os.environ",
                             {"LC_ALL": "tr_TR.UTF-8", "LANG": "en_GB.UTF-8"},
                             clear=True):
            self.assertEqual(i18n.resolve("auto"), "tr")

    def test_no_locale_at_all_falls_back_to_english(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(i18n.resolve("auto"), "en")

    def test_an_unknown_code_is_not_taken_at_its_word(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(i18n.resolve("de"), "en")


class Translate(DikteTest):
    def test_english_returns_the_source_string(self):
        self.assertEqual(i18n.t("Quit"), "Quit")

    def test_turkish_looks_the_string_up(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.t("Quit"), "Çık")

    def test_an_untranslated_string_falls_through(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.t("Nobody translated this"), "Nobody translated this")

    def test_placeholders_are_filled_in_both_languages(self):
        self.assertEqual(i18n.t("Unknown key: {key}", key="f13"), "Unknown key: f13")
        i18n.set_language("tr")
        self.assertIn("f13", i18n.t("Unknown key: {key}", key="f13"))

    def test_a_string_with_no_arguments_is_not_formatted(self):
        # Braces in the text itself must survive when nothing is passed in.
        self.assertEqual(i18n.t("{not a placeholder}"), "{not a placeholder}")

    def test_a_placeholder_may_be_called_anything(self):
        """Including the names of t()'s own parameters, which is why they are
        positional-only: worker.py says {text}, and that has to work."""
        self.assertEqual(i18n.t("Discarded: {text}", text="hello"), "Discarded: hello")
        self.assertEqual(i18n.name("Claude", case="dative"), "Claude")


class Names(DikteTest):
    def test_english_leaves_the_name_alone(self):
        self.assertEqual(i18n.name("Claude", "dative"), "Claude")

    def test_turkish_inflects_by_the_vowels_of_the_name(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.name("Claude", "dative"), "Claude'a")
        self.assertEqual(i18n.name("Codex", "dative"), "Codex'e")
        self.assertEqual(i18n.name("OpenRouter", "accusative"), "OpenRouter'ı")
        self.assertEqual(i18n.name("Deepgram", "dative"), "Deepgram'a")
        self.assertEqual(i18n.name("Deepgram", "accusative"), "Deepgram'ı")

    def test_no_case_asked_for(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.name("Claude"), "Claude")

    def test_an_unlisted_name_or_case_comes_back_unchanged(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.name("Ollama", "dative"), "Ollama")
        self.assertEqual(i18n.name("Claude", "ablative"), "Claude")


class Table(unittest.TestCase):
    """The Turkish table against the English strings it stands in for."""

    def test_every_translation_keeps_the_placeholders_of_its_source(self):
        for source, translated in i18n.TR.items():
            with self.subTest(source=source[:50]):
                self.assertEqual(
                    placeholders(source), placeholders(translated),
                    "the Turkish string does not take the same arguments",
                )

    def test_nothing_is_translated_to_an_empty_string(self):
        for source, translated in i18n.TR.items():
            with self.subTest(source=source[:50]):
                self.assertTrue(translated.strip())

    def test_every_translation_is_formattable(self):
        """Whatever the table holds, .format() must not blow up on it."""
        for source, translated in i18n.TR.items():
            names = placeholders(translated)
            if not names:
                continue
            with self.subTest(source=source[:50]):
                translated.format(**{key: "x" for key in names})

    def test_every_t_literal_is_translated_or_recorded(self):
        """The gap may not grow, and the record may not lie.

        This replaced a count-based ratchet (`assertLessEqual(len(missing),
        104)`) on 2026-09-12. A count cannot tell a new gap from an old one:
        swapping one untranslated string for another keeps the number and
        passes. It also never tightened, so a closed gap silently bought room
        for a new one, and it did not follow the `_t` alias, which hid two
        strings the sidebar shows on every page.

        So the exact set is recorded in `tests/i18n_untranslated.json` and both
        directions fail. Closing a gap is progress that has to be written down;
        opening one is the thing this exists to stop.
        """
        actual = untranslated_strings()
        recorded = recorded_gaps()

        opened = sorted(set(actual) - set(recorded))
        self.assertEqual([], opened, (
            "these strings reach t() with no Turkish entry and are not in "
            f"{GAPS_FILE.name}. Translate them in i18n.py, or — if the gap is "
            "genuinely accepted for now — record it with "
            "'python tools/i18n_gaps.py --write':\n  "
            + "\n  ".join(f"{key!r} at {', '.join(actual[key])}" for key in opened)))

        closed = sorted(set(recorded) - set(actual))
        self.assertEqual([], closed, (
            "these strings are recorded as untranslated but no longer are, so "
            "the record is holding room the gap does not need. Delete them with "
            f"'python tools/i18n_gaps.py --write':\n  " + "\n  ".join(repr(k) for k in closed)))

    def test_the_gap_record_lists_where_each_string_is_asked_for(self):
        """A record with no call site is a note, not a lead for whoever fixes it."""
        for key, sites in recorded_gaps().items():
            with self.subTest(string=key[:40]):
                self.assertTrue(sites, f"{key!r} is recorded without a location")
                for site in sites:
                    path, _, lineno = site.rpartition(":")
                    self.assertTrue((REPO / path).is_file(), f"{path} no longer exists")
                    self.assertTrue(lineno.isdigit(), f"{site!r} has no line number")


class VoiceReliabilityParity(DikteTest):
    """Changed recovery/capture copy must not fall through to English in TR."""

    SOURCES = (
        "Could not preserve recording safely",
        "Cannot start {activity} while the meeting microphone is active on this device. Finish the meeting or choose a shareable input.",
        "dictation",
        "agent",
    )

    def test_capture_recovery_strings_have_real_turkish_translations(self):
        i18n.set_language("tr")
        for source in self.SOURCES:
            with self.subTest(source=source):
                self.assertIn(source, i18n.TR)
                self.assertNotEqual(i18n.t(source, activity="dikte"), source)


if __name__ == "__main__":
    unittest.main()

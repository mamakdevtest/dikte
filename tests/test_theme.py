"""The colour theme's contract with the widgets: the sheet, once, and legible.

Two things are worth pinning here. The sheet is put on the application once and
not again for a theme that has not changed, because re-polishing every widget
costs most of a second once a window is up. And the palette is legible: contrast
is the one property of a colour theme that a later edit can quietly ruin for
everybody, and the reference this palette comes from was itself below the bar
(its helper-text grey measured 2.75:1).
"""

import re
from unittest import mock

from PyQt6.QtWidgets import QApplication

from tests.support import DikteTest
from ui import theme
from ui.tokens import (
    DARK, LIGHT, RETIRED_THEMES, THEMES, contrast_ratio, mix,
)

_app = QApplication.instance() or QApplication([])

# 4.5:1 is WCAG AA for body text. The tiers are held to it, not to a feeling.
AA = 4.5


class Apply(DikteTest):
    def setUp(self):
        super().setUp()
        self.addCleanup(theme.apply, theme.current())

    def test_the_application_holds_the_theme_s_own_sheet(self):
        theme.apply("light")
        self.assertEqual(_app.styleSheet(), theme.stylesheet("light"))

    def test_a_theme_change_reaches_the_application(self):
        theme.apply("light")
        theme.apply("dark")
        self.assertEqual(_app.styleSheet(), theme.stylesheet("dark"))

    def test_an_unchanged_theme_is_not_put_back_on_the_application(self):
        """Putting it back re-polishes every widget in the process, which is
        most of a second once a window is up, and it changes nothing."""
        real = _app.setStyleSheet
        with mock.patch.object(_app, "setStyleSheet", side_effect=real) as spy:
            theme.apply("light")
            theme.apply("light")
            self.assertEqual(spy.call_count, 1)
            theme.apply("dark")
            self.assertEqual(spy.call_count, 2)


class Names(DikteTest):
    """Which names are themes, and what an old one answers with."""

    def test_there_are_two_themes_and_they_are_light_and_dark(self):
        self.assertEqual(sorted(THEMES), ["dark", "light"])

    def test_a_real_theme_name_comes_back_unchanged(self):
        for name in ("light", "dark"):
            with self.subTest(name=name):
                self.assertEqual(theme.normalize(name), name)

    def test_a_retired_room_name_migrates_to_the_default(self):
        """Not a lie, a migration: until 2026-09-12 every name outside the six
        rooms was coerced to `blue`, so a config saying `light` silently became a
        dark room while the picker showed a choice nobody had made."""
        from ui.tokens import DEFAULT_THEME
        for name in RETIRED_THEMES:
            with self.subTest(name=name):
                self.assertEqual(theme.normalize(name), DEFAULT_THEME)

    def test_an_unknown_name_does_not_escape_the_theme_list(self):
        for name in ("", "chartreuse", "Dark", None):
            with self.subTest(name=name):
                self.assertIn(theme.normalize(name), THEMES)

    def test_every_theme_carries_the_same_keys(self):
        """QSS and paint code must never branch on which theme is in use."""
        self.assertEqual(set(LIGHT), set(DARK))

    def test_a_theme_knows_the_names_the_qss_engine_reads(self):
        required = {"canvas", "sidebar", "surface", "surface2", "field",
                    "border", "borderStrong", "fg", "fg2", "fg3",
                    "accent", "accentDeep", "sage", "sageDark",
                    "ok", "warn", "err", "info", "inkBtn", "onInk"}
        for name, tokens in sorted(THEMES.items()):
            with self.subTest(theme=name):
                self.assertEqual(set(), required - set(tokens))


class Legible(DikteTest):
    """WCAG AA, measured, on the background each colour is really drawn on."""

    TEXT_TIERS = ("fg", "fg2", "fg3")
    BACKGROUNDS = ("canvas", "sidebar", "surface")
    # The chips draw their colour as text on a tint of that same colour.
    CHIPS = {"ok": 0.12, "warn": 0.14, "err": 0.10, "info": 0.07}

    def test_every_text_tier_clears_aa_on_every_background(self):
        for name, tokens in sorted(THEMES.items()):
            for tier in self.TEXT_TIERS:
                for background in self.BACKGROUNDS:
                    with self.subTest(theme=name, tier=tier, on=background):
                        ratio = contrast_ratio(tokens[tier], tokens[background])
                        self.assertGreaterEqual(
                            round(ratio, 2), AA,
                            f"{name}: {tier} on {background} is {ratio:.2f}:1")

    def test_the_tiers_descend(self):
        """fg is the loudest, fg3 the quietest, and the order is visible."""
        for name, tokens in sorted(THEMES.items()):
            with self.subTest(theme=name):
                loud = contrast_ratio(tokens["fg"], tokens["canvas"])
                middle = contrast_ratio(tokens["fg2"], tokens["canvas"])
                quiet = contrast_ratio(tokens["fg3"], tokens["canvas"])
                self.assertGreater(loud, middle)
                self.assertGreater(middle, quiet)

    def test_status_colours_clear_aa_as_chip_text(self):
        for name, tokens in sorted(THEMES.items()):
            for key, share in self.CHIPS.items():
                with self.subTest(theme=name, chip=key):
                    tint = mix(tokens[key], tokens["surface"], share)
                    ratio = contrast_ratio(tokens[key], tint)
                    self.assertGreaterEqual(
                        round(ratio, 2), AA,
                        f"{name}: the {key} chip is {ratio:.2f}:1 on its own tint")

    def test_the_sage_link_clears_aa(self):
        for name, tokens in sorted(THEMES.items()):
            with self.subTest(theme=name):
                for background in self.BACKGROUNDS:
                    ratio = contrast_ratio(tokens["sageDark"], tokens[background])
                    self.assertGreaterEqual(round(ratio, 2), AA,
                                            f"{name}: sageDark on {background}")
                tint = mix(tokens["sage"], tokens["surface"], 0.30)
                self.assertGreaterEqual(
                    round(contrast_ratio(tokens["sageDark"], tint), 2), AA)

    def test_a_filled_button_can_be_read(self):
        """One solid fill carries text, and it is ink.

        Terracotta cannot do this job: the button text measures 3.5:1 on the
        light theme's accent and 2.6:1 on the dark one's, both under AA. It is
        the recording signal and nothing else — which is also what the design
        reference asks for ("ink charcoal primary button, NOT orange").
        """
        for name, tokens in sorted(THEMES.items()):
            with self.subTest(theme=name):
                backgrounds = {
                    "the button": tokens["inkBtn"],
                    "its hover": mix(tokens["inkBtn"], tokens["surface2"], 0.78),
                    "its pressed state": tokens["inkBtn"],
                }
                for label, background in backgrounds.items():
                    ratio = contrast_ratio(tokens["onInk"], background)
                    self.assertGreaterEqual(
                        round(ratio, 2), AA,
                        f"{name}: the text on {label} is {ratio:.2f}:1")

    def test_terracotta_cannot_carry_the_button_text(self):
        """The bright recording accent is a mark, never something you read on.

        This is the measurement behind the design decision, not a preference:
        the button text lands at 3.5:1 on the light theme's `accent` and 2.6:1
        on the dark one's. (`accentDeep` measures 4.72 and 4.61 — just over AA,
        which is why it was tempting, and still the wrong colour to read on:
        it is 11 px of contrast for a 13 px label.) Both stay what the design
        reference says they are for: recording.
        """
        for name, tokens in sorted(THEMES.items()):
            with self.subTest(theme=name):
                ratio = contrast_ratio(tokens["onInk"], tokens["accent"])
                self.assertLess(
                    ratio, AA,
                    f"{name}: the accent now carries the button text "
                    f"({ratio:.2f}:1), so this test and the decision behind it "
                    "are stale")

    def test_the_filled_button_is_ink_in_the_sheet(self):
        """The decision reaches the sheet, not just the palette."""
        for name in sorted(THEMES):
            tokens = THEMES[name]
            ink = tokens["inkBtn"]
            # The one fill, and the one lift it takes on hover. Anything else in
            # a primary rule is a colour from a different decision.
            allowed = {ink, mix(ink, tokens["surface2"], 0.78)}
            # Whitespace is collapsed first: a selector list wraps in the source,
            # so the selector and its background can share two lines.
            rules = [" ".join(rule.split())
                     for rule in theme.stylesheet(name).split("}")]
            fills = []
            for rule in rules:
                if 'variant="primary"' not in rule or "background" not in rule:
                    continue
                if ":disabled" in rule:
                    continue
                background = rule.split("background:", 1)[1].split(";", 1)[0].strip()
                fills.append(background)
            self.assertTrue(fills, f"{name}: the primary button has no rule")
            self.assertIn(ink, fills, f"{name}: the primary button is not filled with ink")
            for background in fills:
                with self.subTest(theme=name, background=background):
                    self.assertIn(background, allowed,
                                  "the primary button carries a colour that is "
                                  "not part of its own decision")

    def test_the_qss_source_carries_no_bare_colour(self):
        """Every colour in the sheet comes from the palette.

        A hardcoded one is how the tan chip ended up with dark brown text on a
        dark background, and how a removed error colour left `#ff6b6b` behind in
        an earlier pass. The check is on the engine's own source: a bare literal
        there is a colour that ignores the theme.
        """
        import pathlib
        source = (pathlib.Path(theme.__file__).resolve().parent / "qss.py")
        text = source.read_text(encoding="utf-8")
        stripped = "\n".join(line.split("#", 1)[0] if line.strip().startswith("#")
                            else line
                            for line in text.splitlines())
        bare = sorted(set(re.findall(r'"#([0-9A-Fa-f]{6})"', stripped)))
        self.assertEqual([], bare, (
            f"ui/qss.py has colours that do not come from the palette: {bare}"))


if __name__ == "__main__":
    import unittest
    unittest.main()

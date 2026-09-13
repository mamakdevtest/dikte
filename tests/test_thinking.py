"""The thinking panel: its activity cue, and the language it speaks.

U11 said the panel "has no activity indicator while its text says 'Cleaning up…'"
and that it does not look like it comes from the same product as the pill. The
second half was unprovable — the design reference is a settings reference and says
nothing about the indicator — but the first half was true and worse than reported:
the activity cue was a bare `QLabel` with a fixed size, repainted on every tick and
given nothing to draw.

Reading the file to check that also turned up something U11 did not mention: the
panel had no i18n at all. Its title and three of its buttons were Turkish string
literals, so the English interface showed "Dusunuyor…" with
"Duraklat / Durdur / Kapat" underneath it.
"""

import json

import i18n
from PyQt6.QtWidgets import QApplication

import config as cfg
from ui.thinking import Spinner, ThinkingPopup

from tests.support import DikteTest


class _WithQt(DikteTest):
    """A test that has a QApplication.

    `DikteTest` deliberately does not make one — it only owns the config, the data
    directory and the language — so every widget test brings its own. Without it
    the first QWidget aborts the process with a Qt qFatal, which is how this file
    first failed: `Fatal Python error: Aborted`, no traceback, core dumped.
    """

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])

    def speak(self, language):
        """Make the process speak `language` — and keep it that way.

        Setting the language is not enough on its own: showing the panel reads the
        config (`_reposition` builds a `Config`) and `Config.__init__` re-applies the
        *stored* language to the whole process, so a test that only calls
        `set_language` has it undone the moment the panel appears. Storing it too is
        what the running app ends up with, and it is what this asserts against.
        """
        cfg.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        cfg.CONFIG_FILE.write_text(json.dumps({"ui_language": language}))
        i18n.set_language(language)

    def fingerprint(self, widget, size=14):
        """What the widget actually paints.

        `QPixmap.cacheKey()` cannot answer this: it identifies the pixmap object, so
        two grabs of identical content still differ and two grabs of *changed*
        content can still match. Every pixel is the content.
        """
        widget.resize(size, size)
        image = widget.grab().toImage()
        return [image.pixel(x, y) for x in range(size) for y in range(size)]


class TheSpinnerTest(_WithQt):
    """The cue that the panel is still working."""

    def _drawn(self, widget, size=14):
        """How many pixels differ from the widget's own background."""
        widget.resize(size, size)
        image = widget.grab().toImage()
        background = image.pixelColor(0, 0)
        return sum(1 for x in range(size) for y in range(size)
                   if image.pixelColor(x, y) != background)

    def test_the_spinner_draws_something(self):
        """It was a QLabel: 14x14, repainted every tick, never painted."""
        spinner = Spinner()
        self.addCleanup(spinner.deleteLater)
        self.assertGreater(self._drawn(spinner), 0, "the spinner paints nothing")

    def test_the_spinner_turns(self):
        spinner = Spinner()
        self.addCleanup(spinner.deleteLater)
        before = self.fingerprint(spinner)
        spinner.advance(1.0)
        self.assertNotEqual(before, self.fingerprint(spinner),
                            "the cue does not move, so it does not say 'working'")

    def test_a_paused_spinner_holds_still(self):
        spinner = Spinner()
        self.addCleanup(spinner.deleteLater)
        spinner.set_paused(True)
        before = self.fingerprint(spinner)
        spinner.advance(5.0)
        self.assertEqual(before, self.fingerprint(spinner),
                         "a paused panel must not look busy")

    def test_the_panel_turns_its_spinner(self):
        popup = ThinkingPopup()
        self.addCleanup(popup.deleteLater)
        before = self.fingerprint(popup.spinner)
        popup._on_tick()
        self.assertNotEqual(before, self.fingerprint(popup.spinner))

    def test_pausing_the_panel_pauses_the_cue(self):
        popup = ThinkingPopup()
        self.addCleanup(popup.deleteLater)
        popup.set_paused(True)
        self.assertTrue(popup.spinner._paused)


class ThePanelIsTranslatedTest(_WithQt):
    """It had no i18n at all."""

    def _labels(self):
        popup = ThinkingPopup()
        self.addCleanup(popup.deleteLater)
        popup.show_thinking()
        return [popup.title.text(), popup.stage_lbl.text(),
                popup.pause_btn.text(), popup.stop_btn.text(),
                popup.close_btn.text()]

    def test_the_panel_speaks_the_chosen_language(self):
        """Every visible label has to change with the language.

        Compared per label rather than as one blob, so a single hardcoded string
        cannot hide behind its translated neighbours. A Turkish-character check
        would not have caught this one: the literals were ASCII-folded
        ("Dusunuyor…", "Duraklatildi").
        """
        self.speak("en")
        english = self._labels()
        self.speak("tr")
        turkish = self._labels()
        for index, name in enumerate(("title", "stage", "pause", "stop", "close")):
            with self.subTest(label=name):
                self.assertNotEqual(
                    english[index], turkish[index],
                    f"the {name} label is the same in both languages — "
                    f"it is a literal, not a t() call: {english[index]!r}")

    def test_the_paused_panel_is_translated_too(self):
        self.speak("en")
        popup = ThinkingPopup()
        self.addCleanup(popup.deleteLater)
        popup.set_paused(True)
        self.assertEqual("Paused", popup.title.text())
        self.assertEqual("Resume", popup.pause_btn.text())

    def test_the_default_stage_is_translated(self):
        self.speak("tr")
        popup = ThinkingPopup()
        self.addCleanup(popup.deleteLater)
        popup.show_thinking()
        self.assertEqual(i18n.t("Thinking…"), popup.stage_lbl.text())
        self.assertNotEqual("Thinking…", popup.stage_lbl.text())


class ThePanelDoesNotDecideTheLanguageTest(_WithQt):
    """N7: placing the panel read a *fresh* `Config`, and a fresh `Config` applies the saved
    language to the whole process — so a language the user had just picked in the settings
    window and not yet saved was put back to the stored one."""

    def test_placing_the_panel_does_not_overrule_an_unsaved_language(self):
        self.speak("en")                        # the settings file says English
        popup = ThinkingPopup(conf=self.config())
        self.addCleanup(popup.deleteLater)
        i18n.set_language("tr")                 # the user picks Turkish, and has not saved yet
        popup._reposition()                     # the panel is placed
        self.assertEqual("tr", i18n.language(),
                         "placing the panel put the stored language back")

    def test_a_fresh_config_is_what_makes_that_a_risk(self):
        """The mechanism behind the guard above, pinned.

        If reading a config ever stops applying the language, this test fails and the guard
        above becomes belt and braces — that is a fine thing to be told.
        """
        self.speak("en")
        i18n.set_language("tr")
        cfg.Config()
        self.assertEqual("en", i18n.language())

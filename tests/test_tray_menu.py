"""Tray menu contracts: hint painting, meeting metadata, title eliding."""

import unittest

import tests  # noqa: F401  (offscreen Qt + sandbox)
from tests.support import DikteTest

import dikte
import i18n


class MeetingMeta(DikteTest):
    """The right-aligned date/time the meetings submenu shows."""

    def test_a_full_timestamp_becomes_the_turkish_day_and_clock(self):
        self.assertEqual(dikte.meeting_meta("2026-08-30 20:12"), "30 Ağu · 20:12")

    def test_every_month_uses_its_own_abbreviation(self):
        stamps = [f"2026-{m:02d}-05 09:05" for m in range(1, 13)]
        metas = [dikte.meeting_meta(s) for s in stamps]
        months = [m.split()[1] for m in metas]
        self.assertEqual(months, ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
                                  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"])
        for meta in metas:
            self.assertTrue(meta.endswith("· 09:05"), meta)

    def test_anything_unparsable_is_empty_rather_than_a_lie(self):
        for bad in ("", "not a date", None, 5, "2026-08-30", "2026-13-99 25:61"):
            self.assertEqual(dikte.meeting_meta(bad), "")


class ElidedTitle(DikteTest):
    def test_a_long_title_is_cut_and_a_short_one_is_left_alone(self):
        long_text = "Türkiye Pazarlık Stratejisi Planlama Toplantısı ve Sonrası"
        cut = dikte.elide_title(long_text, 120)
        self.assertTrue(cut.endswith("…") or len(cut) < len(long_text))
        self.assertEqual(dikte.elide_title("Kısa", 120), "Kısa")
        self.assertEqual(dikte.elide_title("", 120), "")


class HintMenu(DikteTest):
    def test_the_menu_renders_with_hints_separators_and_hintless_rows(self):
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        menu = dikte.HintMenu()
        one = QAction("Kaydı başlat", menu)
        one.setProperty("shortcutHint", "Ctrl Space")
        menu.addAction(one)
        two = QAction("Çık", menu)
        two.setProperty("shortcutHint", "Alt F4")
        menu.addAction(two)
        menu.addSeparator()
        three = QAction("Toplantılar", menu)
        menu.addAction(three)

        menu.resize(menu.sizeHint())
        pixmap = menu.grab()
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 40)
        self.assertGreater(pixmap.height(), 40)


class TheAssistantInTheTray(DikteTest):
    """What the tray says while the assistant has the microphone.

    Both of these used to name a fixed assistant — "Dikte: recording for Claude",
    "Dikte: talking to Claude" — a couple of lines below a `display_name(self.conf)`
    that had already worked out the right one, so a Codex or a local model user was
    told the wrong program was listening. The Turkish entries had quietly dropped the
    name altogether, which is the tell: the name was never the translator's to drop.
    """

    def test_the_tooltip_names_the_assistant_you_configured(self):
        for agent in ("Claude", "Codex", "Antigravity", "qwen3:8b", "OpenCode Go"):
            with self.subTest(agent=agent):
                _icon, tip = dikte.ask_tray_state(dikte.RECORDING, agent)
                self.assertIn(agent, tip)
                self.assertNotIn("Claude", tip.replace(agent, ""),
                                 "a tooltip naming somebody else")

    def test_a_paused_assistant_says_paused(self):
        icon, tip = dikte.ask_tray_state(dikte.PAUSED, "Codex")
        self.assertEqual("media-record", icon)
        self.assertEqual(dikte.t("Dikte: paused"), tip)

    def test_a_working_assistant_wears_the_working_icon(self):
        icon, tip = dikte.ask_tray_state(dikte.BUSY, "Codex")
        self.assertEqual("view-refresh", icon)
        self.assertIn("Codex", tip)

    def test_recording_and_working_look_different(self):
        """One is a red record dot, the other a refresh — not the same cue twice."""
        self.assertNotEqual(dikte.ask_tray_state(dikte.RECORDING, "Codex")[0],
                            dikte.ask_tray_state(dikte.BUSY, "Codex")[0])

    def test_the_tooltips_are_translated(self):
        i18n.set_language("en")
        english = dikte.ask_tray_state(dikte.RECORDING, "Codex")[1]
        i18n.set_language("tr")
        turkish = dikte.ask_tray_state(dikte.RECORDING, "Codex")[1]
        self.assertNotEqual(english, turkish, "the tooltip is not translated")
        self.assertIn("Codex", turkish, "the name has to survive the translation")
        self.assertEqual("Dikte: duraklatıldı",
                         dikte.ask_tray_state(dikte.PAUSED, "Codex")[1])
        self.assertIn("konuşuyor", dikte.ask_tray_state(dikte.BUSY, "Codex")[1])


if __name__ == "__main__":
    unittest.main()

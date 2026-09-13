"""The wider live view popup: state, text, and the toggle."""

import unittest

from PyQt6.QtWidgets import QApplication, QToolButton

from tests.support import DikteTest
from ui.live_popup import HEIGHT, MIN_HEIGHT, WIDTH, LivePopup


def _long_text(lines=200):
    return "\n".join("line %d" % i for i in range(lines))


class LivePopupTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.popup = LivePopup()
        self.addCleanup(self.popup.hide)

    def test_set_text_replaces_and_holds(self):
        self.popup.set_text("merhaba dünya")
        self.assertEqual(self.popup.text.toPlainText(), "merhaba dünya")
        self.popup.set_text("merhaba dünya")  # same text: no rewrite
        self.assertEqual(self.popup.text.toPlainText(), "merhaba dünya")

    def test_toggle_shows_and_hides(self):
        self.assertFalse(self.popup.isVisible())
        self.popup.toggle()
        self.app.processEvents()
        self.assertTrue(self.popup.isVisible())
        self.popup.toggle()
        self.app.processEvents()
        self.assertFalse(self.popup.isVisible())

    def test_empty_text_is_tolerated(self):
        self.popup.set_text("")
        self.assertEqual(self.popup.text.toPlainText(), "")


class LivePopupExpandTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.popup = LivePopup()
        self.popup.show()
        self.app.processEvents()
        self.addCleanup(self.popup.hide)

    def _screen_area(self):
        screen = QApplication.screenAt(self.popup.pos()) \
            or QApplication.primaryScreen()
        return screen.availableGeometry()

    def test_arrow_button_toggles_expansion(self):
        button = self.popup.findChild(QToolButton)
        self.assertIsNotNone(button)
        self.assertEqual(button.objectName(), "live_popup_expand")
        # Enough words that the compact card cannot show them all: the question
        # this test asks is whether expanding reveals more, and with the card sized
        # to its text a short transcript has nothing more to reveal.
        self.popup.set_text(_long_text(120))
        self.app.processEvents()
        compact = self.popup.height()
        self.assertEqual(self.popup.width(), WIDTH)
        self.assertLessEqual(compact, HEIGHT)
        self.assertTrue(button.isEnabled())
        button.click()
        self.app.processEvents()
        self.assertGreater(self.popup.height(), compact)
        button.click()
        self.app.processEvents()
        self.assertEqual((self.popup.width(), self.popup.height()), (WIDTH, compact))

    def test_expanded_card_stays_on_screen(self):
        self.popup.set_expanded(True)
        self.app.processEvents()
        area = self._screen_area()
        g = self.popup.geometry()
        self.assertLessEqual(self.popup.height(),
                             int(area.height() * 0.6) + 1)
        self.assertGreaterEqual(g.top(), area.top())
        self.assertLessEqual(g.bottom(), area.bottom())
        self.assertGreaterEqual(g.left(), area.left())
        self.assertLessEqual(g.right(), area.right())

    def test_expand_twice_is_a_noop(self):
        self.popup.set_expanded(True)
        grown = (self.popup.width(), self.popup.height())
        self.popup.set_expanded(True)
        self.assertEqual((self.popup.width(), self.popup.height()), grown)
        self.popup.set_expanded(False)
        collapsed_pos = self.popup.pos()
        self.popup.set_expanded(True)
        self.popup.set_expanded(False)
        self.assertEqual(self.popup.pos(), collapsed_pos)


class LivePopupFollowTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.popup = LivePopup()
        self.popup.set_expanded(True)
        self.popup.show()
        self.app.processEvents()
        self.addCleanup(self.popup.hide)
        self.bar = self.popup.text.verticalScrollBar()

    def test_following_pins_to_bottom(self):
        self.popup.set_text(_long_text())
        self.app.processEvents()
        self.assertGreater(self.bar.maximum(), 0)
        self.assertEqual(self.bar.value(), self.bar.maximum())

    def test_scrolled_up_view_is_not_yanked_down(self):
        self.popup.set_text(_long_text())
        self.app.processEvents()
        self.bar.setValue(0)
        self.popup.set_text(_long_text() + "\nson satır")
        self.app.processEvents()
        self.assertEqual(self.bar.value(), 0)

    def test_following_resumes_when_back_at_bottom(self):
        self.popup.set_text(_long_text())
        self.app.processEvents()
        self.bar.setValue(0)
        self.popup.set_text(_long_text() + "\nara satır")
        self.bar.setValue(self.bar.maximum())
        self.popup.set_text(_long_text(300) + "\nson satır")
        self.app.processEvents()
        self.assertEqual(self.bar.value(), self.bar.maximum())

    def test_replacement_preserves_scroll_position_when_not_following(self):
        self.popup.set_text(_long_text(300))
        self.app.processEvents()
        held = min(self.bar.maximum() // 2, self.bar.maximum())
        self.bar.setValue(held)
        self.popup.set_text(_long_text(400))
        self.app.processEvents()
        self.assertEqual(self.bar.value(), held)


class LivePopupSizingTest(DikteTest):
    """The card is as tall as its words (U6), and it has an empty state.

    U6 described a fixed ~500x520 panel with three lines of text leaving two
    thirds of it dead, and said there was no empty state. The first half was true
    and is fixed here; the second half was stale — the text area has carried a
    placeholder all along, and the last test in this class pins that so the claim
    cannot come back.
    """

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.popup = LivePopup()
        self.popup.show()
        self.app.processEvents()
        self.addCleanup(self.popup.hide)

    def test_three_lines_do_not_fill_a_whole_card(self):
        self.popup.set_text("bir\niki\nüç")
        self.app.processEvents()
        self.assertLess(self.popup.height(), HEIGHT,
                        "three lines still draw a full-height card")
        self.assertGreaterEqual(self.popup.height(), MIN_HEIGHT)

    def test_the_card_grows_with_the_text(self):
        self.popup.set_text("bir")
        self.app.processEvents()
        short = self.popup.height()
        self.popup.set_text(_long_text(30))
        self.app.processEvents()
        self.assertGreater(self.popup.height(), short)

    def test_the_compact_card_stops_at_the_cap_and_scrolls_instead(self):
        self.popup.set_text(_long_text(400))
        self.app.processEvents()
        self.assertEqual(self.popup.height(), HEIGHT)
        self.assertGreater(self.popup.text.verticalScrollBar().maximum(), 0)

    def test_the_arrow_is_offered_only_when_there_is_more_to_show(self):
        """A control that does nothing when pressed is worse than an absent one."""
        button = self.popup.findChild(QToolButton)
        self.popup.set_text("bir\niki")
        self.app.processEvents()
        self.assertFalse(button.isEnabled())
        self.popup.set_text(_long_text(200))
        self.app.processEvents()
        self.assertTrue(button.isEnabled())

    def test_the_card_shows_all_of_its_text_until_it_hits_the_cap(self):
        """A card with room to grow must not scroll.

        It did. The height was counted from the layout margins alone, and the
        stylesheet's 8px of padding on text areas is invisible to that count, so
        every card came up about a line short and scrolled its last line out of
        sight — the exact "three lines in too much card" complaint, inverted.
        """
        for lines in (1, 3, 6):
            with self.subTest(lines=lines):
                self.popup.set_text(_long_text(lines))
                self.app.processEvents()
                scroll = self.popup.text.verticalScrollBar().maximum()
                self.assertLess(self.popup.height(), HEIGHT, "the card is capped here")
                self.assertEqual(0, scroll, f"{lines} lines do not fit the card")

    def test_an_empty_card_still_has_something_to_say(self):
        """U6 said this was missing. It was not."""
        self.popup.set_text("")
        self.app.processEvents()
        self.assertTrue(self.popup.text.placeholderText(),
                        "an empty live card shows nothing at all")
        self.assertGreaterEqual(self.popup.height(), MIN_HEIGHT)

    def test_the_disabled_arrow_is_not_drawn_in_the_enabled_colour(self):
        """A control that is off has to look off.

        The disabled colour has to travel in the arrow's own stylesheet. It was set
        on the widget's palette first, which does nothing here: with the application
        sheet in play Qt resolves a QToolButton's text through QStyleSheetStyle, and
        the disabled arrow kept the enabled colour.
        """
        running = self.popup._arrow_fg.name()
        stopped = self.popup._arrow_fg3.name()
        self.assertNotEqual(running, stopped)
        sheet = self.popup.arrow.styleSheet()
        self.assertIn(":disabled", sheet)
        self.assertIn(stopped, sheet, "the disabled colour never reaches the widget")


if __name__ == "__main__":
    unittest.main()

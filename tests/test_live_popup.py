"""The wider live view popup: state, text, and the toggle."""

import unittest

from PyQt6.QtWidgets import QApplication, QToolButton

from tests.support import DikteTest
from ui.live_popup import HEIGHT, WIDTH, LivePopup


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
        compact = self.popup.height()
        self.assertEqual((self.popup.width(), compact), (WIDTH, HEIGHT))
        button.click()
        self.app.processEvents()
        self.assertGreater(self.popup.height(), compact)
        self.assertGreaterEqual(self.popup.height(), int(HEIGHT * 1.5))
        self.assertLessEqual(self.popup.height(), int(HEIGHT * 2))
        button.click()
        self.app.processEvents()
        self.assertEqual((self.popup.width(), self.popup.height()),
                         (WIDTH, HEIGHT))

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
        pos = self.popup.pos()
        self.popup.set_expanded(False)
        self.popup.set_expanded(False)
        self.assertEqual(self.popup.pos(), pos)


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


if __name__ == "__main__":
    unittest.main()

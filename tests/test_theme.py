"""The colour theme's contract with the widgets: the sheet, once."""

from unittest import mock

from PyQt6.QtWidgets import QApplication

from tests.support import DikteTest
from ui import theme

_app = QApplication.instance() or QApplication([])


class Apply(DikteTest):
    def setUp(self):
        super().setUp()
        self.addCleanup(theme.apply, theme.current())

    def test_the_application_holds_the_theme_s_own_sheet(self):
        theme.apply("green")
        self.assertEqual(_app.styleSheet(), theme.stylesheet("green"))

    def test_a_theme_change_reaches_the_application(self):
        theme.apply("green")
        theme.apply("violet")
        self.assertEqual(_app.styleSheet(), theme.stylesheet("violet"))

    def test_an_unchanged_theme_is_not_put_back_on_the_application(self):
        """Putting it back re-polishes every widget in the process, which is
        most of a second once a window is up, and it changes nothing."""
        real = _app.setStyleSheet
        with mock.patch.object(_app, "setStyleSheet", side_effect=real) as spy:
            theme.apply("green")
            theme.apply("green")
            self.assertEqual(spy.call_count, 1)
            theme.apply("violet")
            self.assertEqual(spy.call_count, 2)


if __name__ == "__main__":
    import unittest
    unittest.main()

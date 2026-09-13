"""What a settings page shows when it has nothing to show.

U4 called the History page's recovery card "a large empty box" and said the
Indicator page "never centres its empty state". Both held, and the first was worse
than reported: the card was *always* there, holding an empty list box and a Retry
button with nothing to retry, in the best space on the page.

`_load_voice_jobs` is exercised unbound against the three things it touches, the
way `tests/test_minutes_ui.py` does it: everything it does is read the jobs and
toggle two widgets, and building the whole settings window here would only re-test
the scaffolding `tests/test_ui.py` already covers.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from PyQt6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

import paste
import settings_ui
import voice_jobs
from tests.support import DikteTest
from ui.pages import overlay as indicator_page


class TheRecoveryCard(DikteTest):
    """History's "Failed but recoverable", which is a claim, not a fixture."""

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])

    def window(self, group_shown=False):
        group = QPushButton()
        group.setVisible(group_shown)
        return SimpleNamespace(
            voice_jobs_list=QListWidget(),
            voice_jobs_retry_btn=QPushButton(),
            _voice_jobs_group=group,
        )

    def load(self, window):
        settings_ui.SettingsWindow._load_voice_jobs(window)
        return window

    @staticmethod
    def a_retryable_job(**overrides):
        job = {
            "id": "job-1",
            "ts": "2026-08-21 12:06:00",
            "kind": voice_jobs.KIND_DICTATION,
            "status": voice_jobs.STATUS_FAILED_RETRYABLE,
            "error_stage": "cleanup",
            "error_message": "the cleanup provider refused the request",
        }
        job.update(overrides)
        voice_jobs.save_voice_job(job)

    def test_the_card_is_hidden_when_there_is_nothing_to_recover(self):
        """It used to sit there empty, with a live-looking Retry button.

        `isHidden` rather than `isVisible`: the widget has no parent here and was
        never shown, so `isVisible()` is False either way and would pass this test
        without the fix.
        """
        window = self.load(self.window(group_shown=True))
        self.assertTrue(window._voice_jobs_group.isHidden(),
                        "the card is on screen with nothing in it")
        self.assertFalse(window.voice_jobs_retry_btn.isEnabled())
        self.assertEqual(0, window.voice_jobs_list.count())

    def test_the_card_appears_when_there_is_something_to_recover(self):
        self.a_retryable_job()
        window = self.load(self.window())
        self.assertFalse(window._voice_jobs_group.isHidden())
        self.assertTrue(window.voice_jobs_retry_btn.isEnabled())
        self.assertEqual(1, window.voice_jobs_list.count())
        self.assertIn("cleanup", window.voice_jobs_list.item(0).text())

    def test_a_job_that_cannot_be_retried_does_not_raise_the_card(self):
        """Only retryable jobs count — a finished one is not a recovery offer."""
        self.a_retryable_job(id="job-2", status=voice_jobs.STATUS_COMPLETED)
        window = self.load(self.window(group_shown=True))
        self.assertTrue(window._voice_jobs_group.isHidden())
        self.assertEqual(0, window.voice_jobs_list.count())


class TheIndicatorPage(DikteTest):
    """A page whose entire content is one empty state.

    `EmptyState` centres its own contents, but nothing centred `EmptyState`: the
    page put it under the title and then added a stretch, which pushed it up and
    left the void underneath.
    """

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])

    def body(self):
        # build() never touches `window`; it only fills a page column. `scrolled()`
        # wraps that column in a scroll area, so the layout to inspect is the
        # inner widget's.
        area = indicator_page.build(SimpleNamespace())
        self.addCleanup(area.deleteLater)
        return area.widget()

    def test_the_empty_state_is_between_two_stretches(self):
        layout = self.body().layout()
        stretches = [i for i in range(layout.count())
                     if layout.itemAt(i).spacerItem() is not None]
        widget_at = [i for i in range(layout.count())
                     if layout.itemAt(i).widget() is not None
                     and type(layout.itemAt(i).widget()).__name__ == "EmptyState"]
        self.assertEqual(1, len(widget_at), "the empty state is not on the page")
        self.assertEqual(2, len(stretches),
                         "the empty state must have slack above and below, or it "
                         "is pushed to one end of the page")
        self.assertLess(stretches[0], widget_at[0])
        self.assertGreater(stretches[1], widget_at[0])

    def test_the_page_still_says_where_the_indicator_lives(self):
        """Centring it must not turn it into decoration."""
        labels = [w.text() for w in self.body().findChildren(QLabel)]
        joined = " ".join(labels)
        self.assertIn("No overlay preview", joined)
        self.assertIn("appears on its own while recording", joined)

    def test_a_session_that_cannot_place_the_indicator_is_told_so(self):
        """The page says there is nothing to configure here (X2).

        On a Wayland session with no XWayland there is something it cannot do — the
        indicator is drawn wherever the compositor likes — and this page is where
        the corner is chosen, so it is the one place that can say so.
        """
        with mock.patch.object(paste, "indicator_platform",
                               return_value=paste.UNPLACED):
            labels = " ".join(w.text() for w in self.body().findChildren(QLabel))
        self.assertIn("no XWayland", labels)

    def test_a_session_that_can_place_it_hears_nothing_about_xwayland(self):
        with mock.patch.object(paste, "indicator_platform", return_value=paste.XCB):
            labels = " ".join(w.text() for w in self.body().findChildren(QLabel))
        self.assertNotIn("XWayland", labels)


if __name__ == "__main__":
    unittest.main()

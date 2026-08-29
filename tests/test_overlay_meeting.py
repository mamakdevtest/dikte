"""The meeting recording card: status, legend, silence warning, collapse.

Offscreen Qt; what is asserted is state and geometry, not pixels.
"""

import unittest
from unittest import mock

from PyQt6.QtWidgets import QApplication

import dikte
import overlay
from overlay import Overlay
from tests.support import DikteTest


def _app():
    return QApplication.instance() or QApplication([])


class MeetingRemoteSilent(unittest.TestCase):
    """The decision behind the card's warning line."""

    def test_a_fresh_recording_says_nothing(self):
        self.assertFalse(dikte.meeting_remote_silent(5.0, 5.0))

    def test_a_few_quiet_seconds_are_normal(self):
        self.assertFalse(dikte.meeting_remote_silent(60.0, 4.0))

    def test_long_silence_deep_into_a_recording_warns(self):
        self.assertTrue(dikte.meeting_remote_silent(60.0, 12.0))

    def test_recent_sound_overrides_a_long_recording(self):
        self.assertFalse(dikte.meeting_remote_silent(600.0, 10.0))

    def test_never_heard_warns_once_the_window_passes(self):
        # since-sound grows with the recording when nothing ever arrived
        self.assertFalse(dikte.meeting_remote_silent(12.0, 12.0))
        self.assertTrue(dikte.meeting_remote_silent(16.0, 16.0))


class MeetingMicSilent(unittest.TestCase):
    """The decision behind the card's microphone warning line."""

    def test_a_fresh_recording_says_nothing(self):
        self.assertFalse(dikte.meeting_mic_silent(5.0, 0))

    def test_bytes_arriving_means_the_device_is_alive(self):
        self.assertFalse(dikte.meeting_mic_silent(60.0, 32768))

    def test_nothing_arriving_past_the_grace_warns(self):
        self.assertFalse(dikte.meeting_mic_silent(10.0, 0))
        self.assertTrue(dikte.meeting_mic_silent(11.0, 0))


class MeetingCard(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = _app()
        self.overlay = Overlay("bottom-left", interactive_live=True)
        self.addCleanup(self.overlay.dismiss)

    def test_show_meeting_resets_card_state(self):
        self.overlay.show_meeting()
        self.overlay.set_meeting_warning(True)
        self.overlay.set_meeting_collapsed(True)
        self.overlay.show_meeting()
        self.assertEqual(self.overlay.state, "meeting")
        self.assertFalse(self.overlay.meeting_warning)
        self.assertFalse(self.overlay.meeting_collapsed)
        self.overlay.dismiss()

    def test_levels_feed_both_channels(self):
        self.overlay.show_meeting()
        self.overlay.push_levels(0.5, 0.25)
        # display levels lag through the waveform's smoothing, so the raw
        # per-channel history is what says who heard what: (t, level, shown)
        self.assertEqual(self.overlay._wave.history[-1][1], 0.5)
        self.assertEqual(self.overlay._wave2.history[-1][1], 0.25)
        self.overlay.dismiss()

    def test_warning_toggles_and_resets(self):
        self.overlay.show_meeting()
        self.overlay.set_meeting_warning(True)
        self.assertTrue(self.overlay.meeting_warning)
        self.app.processEvents()
        self.overlay.set_meeting_warning(False)
        self.assertFalse(self.overlay.meeting_warning)
        self.overlay.dismiss()

    def test_the_mic_warning_toggles_and_resets(self):
        self.overlay.show_meeting()
        self.overlay.set_meeting_warning(False, mic=True)
        self.assertTrue(self.overlay.meeting_mic_warning)
        self.app.processEvents()
        self.overlay.set_meeting_warning(False, mic=False)
        self.assertFalse(self.overlay.meeting_mic_warning)
        self.overlay.dismiss()

    def test_labeled_lines_grow_the_expanded_panel(self):
        self.overlay.show_meeting()
        self.overlay.set_live_expanded(True)
        self.overlay.set_live_lines(
            [("Ben", "Merhaba, nasılsın?", "mine"),
             ("Karşı taraf", "İyiyim, sen nasılsın?", "theirs")])
        short = self.overlay._live_height()
        self.overlay.set_live_lines(
            [("Ben", "satır %d" % i, "mine") for i in range(60)])
        tall = self.overlay._live_height()
        self.assertGreater(tall, short)
        self.assertLessEqual(tall, overlay._LIVE_MAX_H)
        self.assertEqual(self.overlay.live_lines[-1][0], "Ben")
        self.overlay.dismiss()

    def test_the_collapsed_panel_stays_one_line_tall(self):
        self.overlay.show_meeting()
        self.overlay.set_live_expanded(False)
        self.overlay.set_live_lines(
            [("Ben", "satır %d" % i, "mine") for i in range(20)])
        self.assertEqual(self.overlay._live_height(),
                         overlay._LIVE_COLLAPSED_H)
        self.overlay.dismiss()

    def test_a_push_slides_the_waveform_in_over_frames(self):
        self.overlay.show_meeting()
        self.overlay.push_levels(0.5, 0.25)
        self.assertGreater(self.overlay._wave.scroll, 0.99)
        for _ in range(6):
            self.overlay._wave.advance()
        self.assertEqual(self.overlay._wave.scroll, 0.0)
        self.overlay.dismiss()

    def test_warning_is_ignored_outside_meetings(self):
        self.overlay.state = "recording"
        self.overlay.set_meeting_warning(True)
        self.assertFalse(self.overlay.meeting_warning)

    def test_click_collapses_to_the_compact_card(self):
        self.overlay.show_meeting()
        self.app.processEvents()
        wide = self.overlay.width()
        self.overlay.toggle_meeting_collapsed()
        self.app.processEvents()
        self.assertTrue(self.overlay.meeting_collapsed)
        self.assertLess(self.overlay.width(), wide)
        self.overlay.toggle_meeting_collapsed()
        self.app.processEvents()
        self.assertFalse(self.overlay.meeting_collapsed)
        self.assertEqual(self.overlay.width(), wide)
        self.overlay.dismiss()

    def test_resize_keeps_the_footer_out_of_the_compact_card(self):
        self.overlay.show_meeting()
        self.app.processEvents()
        expanded = self.overlay.height()
        self.overlay.set_meeting_collapsed(True)
        self.app.processEvents()
        self.assertLess(self.overlay.height(), expanded)
        self.overlay.dismiss()


if __name__ == "__main__":
    unittest.main()

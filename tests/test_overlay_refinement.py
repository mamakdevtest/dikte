"""Deterministic contracts for the compact recording overlay pass."""

import unittest

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication

import overlay as overlay_module
from tests.support import DikteTest


_app = QApplication.instance() or QApplication([])


class OverlayRefinement(DikteTest):
    def overlay(self, **kwargs):
        widget = overlay_module.Overlay(interactive_live=True, **kwargs)
        self.addCleanup(widget.deleteLater)
        self.addCleanup(widget.close)
        return widget

    def settle_reveal(self, widget):
        widget._reveal_t0 = 0.0
        widget._reveal_progress = 1.0
        widget._sync_animation_timer()

    def test_recording_scheduler_is_bounded_and_pause_stops_it(self):
        widget = self.overlay()
        widget.show_recording()
        self.assertTrue(widget._anim.isActive())
        self.assertGreaterEqual(widget._anim.interval(), 22)
        self.assertLessEqual(widget._anim.interval(), 33)

        widget.show_paused()
        self.settle_reveal(widget)
        self.assertFalse(widget._anim.isActive())

    def test_non_live_states_do_not_keep_the_visual_scheduler_alive(self):
        widget = self.overlay()
        widget.show_busy("Transcribing…")
        self.assertTrue(widget._anim.isActive())
        widget.show_done("Pasted")
        self.assertFalse(widget._anim.isActive())

    def test_waveform_geometry_is_cached_and_uses_a_flow_bar_count(self):
        widget = self.overlay()
        widget.show_recording()
        first = widget._layout()
        self.assertGreaterEqual(len(first["bars"]), 28)
        self.assertLessEqual(len(first["bars"]), 36)
        self.assertTrue(all(isinstance(rect, QRectF) for rect in first["bars"]))

        widget.resize(widget.width() + 18, widget.height())
        self.assertIsNone(widget._layout_cache)
        second = widget._layout()
        self.assertNotEqual(first["bars"][-1].right(), second["bars"][-1].right())

    def test_recording_pill_is_wide_and_uses_a_larger_action_target(self):
        widget = self.overlay()
        widget.show_recording()

        action = widget._pause_button_rect()

        self.assertGreaterEqual(widget.width(), 500)
        self.assertGreaterEqual(widget.height(), 68)
        self.assertGreaterEqual(action.width(), 46)
        self.assertLessEqual(action.width(), 50)

    def test_new_audio_is_at_the_right_edge_of_the_flowing_waveform(self):
        widget = self.overlay()
        widget.show_recording()
        self.settle_reveal(widget)

        for _ in range(overlay_module.BARS - 1):
            widget.push_level(0.05)
            widget._tick()
        widget.push_level(0.88)
        for _ in range(12):
            widget._tick()

        levels = widget._wave.get_display_levels()
        self.assertGreater(levels[-1], levels[0] + 0.08)
        self.assertGreater(max(levels), overlay_module._BASELINE)

    def test_waveform_advances_between_audio_events(self):
        widget = self.overlay()
        widget.show_recording()
        self.settle_reveal(widget)

        widget.push_level(0.82)
        before_frame = widget._wave.get_smoothed()
        widget._tick()

        self.assertGreater(widget._wave.get_smoothed(), before_frame)
        self.assertLess(widget._wave.get_smoothed(), overlay_module._gate(0.82))

    def test_pause_and_resume_share_a_fixed_hit_rect(self):
        widget = self.overlay()
        widget.show_recording()
        recording_rect = widget._pause_button_rect()
        widget.show_paused()
        paused_rect = widget._pause_button_rect()

        self.assertEqual(recording_rect, paused_rect)
        self.assertGreaterEqual(recording_rect.width(), 46)
        self.assertLessEqual(recording_rect.width(), 50)

    def test_timer_text_is_cached_until_the_displayed_second_changes(self):
        widget = self.overlay()
        widget.show_recording()
        widget.set_seconds(3.2)
        first = widget._timer_text
        widget.set_seconds(3.8)
        self.assertIs(widget._timer_text, first)
        widget.set_seconds(4.0)
        self.assertNotEqual(widget._timer_text, first)

    def test_resume_keeps_timer_and_completed_reveal(self):
        widget = self.overlay()
        widget.show_recording()
        widget.set_seconds(14)
        widget._reveal_t0 = 0.0
        widget._reveal_progress = 1.0
        widget.show_paused()

        widget.show_resumed()

        self.assertEqual(widget.state, "recording")
        self.assertEqual(widget._timer_text, "0:14")
        self.assertEqual(widget._reveal_progress, 1.0)


if __name__ == "__main__":
    unittest.main()

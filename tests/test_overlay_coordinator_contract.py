"""Activity-stack contracts that must survive independent overlay lifecycles."""

import unittest
from unittest import mock

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

import dikte
import overlay as overlay_module
from tests.support import DikteTest
from ui import overlay_coordinator as coordinator
from ui.live_popup import LivePopup
from ui.overlay_coordinator import Activity, OverlayCoordinator
from ui.result_overlay import ResultOverlay


_app = QApplication.instance() or QApplication([])


class _OverlayStub:
    """A geometry-only overlay; no pixels or window manager are involved."""

    def __init__(self, width=320, height=72):
        self._width = width
        self._height = height
        self.moves = []
        self.below = None
        self._stacked = False

    def width(self):
        return self._width

    def height(self):
        return self._height

    def move(self, x, y):
        self.moves.append((x, y))


class TheFallbackSlot(unittest.TestCase):
    """An activity with no widget, which the registry documents as optional (R1).

    The app always registers a widget, so this path had never been run — which is
    how `height()` kept a branch that returned the same number for collapsed and
    expanded while its comment claimed the collapsed one was shorter.
    """

    def activity(self, ident, order, **kwargs):
        return Activity(id=ident, kind=ident, created_order=order,
                        state="recording", **kwargs)

    def test_a_collapsed_slot_is_shorter_than_an_expanded_one(self):
        self.assertLess(self.activity("a", 0, collapsed=True).height(),
                        self.activity("b", 1).height())

    def test_the_fallbacks_are_the_live_overlays_own_heights(self):
        """A widget-less stack that disagreed with a real one would misplace the
        next card, so these are the overlay's numbers rather than new ones."""
        self.assertEqual(overlay_module._LIVE_EXPANDED_H,
                         coordinator.FALLBACK_HEIGHT)
        self.assertEqual(overlay_module._LIVE_COLLAPSED_H,
                         coordinator.FALLBACK_COLLAPSED_HEIGHT)

    def test_a_widgetless_neighbour_still_takes_its_slot(self):
        """Compared as a difference, so the screen it lands on does not matter."""
        alone = _OverlayStub()
        first = OverlayCoordinator("bottom-left")
        first.register(self.activity("a", 0, widget=alone))
        y_alone = alone.moves[-1][1]

        with_neighbour = _OverlayStub()
        second = OverlayCoordinator("bottom-left")
        second.register(self.activity("a", 0, widget=with_neighbour))
        second.register(self.activity("b", 1))  # no widget at all
        y_with_neighbour = with_neighbour.moves[-1][1]

        self.assertEqual(int(coordinator.FALLBACK_HEIGHT + second.gap),
                         y_alone - y_with_neighbour)

    def test_collapsing_a_widgetless_neighbour_frees_the_difference(self):
        expanded = _OverlayStub()
        first = OverlayCoordinator("bottom-left")
        first.register(self.activity("a", 0, widget=expanded))
        first.register(self.activity("b", 1))
        y_expanded = expanded.moves[-1][1]

        collapsed = _OverlayStub()
        second = OverlayCoordinator("bottom-left")
        second.register(self.activity("a", 0, widget=collapsed))
        second.register(self.activity("b", 1, collapsed=True))
        y_collapsed = collapsed.moves[-1][1]

        self.assertEqual(int(coordinator.FALLBACK_HEIGHT
                             - coordinator.FALLBACK_COLLAPSED_HEIGHT),
                         y_collapsed - y_expanded,
                         "a collapsed slot must actually take less room")

    def test_a_widget_that_cannot_be_measured_falls_back_instead_of_raising(self):
        class Deleted:
            """What Qt gives you after the C++ object is gone."""

            def height(self):
                raise RuntimeError("wrapped C/C++ object of type Overlay deleted")

            def width(self):
                raise RuntimeError("wrapped C/C++ object of type Overlay deleted")

        act = self.activity("a", 0, widget=Deleted())
        self.assertEqual(coordinator.FALLBACK_HEIGHT, act.height())
        self.assertEqual(coordinator.FALLBACK_WIDTH, act.width())


class DynamicActivityStack(unittest.TestCase):
    def activity(self, ident, order, widget):
        return Activity(id=ident, kind=ident, created_order=order,
                        state="recording", widget=widget)

    def test_register_reflows_existing_and_new_activity_without_a_second_call(self):
        coordinator = OverlayCoordinator("bottom-left")
        meeting = _OverlayStub()
        dictation = _OverlayStub()

        coordinator.register(self.activity("meeting-1", 0, meeting))
        coordinator.register(self.activity("dictation-2", 1, dictation))

        # Registration itself is the lifecycle event. A caller must not have
        # to remember a second geometry call that could leave an active card
        # hidden or overlapping while another voice action starts.
        self.assertTrue(meeting.moves)
        self.assertTrue(dictation.moves)
        self.assertLess(meeting.moves[-1][1], dictation.moves[-1][1])
        self.assertEqual(
            [item.id for item in coordinator.ordered()],
            ["meeting-1", "dictation-2"],
        )

    def test_removing_middle_activity_immediately_closes_the_gap(self):
        coordinator = OverlayCoordinator("bottom-left")
        meeting, dictation, agent = (_OverlayStub(), _OverlayStub(), _OverlayStub())
        for order, ident, widget in (
            (0, "meeting-1", meeting),
            (1, "dictation-2", dictation),
            (2, "agent-3", agent),
        ):
            coordinator.register(self.activity(ident, order, widget))
        coordinator.recompute_geometry()
        before_meeting = meeting.moves[-1]
        before_agent = agent.moves[-1]

        coordinator.remove("dictation-2")

        self.assertEqual(
            [item.id for item in coordinator.ordered()], ["meeting-1", "agent-3"]
        )
        # Bottom-corner stacks pin the newest card to the corner.  Removing a
        # middle card therefore moves the older/top card down and closes the
        # gap above the newest card; it must not move the newer card upward.
        self.assertGreater(meeting.moves[-1][1], before_meeting[1])
        self.assertEqual(agent.moves[-1][1], before_agent[1])
        self.assertEqual(
            meeting.moves[-1][1] + meeting.height() + coordinator.gap,
            agent.moves[-1][1],
        )
        # Managed cards are positioned by the coordinator alone.  Leaving a
        # legacy `below` link here lets a widget re-position itself later and
        # overwrite the activity stack's independent geometry.
        self.assertIsNone(meeting.below)
        self.assertIsNone(agent.below)


class ManagedOverlayGeometry(unittest.TestCase):
    @staticmethod
    def activity(ident, order, widget):
        return Activity(id=ident, kind=ident, created_order=order,
                        state="recording", widget=widget)

    def setUp(self):
        self.meeting = overlay_module.Overlay("bottom-left", interactive_live=True)
        self.dictation = overlay_module.Overlay("bottom-left", interactive_live=True)
        self.addCleanup(self.meeting.close)
        self.addCleanup(self.dictation.close)
        self.addCleanup(self.meeting.deleteLater)
        self.addCleanup(self.dictation.deleteLater)

    def test_expanding_first_managed_card_preserves_coordinator_gap(self):
        self.meeting.show_meeting()
        self.dictation.show_recording()
        coordinator = OverlayCoordinator("bottom-left")
        coordinator.register(self.activity("meeting-1", 0, self.meeting))
        coordinator.register(self.activity("dictation-2", 1, self.dictation))
        self.meeting.set_live_transcript(" ".join(["meeting"] * 80))

        self.meeting.set_live_expanded(True)

        # The coordinator, not a widget's historic `below` relationship,
        # owns every managed card's position after a content-driven resize.
        self.assertAlmostEqual(
            self.meeting.y() + self.meeting.height() + coordinator.gap,
            self.dictation.y(),
            delta=1,
        )
        self.assertIsNone(self.dictation.below)


class ManagedDetailCards(unittest.TestCase):
    @staticmethod
    def activity(ident, order, widget):
        return Activity(id=ident, kind=ident, created_order=order,
                        state="recording", widget=widget)

    def setUp(self):
        self.meeting = overlay_module.Overlay("bottom-left", interactive_live=True)
        self.meeting.show_meeting()
        self.addCleanup(self.meeting.close)
        self.addCleanup(self.meeting.deleteLater)

    def coordinator_with(self, ident, detail):
        coordinator = OverlayCoordinator("bottom-left")
        coordinator.register(self.activity("meeting-1", 0, self.meeting))
        coordinator.register(self.activity(ident, 1, detail))
        return coordinator

    def assert_contiguous(self, coordinator, detail):
        self.assertAlmostEqual(
            self.meeting.y() + self.meeting.height() + coordinator.gap,
            detail.y(),
            delta=1,
        )
        self.assertIsNone(getattr(detail, "below", None))

    def test_expanding_managed_result_card_reflows_the_activity_stack(self):
        detail = ResultOverlay("bottom-left")
        self.addCleanup(detail.close)
        self.addCleanup(detail.deleteLater)
        detail.show_result(" ".join(["result"] * 80))
        coordinator = self.coordinator_with("result-2", detail)

        detail.set_expanded(True)

        self.assert_contiguous(coordinator, detail)

    def test_expanding_managed_live_popup_reflows_the_activity_stack(self):
        detail = LivePopup("bottom-left")
        self.addCleanup(detail.close)
        self.addCleanup(detail.deleteLater)
        detail.toggle()
        coordinator = self.coordinator_with("live-2", detail)

        detail.set_expanded(True)

        self.assert_contiguous(coordinator, detail)


class RetiredViewStaysUsable(DikteTest):
    """A retired activity's view is put away, not deleted.

    `dikte restart` dismisses the views that are still current before it
    replaces the process. A view deleted when its activity ended left that name
    pointing at a dead object, so the restart raised on the way, the exec never
    happened, and the old code kept running with nothing said about why.
    """

    def test_a_restart_after_a_finished_dictation_still_goes_through(self):
        shell = object.__new__(dikte.Dikte)
        shell.state = dikte.IDLE
        shell.ask_state = dikte.IDLE
        shell.meeting_state = dikte.M_IDLE
        shell.evdev = shell.tray = mock.Mock()
        shell.recorder = shell.meeting_ticker = shell.meeting_recorder = mock.Mock()
        shell._coordinator = None
        shell._activity_ids = {}
        shell.result_overlay = None
        finished = overlay_module.Overlay(interactive_live=True)
        self.addCleanup(finished.close)
        self.addCleanup(finished.deleteLater)
        shell.overlay = finished
        shell.ask_overlay = mock.Mock()
        shell.meeting_overlay = mock.Mock()
        shell._activity_widgets = {dikte.DICTATION: finished}

        dikte.Dikte._retire_activity(shell, dikte.DICTATION, finished)
        # No loop turns in a test: a deletion queued by the old code is run by
        # hand, so this test still fails if retiring deletes the view.
        QApplication.sendPostedEvents(finished, QEvent.Type.DeferredDelete)

        with mock.patch.object(dikte.ggml, "stop_all"):
            dikte.Dikte.shutdown(shell)

        finished.dismiss()                    # the view is still usable
        shell.ask_overlay.dismiss.assert_called_once()
        shell.tray.hide.assert_called_once()


if __name__ == "__main__":
    unittest.main()

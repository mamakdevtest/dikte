"""Activity-stack contracts that must survive independent overlay lifecycles."""

import unittest

from PyQt6.QtWidgets import QApplication

import overlay as overlay_module
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


if __name__ == "__main__":
    unittest.main()

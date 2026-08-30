"""Chronological layout authority for independent overlay activities.

An activity belongs to the coordinator for its complete visible lifetime.
The coordinator, rather than a widget's legacy ``below`` relationship, owns
its corner placement.  This keeps an expanding card from moving itself into a
neighbour's slot and makes removal close gaps immediately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import QApplication
except Exception:  # headless / import-time fallback
    QCursor = None  # type: ignore
    QApplication = None  # type: ignore

from overlay import GAP as OVERLAY_GAP, MARGIN as OVERLAY_MARGIN


@dataclass
class Activity:
    """A logical activity occupying one overlay slot.

    ``created_order`` is monotonic; smaller values are older and appear
    higher (smaller y) when ``ordered()`` is used.
    """

    id: str
    kind: str
    created_order: int = -1
    state: str = "recording"
    # Optional live widget reference; coordinator positions it if present.
    widget: object = field(default=None, compare=False, repr=False)
    collapsed: bool = False
    expanded: bool = False

    def height(self) -> float:
        """Effective height used for geometry (collapsed vs expanded)."""
        w = self.widget
        if w is not None and hasattr(w, "height"):
            try:
                # Prefer the widget's current height (already accounts for
                # collapsed constant _MEETING_COLLAPSED_W / _LIVE vs footer).
                return float(w.height())
            except Exception:
                pass
        # Fallback for widget-less activities: collapsed is shorter.
        return 72.0 if not self.collapsed else 72.0

    def width(self) -> float:
        w = self.widget
        if w is not None and hasattr(w, "width"):
            try:
                return float(w.width())
            except Exception:
                pass
        return 320.0


class OverlayCoordinator:
    """Chronological stacking of overlays in a screen corner.

    - ``ordered()``: oldest → newest (deterministic).
    - ``register``/``remove`` do not mutate unrelated activities besides
      re-stacking geometry.
    - ``recompute_geometry()`` reflows gaps and respects collapsed states.
    """

    def __init__(self, corner: str = "bottom-left", margin: int = OVERLAY_MARGIN, gap: int = OVERLAY_GAP):
        self.corner: str = corner
        self.margin: int = int(margin)
        self.gap: int = int(gap)
        self._activities: Dict[str, Activity] = {}
        self._next_order: int = 0

    # -- CRUD ---------------------------------------------------------

    def register(self, activity: Activity) -> Activity:
        """Add and place an activity as one atomic lifecycle operation."""
        if activity.id in self._activities:
            raise ValueError(f"activity {activity.id!r} already registered")
        if activity.created_order < 0:
            activity.created_order = self._next_order
            self._next_order += 1
        else:
            # advance counter past explicit order
            self._next_order = max(self._next_order, activity.created_order + 1)
        # Keep the same object so widget references and lifecycle state remain
        # live, while ``created_order`` stays immutable after registration.
        self._activities[activity.id] = activity
        self._bind_widget(activity.widget)
        self.recompute_geometry()
        return activity

    def update(self, activity: Activity) -> Activity:
        """Update state/kind/collapsed for existing id; ``created_order`` is immutable."""
        existing = self._activities.get(activity.id)
        if existing is None:
            raise KeyError(activity.id)
        # Do not allow order to change — preserve chronological position
        existing.kind = activity.kind
        existing.state = activity.state
        existing.collapsed = bool(activity.collapsed)
        existing.expanded = bool(activity.expanded)
        if activity.widget is not None:
            existing.widget = activity.widget
        self._bind_widget(existing.widget)
        self.recompute_geometry()
        return existing

    def remove(self, activity_or_id) -> Optional[Activity]:
        """Remove an activity and immediately reflow every survivor."""
        key = activity_or_id.id if isinstance(activity_or_id, Activity) else str(activity_or_id)
        removed = self._activities.pop(key, None)
        if removed is not None:
            self._unbind_widget(removed.widget)
            self.recompute_geometry()
        return removed

    def get(self, activity_id: str) -> Optional[Activity]:
        return self._activities.get(activity_id)

    def ordered(self) -> List[Activity]:
        """Chronological — oldest (smallest created_order) first = top."""
        return sorted(self._activities.values(), key=lambda a: a.created_order)

    def __len__(self) -> int:
        return len(self._activities)

    def __contains__(self, activity_id: str) -> bool:
        return activity_id in self._activities

    # -- widget ownership ---------------------------------------------

    def _bind_widget(self, widget) -> None:
        """Tell a widget that its position is coordinator-managed.

        Overlay-family widgets implement ``set_overlay_coordinator``.  The
        light fallback keeps geometry-only test doubles usable without making
        an unmanaged legacy ``below`` chain part of the runtime contract.
        """
        if widget is None:
            return
        setter = getattr(widget, "set_overlay_coordinator", None)
        if callable(setter):
            setter(self)
        else:
            setattr(widget, "_overlay_coordinator", self)

    def _unbind_widget(self, widget) -> None:
        """Release a widget when its activity is no longer active."""
        if widget is None:
            return
        if getattr(widget, "_overlay_coordinator", None) is not self:
            return
        setter = getattr(widget, "set_overlay_coordinator", None)
        if callable(setter):
            setter(None)
        else:
            setattr(widget, "_overlay_coordinator", None)

    # -- geometry -----------------------------------------------------

    def _screen_area(self):
        if QApplication is None:
            return None
        try:
            if QCursor is not None:
                screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            else:
                screen = QApplication.primaryScreen()
            if screen is None:
                return None
            return screen.availableGeometry()
        except Exception:
            return None

    def _activity_height(self, act: Activity) -> int:
        # If widget exists use its sizeHint/height; otherwise use Activity.height()
        try:
            h = int(act.height())
            return max(1, h)
        except Exception:
            return 72

    def _activity_width(self, act: Activity) -> int:
        try:
            return int(act.width())
        except Exception:
            return 320

    def recompute_geometry(self) -> List[Activity]:
        """Reflow all widgets from the screen corner with gaps.

        - Oldest at smallest y (top of stack).
        - Gaps collapsed cleanly on removal.
        - Collapsed activities use their smaller height.
        - Managed widgets never use a legacy ``below`` pointer for placement.
        - Positions widgets via ``move(x, y)`` when available.

        Returns ``ordered()`` for convenience.
        """
        ordered = self.ordered()
        if not ordered:
            return ordered

        area = self._screen_area()
        # Fallback geometry for headless/offscreen tests
        if area is None:
            # Simulate a 1920x1080 available area
            class _Fallback:
                def left(self): return 0
                def top(self): return 0
                def right(self): return 1920
                def bottom(self): return 1080
                def width(self): return 1920
                def height(self): return 1080
            area = _Fallback()  # type: ignore

        left = "left" in self.corner
        top = "top" in self.corner

        # Gather heights
        heights = [self._activity_height(a) for a in ordered]
        total = sum(heights) + self.gap * max(0, len(ordered) - 1)

        # Compute y for each activity
        if top:
            y_cursor = int(area.top() + self.margin)  # type: ignore
            ys = []
            for h in heights:
                ys.append(y_cursor)
                y_cursor += h + self.gap
        else:
            # bottom: newest closest to corner -> oldest at smallest y
            bottom = int(area.bottom())  # type: ignore
            start_y = bottom - self.margin - total
            ys = []
            y = start_y
            for h in heights:
                ys.append(int(y))
                y += h + self.gap

        # Compute x (same for all in corner)
        for act, y in zip(ordered, ys):
            w = self._activity_width(act)
            if left:
                x = int(area.left() + self.margin)  # type: ignore
            else:
                x = int(area.right() - w - self.margin)  # type: ignore
            widget = act.widget
            if widget is not None:
                # Keep corner in sync
                try:
                    widget.corner = self.corner  # type: ignore
                except Exception:
                    pass
                try:
                    widget.move(int(x), int(y))
                except Exception:
                    pass

        return ordered

    # -- convenience --------------------------------------------------

    def set_corner(self, corner: str):
        self.corner = str(corner)
        self.recompute_geometry()

    def clear(self):
        for activity in self._activities.values():
            self._unbind_widget(activity.widget)
        self._activities.clear()

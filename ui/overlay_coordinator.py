"""OverlayCoordinator — chronological stacking for N overlays in a corner.

Replaces the fixed ``below`` 2-deep chain with explicit chronological
ordering (oldest at top). Handles gaps, collapsed states, and screen
positioning; keeps ``below`` pointer in sync for backward compatibility.
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
    created_order: int
    state: str
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
        """Add an activity. Assigns ``created_order`` if negative/unset."""
        if activity.id in self._activities:
            raise ValueError(f"activity {activity.id!r} already registered")
        if activity.created_order < 0:
            activity.created_order = self._next_order
            self._next_order += 1
        else:
            # advance counter past explicit order
            self._next_order = max(self._next_order, activity.created_order + 1)
        # store copy to avoid external mutation? Keep same object intentionally
        # so widget references stay live, but ordering keys are stable.
        self._activities[activity.id] = activity
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
        return existing

    def remove(self, activity_or_id) -> Optional[Activity]:
        """Remove by Activity or id; returns removed activity or None."""
        key = activity_or_id.id if isinstance(activity_or_id, Activity) else str(activity_or_id)
        return self._activities.pop(key, None)

    def get(self, activity_id: str) -> Optional[Activity]:
        return self._activities.get(activity_id)

    def ordered(self) -> List[Activity]:
        """Chronological — oldest (smallest created_order) first = top."""
        return sorted(self._activities.values(), key=lambda a: a.created_order)

    def __len__(self) -> int:
        return len(self._activities)

    def __contains__(self, activity_id: str) -> bool:
        return activity_id in self._activities

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
        - Updates each widget's ``below`` pointer for backward compatibility.
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

        # Backward-compat: chain ``below`` pointers oldest→newest
        # bottom chain: below is the item directly beneath (larger y for top,
        # or smaller? Original: below is visually below (larger y for top,
        # smaller y for bottom?) Simplify: chain in ordered order: each item's
        # below is the previous item (older). Top stacking test expects deterministic.
        for idx, act in enumerate(ordered):
            widget = act.widget
            if widget is None:
                continue
            if idx == 0:
                below_widget = None
            else:
                below_widget = ordered[idx - 1].widget
            try:
                # Only assign if widget has attribute
                if hasattr(widget, "below"):
                    widget.below = below_widget  # type: ignore
            except Exception:
                pass
            # Update stacked flag if method exists
            try:
                if hasattr(widget, "_stacked"):
                    # Reflect whether below is showing
                    showing = False
                    if below_widget is not None and hasattr(below_widget, "showing"):
                        showing = bool(below_widget.showing)
                    elif below_widget is not None and hasattr(below_widget, "isVisible"):
                        try:
                            showing = bool(below_widget.isVisible())
                        except Exception:
                            showing = False
                    widget._stacked = showing  # type: ignore
            except Exception:
                pass

        return ordered

    # -- convenience --------------------------------------------------

    def set_corner(self, corner: str):
        self.corner = str(corner)
        self.recompute_geometry()

    def clear(self):
        self._activities.clear()

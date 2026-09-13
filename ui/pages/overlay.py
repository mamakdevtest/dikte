"""Overlay page: the indicator lives outside this window, so it says where."""

import paste

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from i18n import t

from .. import theme
from ..widgets import EmptyState, InfoNote
from . import page, scrolled


def _desk_palette():
    return theme.palette()


def _state_card(title: str, desc: str, preview: QWidget) -> QWidget:
    """Compatibility caption card (kept for tests); not used by build()."""
    from PyQt6.QtWidgets import QFrame
    c = _desk_palette()
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 8px; }}"
    )
    outer = QVBoxLayout(card)
    outer.setContentsMargins(10, 10, 10, 10)
    outer.setSpacing(9)

    desk = QFrame(card)
    desk.setStyleSheet(
        f"QFrame {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }}"
    )
    desk.setMinimumHeight(96)
    desk_layout = QVBoxLayout(desk)
    desk_layout.setContentsMargins(12, 18, 12, 18)
    desk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desk_layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignCenter)
    outer.addWidget(desk)

    cap = QVBoxLayout()
    cap.setContentsMargins(2, 0, 2, 0)
    cap.setSpacing(1)
    b = QLabel(title, card)
    b.setWordWrap(True)
    b.setStyleSheet("font-size: 13px; font-weight: 600;")
    cap.addWidget(b)
    s = QLabel(desc, card)
    s.setWordWrap(True)
    s.setStyleSheet(f"font-size: 11.5px; color: {c['fg3']};")
    cap.addWidget(s)
    cap_wrap = QWidget(card)
    cap_wrap.setLayout(cap)
    outer.addWidget(cap_wrap)
    return card


def build(window):
    body, outer = page(
        t("Indicator"),
        t("The indicator shows recording, work and result states at a glance. The tray menu keeps the same actions reachable outside the window."),
    )

    # A session with no XWayland cannot place the indicator at all, and this page
    # is where the corner is chosen and otherwise says there is nothing to
    # configure — so it is the one honest place to say that. See
    # paste.UNPLACED for the decision.
    if paste.indicator_platform() == paste.UNPLACED:
        outer.addWidget(InfoNote(t(
            "This session has no XWayland, so the indicator cannot be placed in a "
            "corner: it appears wherever the compositor puts it. Installing "
            "XWayland gives it back the corner you choose here.")))

    # The empty state is the whole page. It used to sit under the title with a
    # void beneath it — `EmptyState` centres its own contents, but nothing centred
    # `EmptyState`, and the trailing stretch pushed it up out of the middle.
    outer.addStretch(1)
    outer.addWidget(EmptyState(
        "monitor",
        t("No overlay preview"),
        t("The live indicator appears on its own while recording; "
          "there is nothing to configure here."),
    ))
    outer.addStretch(1)
    return scrolled(body)

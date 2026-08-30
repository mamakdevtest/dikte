"""Overlay page: visual states, corner behavior, tuning and tray demo."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from i18n import t

from .. import theme
from ..icons import icon as app_icon
from ..widgets import SectionCard
from . import page, scrolled


def _desk_palette():
    return theme.palette()


def _ov_widget(state: str, text: str = "", timer: str = "", dismissable: bool = False, dual: bool = False) -> QWidget:
    """One overlay pill preview matching overlay.html .ov variants."""
    # Thinking is a composite preview: small panel above busy pill
    if state == "thinking":
        # Outer wrapper with thinking pill + busy pill
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        thinking = QLabel(text or "Agent is thinking…")
        thinking.setFixedHeight(36)
        thinking.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        c = _desk_palette()
        thinking.setStyleSheet(
            f"QLabel {{ background: {c['field']}; border: 1px solid {c['border']}; border-radius: 10px; padding-left: 12px; font-size: 11px; color: {c['fg']}; }}")
        v.addWidget(thinking)
        busy = _ov_widget("busy", text="Asking Claude…", dismissable=False)
        v.addWidget(busy)
        wrapper.setFixedHeight(72 + 10 + 36)
        return wrapper
    c = _desk_palette()
    ov = QFrame()
    ov.setObjectName("ovPreview")
    # Visual mimic .ov
    ov.setStyleSheet(
        f"QFrame#ovPreview {{ background: {c['field']}; border: 1px solid {c['border']}; "
        f"border-radius: 24px; }} Label {{ background: transparent; border: none; }}"
    )
    ov.setFixedHeight(72)
    if state in ("recording", "asking", "meeting", "paused"):
        ov.setFixedWidth(520)
    # Inner layout
    layout = QHBoxLayout(ov)
    layout.setContentsMargins(28, 0, 20, 0)
    layout.setSpacing(16)
    layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    # dot / arc / check
    state_colors = {
        "recording": c["terra"],
        "asking": c["sageDark"],
        "meeting": c["terra"],
        "paused": c["sageDark"],
        "busy": c["info"],
        "done": c["ok"],
        "warning": c["warn"],
        "error": c["err"],
    }
    color = state_colors.get(state, c["fg3"])
    if state in ("recording", "asking", "meeting", "paused"):
        dot = QLabel(ov)
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background: {color}; border-radius: 6px;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        # Preview the same right-edge/live-edge waveform as production.
        wave = QWidget(ov)
        wave.setFixedWidth(280)
        wave_layout = QHBoxLayout(wave)
        wave_layout.setContentsMargins(0, 0, 0, 0)
        wave_layout.setSpacing(3)
        heights = (4, 5, 6, 7, 9, 12, 16, 13, 18, 10, 14, 20, 12, 23,
                   16, 25, 11, 20, 29, 17, 31, 23, 35, 19, 28, 38, 24, 32,
                   18, 27, 34)
        # For dual, show two channel accents without adding extra controls.
        if dual:
            for index, h in enumerate(heights):
                bar = QLabel(wave)
                bar.setFixedSize(4, max(4, h // 2))
                bar_color = c["terra"] if index % 2 else c["info"]
                bar.setStyleSheet(f"background: {bar_color}; border-radius: 2px;")
                wave_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignBottom)
            layout.addWidget(wave, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            for index, h in enumerate(heights):
                bar = QLabel(wave)
                bar.setFixedSize(4, h if not state == "paused" else 4)
                bar.setStyleSheet(
                    f"background: {color}; border-radius: 2px; opacity: "
                    f"{0.58 + 0.42 * index / (len(heights) - 1):.2f};")
                wave_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(wave, 0, Qt.AlignmentFlag.AlignVCenter)
        if timer:
            tm = QLabel(timer, ov)
            tm.setFixedWidth(76)
            tm.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tm.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 12px; color: white;")
            layout.addWidget(tm, 0, Qt.AlignmentFlag.AlignVCenter)
        if not dual:
            # Pause/Resume button
            action = QLabel(ov)
            action.setObjectName("ovAction")
            action.setFixedSize(40, 40)
            action.setAlignment(Qt.AlignmentFlag.AlignCenter)
            action.setPixmap(app_icon("play" if state == "paused" else "pause", 20, c["fg"]).pixmap(20, 20))
            action.setStyleSheet(
                f"QLabel#ovAction {{ background: {c['surface2']}; "
                f"border: 1px solid {c['sageDark'] if state == 'paused' else c['border']}; border-radius: 20px; }}")
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignVCenter)
            # Stop button (separate Stop Recording action, 40px visual, 48px hit in production)
            stop = QLabel(ov)
            stop.setObjectName("ovStop")
            stop.setFixedSize(40, 40)
            stop.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Draw stop as a small square via stylesheet; use icon for consistency
            stop.setPixmap(app_icon("stop", 14, c["fg"]).pixmap(14, 14))
            stop.setStyleSheet(
                f"QLabel#ovStop {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 20px; }}")
            layout.addWidget(stop, 0, Qt.AlignmentFlag.AlignVCenter)
    elif state == "busy":
        # spinner arc approx
        arc = QLabel(ov)
        arc.setFixedSize(15, 15)
        arc.setStyleSheet(f"border: 2px solid {c['border']}; border-top-color: {c['info']}; border-radius: 7px;")
        layout.addWidget(arc, 0, Qt.AlignmentFlag.AlignVCenter)
        msg = QLabel(text or t("Transcribing…"), ov)
        msg.setStyleSheet(f"font-size: 12.5px; color: {c['fg']};")
        msg.setWordWrap(False)
        layout.addWidget(msg, 1)
        if dismissable:
            x = QLabel("×", ov)
            x.setFixedSize(20, 20)
            x.setAlignment(Qt.AlignmentFlag.AlignCenter)
            x.setStyleSheet(f"color: {c['fg3']}; border-radius: 5px;")
            layout.addWidget(x, 0, Qt.AlignmentFlag.AlignVCenter)
        elif timer:
            tm = QLabel(timer, ov)
            tm.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {c['fg3']};")
            layout.addWidget(tm, 0, Qt.AlignmentFlag.AlignVCenter)
    elif state in ("done", "warning", "error"):
        dot = QLabel(ov)
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        # icon placeholder
        icon_map = {"done": "✓", "warning": "⚠", "error": "✕"}
        ic = QLabel(icon_map.get(state, ""), ov)
        ic.setFixedSize(15, 15)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"color: {color}; font-weight: 600;")
        layout.addWidget(ic, 0, Qt.AlignmentFlag.AlignVCenter)
        msg = QLabel(text or ("Pasted: ..." if state == "done" else "Warning" if state == "warning" else "Error"), ov)
        msg.setStyleSheet(f"font-size: 12.5px; color: {c['fg']};")
        msg.setWordWrap(False)
        layout.addWidget(msg, 1)
    else:
        msg = QLabel(text or state, ov)
        layout.addWidget(msg, 1)

    return ov


def _state_card(title: str, desc: str, preview: QWidget) -> QWidget:
    c = _desk_palette()
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 8px; }}"
    )
    outer = QVBoxLayout(card)
    outer.setContentsMargins(10, 10, 10, 10)
    outer.setSpacing(9)

    # desk area mimicking .desk container
    desk = QFrame(card)
    desk.setStyleSheet(
        f"QFrame {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }}"
    )
    desk.setMinimumHeight(96)
    desk_layout = QVBoxLayout(desk)
    desk_layout.setContentsMargins(12, 18, 12, 18)
    desk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desk_layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignCenter)
    # corner tag
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
    # Add as widget
    cap_wrap = QWidget(card)
    cap_wrap.setLayout(cap)
    outer.addWidget(cap_wrap)
    return card


def build(window):
    body, outer = page(
        t("Overlay/Indicator"),
        t("The indicator shows recording, work and result states at a glance. The tray menu keeps the same actions reachable outside the window."),
    )

    info = QLabel(t("Overlay interaction — live prediction already shown in the corner indicator and the Minutes raw view; visuals removed as requested."))
    info.setWordWrap(True)
    info.setStyleSheet(f"font-size: 12.5px; color: {_desk_palette()['fg2']};")
    outer.addWidget(info)

    outer.addStretch(1)
    return scrolled(body)

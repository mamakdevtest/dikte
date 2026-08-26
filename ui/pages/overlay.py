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
            action = QLabel(ov)
            action.setObjectName("ovAction")
            action.setFixedSize(40, 40)
            action.setAlignment(Qt.AlignmentFlag.AlignCenter)
            action.setPixmap(app_icon("play" if state == "paused" else "pause", 20, c["fg"]).pixmap(20, 20))
            action.setStyleSheet(
                f"QLabel#ovAction {{ background: {c['surface2']}; "
                f"border: 1px solid {c['sageDark'] if state == 'paused' else c['border']}; border-radius: 20px; }}")
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignVCenter)
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
    cap.addLayout(cap)
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

    # ---- overlay states grid ------------------------------------------
    states_card = SectionCard(
        t("Overlay states"),
        t("The corner band is 72 px tall. Color alone never carries meaning; each state also shows an icon or waveform."),
    )
    outer.addWidget(states_card)

    grid_host = QWidget()
    grid = QGridLayout(grid_host)
    grid.setContentsMargins(12, 10, 12, 12)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(14)

    states = [
        ("recording", t("A · Dictation recording"), t("Wide recording pill with a right-to-left live waveform, timer and a circular Pause action."), "recording", "00:42", False, False),
        ("asking", t("B · Agent command recording"), t("Same band, sage accent. What is recorded is a command."), "asking", "00:07", False, False),
        ("meeting", t("C · Meeting recording"), t("Two channels visible: your mic below, the other side above. Hides after 12 s."), "meeting", "1:02:41", False, True),
        ("busy", t("D · Busy"), t('Example messages: "Cleaning…", "Asking Claude…", "Writing minutes…".'), "busy", "", False, False),
        ("dismissable", t("I · Dismissable long job"), t("Faint × on the right quiets the notice; work continues and result is still shown."), "busy", "", True, False),
        ("paused", t("P · Paused"), t("Waveform inactive, timer frozen at 00:18, button becomes Resume. Click Resume to continue same session."), "paused", "00:18", False, False),
        ("done", t("E · Done"), t("Disappears on its own after 2 s; action + short preview."), "done", "", False, False),
        ("warning", t("F · Warning"), t("Text was pasted but cleanup didn't finish. 9 s."), "warning", "", False, False),
        ("error", t("G · Error"), t("Single line with call to action. Detail is in the bubble. 6 s."), "error", "", False, False),
        ("stacked", t("H · Stacked indicators"), t("Dictation and agent work independently: two jobs in the same corner with 10 px gap; when one ends the other drops to the corner."), "stacked", "", False, False),
    ]

    # Helper to assign grid position responsive: 3 columns wide, 1 on narrow? We'll create 3 columns; resize handler in settings_ui could adjust, but for now 3.
    cols = 3
    for idx, (key, title, desc, state, timer, dismiss, dual) in enumerate(states):
        if state == "stacked":
            # Special stacked: two ov's vertically
            stack = QWidget()
            sv = QVBoxLayout(stack)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(10)
            sv.addWidget(_ov_widget("recording", timer="00:18"), 0, Qt.AlignmentFlag.AlignCenter)
            sv.addWidget(_ov_widget("busy", text=t("Claude is thinking…")), 0, Qt.AlignmentFlag.AlignCenter)
            preview = stack
            # For _state_card we expect a QWidget preview; wrap stack in container that mimics desk? _state_card already creates desk wrapper, so we need to pass preview that will be placed inside desk.
            # Instead create card manually for stacked to show two.
            # Use _state_card with custom preview containing stack
            card = _state_card(title, desc, preview)
        else:
            ov = _ov_widget(state, text=title if state in ("done", "warning", "error", "busy") else "", timer=timer, dismissable=dismiss, dual=dual)
            # For done/warning/error use specific messages
            if state == "done":
                ov = _ov_widget("done", text=t("Pasted: meeting notes sent…"), timer="")
            elif state == "warning":
                ov = _ov_widget("warning", text=t("Raw pasted, cleanup failed: gateway not responding"), timer="")
            elif state == "error":
                ov = _ov_widget("error", text=t("Claude not found. Install or change provider."), timer="")
            elif state == "busy":
                ov = _ov_widget("busy", text=t("Transcribing…"), timer="0:04")
            card = _state_card(title, desc, ov)
        r, c = divmod(idx, cols)
        grid.addWidget(card, r, c)

    # Make columns stretch equally
    for col in range(cols):
        grid.setColumnStretch(col, 1)
    states_card.add(grid_host)

    # ---- corner & behavior --------------------------------------------
    behavior = SectionCard(
        t("Corner & behavior"),
        t("The indicator appears on the screen where the cursor is; it cannot be dragged, does not take focus, and only its live action accepts clicks."),
    )
    outer.addWidget(behavior)

    # Reuse corner picker note but not duplicate control; show info rows
    peek_row_widget = QWidget()
    peek_layout = QHBoxLayout(peek_row_widget)
    peek_layout.setContentsMargins(0, 0, 0, 0)
    peek_layout.addWidget(QLabel(t("Meeting indicator hides after 12 s")))
    chip = QLabel(t("automatic"))
    chip.setStyleSheet(f"background: {_desk_palette()['surface2']}; border: 1px solid {_desk_palette()['border']}; border-radius: 11px; padding: 2px 8px; font-size: 11.5px;")
    peek_layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignRight)
    # Use SettingRow wrappers? Instead add via SectionCard.add which expects widget with row styling; create custom rows
    from ..widgets import SettingRow
    # Peek row
    peek_row = SettingRow(
        t("Meeting indicator hides after 12 s"),
        t("In a long meeting the band is not always visible; after both channels are seen it yields to the tray clock."),
        chip,
    )
    # This duplicates chip; instead create row with chip already. Simplify: create row with same content.
    # We'll just use the SettingRow already with chip passed.
    behavior.add(peek_row)

    click_row = SettingRow(
        t("Click-through"),
        t("Recording and busy indicators are not there for the mouse; only the agent band is clickable and dismissable."),
        QLabel(""),  # placeholder toggle disabled
    )
    # Add a disabled toggle visual
    dummy_toggle = QLabel("✓")
    dummy_toggle.setStyleSheet(f"color: {_desk_palette()['fg3']};")
    click_row.add_control(dummy_toggle)
    behavior.add(click_row)

    # ---- tuning (simplified) -------------------------------------------
    tuning = SectionCard(
        t("Color & sound response"),
        t("Change overlay colors to match product states. The waveform grows and shrinks with sound level."),
    )
    outer.addWidget(tuning)
    # Color grid placeholder
    color_info = QLabel(t("Colors: Recording · Agent · Working · Success · Warning · Error — use theme settings to adjust."))
    color_info.setWordWrap(True)
    color_info.setStyleSheet(f"font-size: 12.5px; color: {_desk_palette()['fg2']};")
    tuning.add(color_info)
    # Sensitivity placeholder row
    sens_row = SettingRow(
        t("Sound sensitivity"),
        t("Higher values make small sounds produce a larger waveform."),
        QLabel("62"),
    )
    tuning.add(sens_row)

    # ---- tray menu demo stub -------------------------------------------
    tray_card = SectionCard(
        t("Tray menu"),
        t("Labels change with state, actions enable/disable. Left click ends a running recording or toggles dictation."),
    )
    outer.addWidget(tray_card)
    tray_demo = QLabel(t("Tray demo: Ready · Recording · Agent recording · Agent thinking · Meeting · Writing — select a state to preview the menu (prototype only)."))
    tray_demo.setWordWrap(True)
    tray_demo.setStyleSheet(f"font-size: 12.5px; color: {_desk_palette()['fg2']}; padding: 8px 4px;")
    tray_card.add(tray_demo)
    # Segmented control stub for tray states (non-functional but visual)
    from ..widgets import SegmentedControl
    seg = SegmentedControl([
        (t("Ready"), "idle"),
        (t("Recording"), "rec"),
        (t("Agent"), "ask"),
        (t("Thinking"), "busy"),
        (t("Meeting"), "meeting"),
        (t("Writing"), "writing"),
    ])
    tray_card.add(seg)
    # Preview area for tray menu (placeholder list)
    tray_preview = QFrame()
    tray_preview.setObjectName("panel")
    tray_preview.setStyleSheet(f"QFrame#panel {{ background: {_desk_palette()['surface']}; border: 1px solid {_desk_palette()['border']}; border-radius: 8px; }}")
    tray_layout = QVBoxLayout(tray_preview)
    tray_layout.setContentsMargins(12, 12, 12, 12)
    tray_layout.setSpacing(4)
    for label in [t("Start recording"), t("Ask Claude"), t("Settings…"), t("Quit")]:
        row = QLabel(f"• {label}")
        row.setStyleSheet(f"font-size: 13px; color: {_desk_palette()['fg']};")
        tray_layout.addWidget(row)
    tray_card.add(tray_preview)

    # ---- notifications ---------------------------------------------------
    notif_card = SectionCard(
        t("Balloon notifications"),
        t("Job results and failure cases. The indicator gives a short summary; detail is here."),
    )
    outer.addWidget(notif_card)
    ok_note = QLabel(t("Meeting written up: Design review\n") + "F:\\Work\\dikte\\meetings\\20260824-1430.md")
    ok_note.setWordWrap(True)
    ok_note.setProperty("note", "ok")
    notif_card.add(ok_note)
    warn_note = QLabel(t("Meeting could not be written up: model did not finish in 600 s.\n\nRecording kept. Retry from Minutes page."))
    warn_note.setWordWrap(True)
    warn_note.setProperty("note", "warn")
    notif_card.add(warn_note)

    outer.addStretch(1)
    return scrolled(body)

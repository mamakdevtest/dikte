"""Shortcuts page: the two global keys and the built-in listener."""

from PyQt6.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QWidget

import hotkey
from i18n import t

from ..widgets import InfoNote, SectionCard
from . import page, scrolled


def build(window):
    body, outer = page(
        t("Shortcuts"),
        t("Global key combinations that work wherever the focus is."),
    )

    keys = SectionCard()
    outer.addWidget(keys)
    holder = QWidget()
    form = QFormLayout(holder)
    form.setContentsMargins(20, 4, 20, 4)
    window._shortcut_row(
        form, "toggle", t("Start and stop"),
        t("No global shortcut installed."), placeholder="Ctrl+Space",
    )
    window._shortcut_row(
        form, "cancel", t("Discard the recording"),
        t("No global shortcut installed. The tray menu discards it too."),
        tooltip=t("Throws the recording away without transcribing it. Works "
                  "on a dictation and on a command for the agent alike, "
                  "whichever is running."),
    )
    window._shortcut_row(
        form, "ask", t("Ask {name}", name="Claude"),
        t("No global shortcut installed. The tray menu asks it too."),
        placeholder="Ctrl+Alt+A",
    )
    window._shortcut_row(
        form, "meeting", t("Record a meeting"),
        t("No global shortcut installed. The tray menu starts a meeting too."),
        placeholder="Ctrl+Alt+M",
    )
    keys.add(holder)

    listener = SectionCard(t("Built-in listener"))
    outer.addWidget(listener)
    window.evdev_enabled = QCheckBox(t(
        "Use the built-in listener (/dev/input), for when the {desktop} "
        "shortcut is not active yet", desktop=hotkey.desktop_name()))
    window.evdev_enabled.setToolTip(t(
        "Works immediately, no session restart. The only difference: the key "
        "combination also reaches the focused application."))
    ev_wrap = QWidget()
    ev_lay = QHBoxLayout(ev_wrap)
    ev_lay.setContentsMargins(20, 12, 20, 12)
    ev_lay.addWidget(window.evdev_enabled, 1)
    listener.add(ev_wrap)
    window.evdev_enabled.setVisible(hotkey.installs_shortcuts())
    ev_wrap.setVisible(hotkey.installs_shortcuts())

    if hotkey.shortcut_needs_restart():
        explanation = t(
            "KWin only reads shortcut settings at startup. After 'Install' the "
            "shortcut shows up under System Settings → Shortcuts, but it will "
            "not fire until you log out and back in. Until then, use the "
            "built-in listener.")
    elif hotkey.installs_shortcuts():
        explanation = t("The shortcut starts working as soon as it is installed.")
    else:
        explanation = t(
            "Dikte asks macOS for these combinations itself, while it is "
            "running. Nothing is installed, and no other application receives "
            "them in the meantime.")
    listener.add(InfoNote(explanation, variant="info"))
    outer.addStretch(1)

    return scrolled(body)

"""Shortcuts page: the two global keys and the built-in listener."""

from PyQt6.QtWidgets import QCheckBox, QFormLayout, QLabel, QVBoxLayout, QWidget

import hotkey
from i18n import t

from . import page, scrolled


def build(window):
    body, outer = page(
        t("Shortcuts"),
        t("Global key combinations that work wherever the focus is."),
    )

    form = QFormLayout()
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
    outer.addLayout(form)

    window.evdev_enabled = QCheckBox(t(
        "Use the built-in listener (/dev/input), for when the {desktop} "
        "shortcut is not active yet", desktop=hotkey.desktop_name()))
    window.evdev_enabled.setToolTip(t(
        "Works immediately, no session restart. The only difference: the key "
        "combination also reaches the focused application."))
    outer.addWidget(window.evdev_enabled)
    window.evdev_enabled.setVisible(hotkey.installs_shortcuts())

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
    note = QLabel(explanation)
    note.setWordWrap(True)
    note.setProperty("note", "info")
    outer.addWidget(note)
    outer.addStretch(1)

    return scrolled(body)

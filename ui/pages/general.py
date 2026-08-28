"""General page: language, insertion, recording, silence and storage."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QSpinBox, QWidget

import paste
from i18n import t

from ..widgets import CornerPicker, MiniScreen, SectionCard, SettingRow, gate, switch_row
from . import page, scrolled


def _combo(items, width=None):
    box = QComboBox()
    for label, data in items:
        box.addItem(label, data)
    if width:
        box.setFixedWidth(width)
    return box


def build(window):
    from settings_ui import UI_LANGUAGES, LANGUAGES, CORNERS

    body, outer = page(
        t("General"),
        t("Everyday dictation: language, where the text goes, recording limits "
          "and silence detection."),
    )

    # --- language and input ----------------------------------------------
    language_card = SectionCard(t("Language and input"))
    outer.addWidget(language_card)

    window.ui_language = _combo([(t(label), code) for label, code in UI_LANGUAGES], 220)
    window.ui_language.setToolTip(
        t("Restart Dikte for the language change to reach every window."))
    language_card.add(SettingRow(t("Interface language"),
                                 t("Restart Dikte for the language change to reach "
                                   "every window."), window.ui_language))

    # Mic sources are loaded off the GUI thread via SettingsWindow._load_audio_devices;
    # build with placeholder to keep startup <300ms.
    window.mic = _combo([(t("Default microphone"), "")], 300)
    window.mic.setPlaceholderText(t("Loading microphones…")) if hasattr(window.mic, "setPlaceholderText") else None
    language_card.add(SettingRow(t("Microphone"),
                                 t("Dictation, the agent command and the meeting "
                                   "microphone listen to this input."), window.mic))

    window.language = _combo([(t(label), code) for label, code in LANGUAGES], 220)
    language_card.add(SettingRow(t("Speech language"),
                                 t("The right language means fewer mishearings on "
                                   "the first try."), window.language))

    # --- insertion --------------------------------------------------------
    insertion = SectionCard(t("Text insertion"))
    outer.addWidget(insertion)

    paste_row, window.auto_paste = switch_row(
        t("Paste the text into the focused window"),
        t("Off means the transcript is only copied to the clipboard."))
    insertion.add(paste_row)

    window.paste_shortcut = QComboBox()
    window.paste_shortcut.setEditable(True)
    window.paste_shortcut.addItems(paste.desktop().shortcuts)
    window.paste_shortcut.setFixedWidth(180)
    window.paste_shortcut.setToolTip(t(
        "macOS asks for Accessibility permission the first time this is sent."
        if paste.desktop() is paste.MACOS else
        "Terminals usually want ctrl+shift+v. Change this if pasting does nothing."
    ))
    paste_key_row = SettingRow(t("Paste key"), "", window.paste_shortcut, dependent=True)
    insertion.add(paste_key_row)

    clipboard_row, window.restore_clipboard = switch_row(
        t("Restore the previous clipboard after pasting"),
        t("What you had copied returns once pasting is done."), dependent=True)
    insertion.add(clipboard_row)

    gate(window.auto_paste, [paste_key_row, clipboard_row])

    # --- result overlay ---------------------------------------------------
    result_card = SectionCard(t("Result display"))
    outer.addWidget(result_card)
    result_row, window.result_overlay_enabled = switch_row(
        t("Show result overlay after dictation"),
        t("When enabled, the final transcript appears in a small overlay with Copy and Close actions. "
          "Auto Paste behavior is unchanged."))
    result_card.add(result_row)

    # --- recording --------------------------------------------------------
    recording = SectionCard(t("Recording behavior"))
    outer.addWidget(recording)

    # Keep a hidden combo for test compat and save/load; visible is CornerPicker+MiniScreen.
    window.corner = _combo([(t(value), value) for value in CORNERS], 220)
    window.corner.hide()
    # Also keep reference hidden so tests can find it but not interfere with layout.
    window.corner.setObjectName("cornerComboHidden")

    corner_picker = CornerPicker(window.corner.currentData() or "bottom-left")
    mini_screen = MiniScreen(window.corner.currentData() or "bottom-left")
    window.corner_picker = corner_picker
    window.mini_screen = mini_screen
    # Side-by-side preview container
    preview_wrap = QWidget()
    preview_layout = QHBoxLayout(preview_wrap)
    preview_layout.setContentsMargins(0, 0, 0, 0)
    preview_layout.setSpacing(16)
    preview_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    preview_layout.addWidget(corner_picker, 0, Qt.AlignmentFlag.AlignVCenter)
    preview_layout.addWidget(mini_screen, 0, Qt.AlignmentFlag.AlignVCenter)
    preview_layout.addStretch(1)

    def _on_picker_changed(corner: str):
        # Sync hidden combo without emitting its signal loop, then update preview.
        idx = window.corner.findData(corner)
        if idx >= 0:
            window.corner.blockSignals(True)
            window.corner.setCurrentIndex(idx)
            window.corner.blockSignals(False)
        mini_screen.setCorner(corner)
        # Live preview: update conf and reposition any existing overlays immediately.
        try:
            if hasattr(window, "conf") and window.conf is not None:
                window.conf["overlay_corner"] = corner
            # Reposition live overlays if any (Dikte's indicator windows)
            from PyQt6.QtWidgets import QApplication
            import overlay as _ov
            app = QApplication.instance()
            if app is not None:
                for w in app.topLevelWidgets():
                    if isinstance(w, _ov.Overlay):
                        w.corner = corner
                        if getattr(w, "showing", False):
                            try:
                                w._reposition()
                            except Exception:
                                pass
        except Exception:
            pass

    corner_picker.cornerChanged.connect(_on_picker_changed)

    def _on_combo_changed(_idx: int):
        data = window.corner.currentData()
        if data:
            corner_picker.blockSignals(True)
            corner_picker.setCorner(data)
            corner_picker.blockSignals(False)
            mini_screen.setCorner(data)

    window.corner.currentIndexChanged.connect(_on_combo_changed)

    recording.add(SettingRow(t("Indicator corner"),
                             t("The floating indicator in the screen corner while "
                               "recording."), preview_wrap))
    # Add hidden combo row holder for test findChildren? Not visible but present
    # Keep a reference for backward compat; no visual row for hidden combo.

    window.max_seconds = QSpinBox()
    window.max_seconds.setRange(10, 3600)
    window.max_seconds.setSuffix(t(" s"))
    window.max_seconds.setFixedWidth(120)
    recording.add(SettingRow(t("Longest recording"),
                             t("A recording that reaches this stops on its own and "
                               "is still transcribed."), window.max_seconds))
    live_row, window.live_transcript = switch_row(
        t("Live transcript preview"),
        t("While recording, the words are shown as they are heard — the small "
          "lines button on the indicator opens a wider view. It transcribes "
          "the newest seconds with the same provider dictation uses, so a "
          "hosted provider makes a few extra small calls."))
    recording.add(live_row)

    # --- silence ----------------------------------------------------------
    silence = SectionCard(t("Silence detection"))
    outer.addWidget(silence)

    skip_row, window.skip_silent = switch_row(
        t("Skip silent recordings (don't call the API)"),
        t("Below the threshold the transcription is never called."))
    silence.add(skip_row)

    window.silence_db = QSpinBox()
    window.silence_db.setRange(-80, -20)
    window.silence_db.setSuffix(" dB")
    window.silence_db.setFixedWidth(120)
    window.silence_db.setToolTip(t(
        "Speech also has to rise {margin} dB above the recording's own noise "
        "floor, so this absolute floor rarely needs touching.", margin=10))
    threshold_row = SettingRow(t("Silence threshold"), "", window.silence_db,
                               dependent=True)
    silence.add(threshold_row)

    hallucination_row, window.filter_hallucinations = switch_row(
        t("Discard stock phrases models invent for near-silent audio"),
        t("Whisper answers silence with things like “Thanks for watching”."),
        dependent=True)
    silence.add(hallucination_row)

    gate(window.skip_silent, [threshold_row, hallucination_row])

    # --- storage ----------------------------------------------------------
    storage = SectionCard(t("Storage"))
    outer.addWidget(storage)
    keep_row, window.keep_audio = switch_row(
        t("Keep audio files"),
        t("Off means the recording is deleted once transcribed."))
    storage.add(keep_row)

    outer.addStretch(1)
    return scrolled(body)

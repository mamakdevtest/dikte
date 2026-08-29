"""Meeting page: sound sources, speakers, the minutes model and recording."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import btn
from . import page, scrolled


def build(window):
    from settings_ui import LANGUAGES, MEETING_MODELS, REASONING_LEVELS

    body, outer = page(
        t("Meeting"),
        t("A meeting is recorded from two devices at once: your microphone and "
          "whatever comes out of your speakers. Nothing has to guess who was "
          "speaking, because the two never share a channel."),
    )

    sources = QGroupBox(t("Sound"))
    sources_form = QFormLayout(sources)
    sources_form.setContentsMargins(20, 16, 20, 12)
    window.meeting_mic = QComboBox()
    window.meeting_mic.addItem(t("Same as dictation"), "")
    # Sources filled asynchronously via SettingsWindow._load_audio_devices
    window.meeting_mic.setFixedWidth(300)
    sources_form.addRow(t("Microphone"), window.meeting_mic)

    window.meeting_system = QComboBox()
    window.meeting_system.addItem(t("Current output"), "")
    # Monitors filled asynchronously via SettingsWindow._load_audio_devices
    window.meeting_system.setFixedWidth(300)
    sources_form.addRow(t("The other participants"), window.meeting_system)

    # macOS loopback note deferred until audio probes complete; show placeholder
    try:
        import audio as _audio

        if _audio.sound() is _audio.COREAUDIO:
            mac_note = QLabel(t(
                "macOS does not offer what the speakers are playing as something "
                "to record. Install BlackHole or Loopback, send the meeting's "
                "sound through it, and pick it above."))
            mac_note.setWordWrap(True)
            sources_form.addRow(mac_note)
    except Exception:
        pass

    note = QLabel(t(
        "Wear headphones if you can. Through speakers your microphone hears "
        "the other side as well, and although a line that lands on both "
        "channels at once is dropped again, the repair is never as clean as "
        "not needing it."))
    note.setWordWrap(True)
    sources_form.addRow(note)
    outer.addWidget(sources)

    people = QGroupBox(t("Who is talking"))
    people_form = QFormLayout(people)
    people_form.setContentsMargins(20, 16, 20, 12)
    window.meeting_self_name = QLineEdit()
    window.meeting_self_name.setPlaceholderText(t("Me"))
    window.meeting_self_name.setFixedWidth(240)
    people_form.addRow(t("You"), window.meeting_self_name)
    window.meeting_other_name = QLineEdit()
    window.meeting_other_name.setPlaceholderText(t("Other side"))
    window.meeting_other_name.setFixedWidth(240)
    people_form.addRow(t("The other end"), window.meeting_other_name)
    window.meeting_participants = QPlainTextEdit()
    window.meeting_participants.setMaximumHeight(70)
    window.meeting_participants.setPlaceholderText(t("One name per line"))
    people_form.addRow(t("Expected"), window.meeting_participants)
    people_note = QLabel(t(
        "Everyone on the far end shares one label: they reach you as a single "
        "mixed signal. The names go to the transcription model so they come "
        "out spelled right, and to the minutes, which may use one for a line "
        "only when the conversation itself makes clear who was speaking."))
    people_note.setWordWrap(True)
    people_form.addRow(people_note)
    outer.addWidget(people)

    models = QGroupBox(t("Minutes"))
    models_form = window.meeting_form = QFormLayout(models)
    models_form.setContentsMargins(20, 16, 20, 12)
    window.meeting_provider = QComboBox()
    for label, value in window._meeting_choices():
        window.meeting_provider.addItem(label, value)
    window.meeting_provider.setFixedWidth(280)
    window.meeting_provider.currentIndexChanged.connect(
        window._meeting_provider_changed)
    models_form.addRow(t("Runs on"), window.meeting_provider)
    window.meeting_model = QComboBox()
    window.meeting_model.setEditable(True)
    window.meeting_model.addItems(MEETING_MODELS)
    window.refresh_meeting_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_meeting_models.clicked.connect(window._load_meeting_models)
    window.meeting_model_row = window._row(window.meeting_model,
                                           window.refresh_meeting_models)
    models_form.addRow(t("Model"), window.meeting_model_row)
    window.meeting_models_label = QLabel("")
    window.meeting_models_label.setWordWrap(True)
    models_form.addRow(window.meeting_models_label)
    window.meeting_reasoning = QComboBox()
    for label, value in REASONING_LEVELS:
        window.meeting_reasoning.addItem(t(label), value)
    window.meeting_reasoning.setFixedWidth(240)
    window.meeting_reasoning.setToolTip(t(
        "Unlike cleanup, this one is worth some thinking: it has to hold a "
        "whole meeting in its head and work out what was actually decided."))
    models_form.addRow(t("Thinking"), window.meeting_reasoning)
    window.meeting_language = QComboBox()
    window.meeting_language.addItem(t("Same as dictation"), "")
    for label, code in LANGUAGES:
        window.meeting_language.addItem(t(label), code)
    window.meeting_language.setFixedWidth(240)
    models_form.addRow(t("Speech language"), window.meeting_language)
    window.meeting_mine_language = QComboBox()
    window.meeting_mine_language.addItem(t("Same as the meeting language"), "")
    for label, code in LANGUAGES:
        window.meeting_mine_language.addItem(t(label), code)
    window.meeting_mine_language.setFixedWidth(240)
    models_form.addRow(t("Your speech"), window.meeting_mine_language)
    window.meeting_theirs_language = QComboBox()
    window.meeting_theirs_language.addItem(t("Same as the meeting language"), "")
    for label, code in LANGUAGES:
        window.meeting_theirs_language.addItem(t(label), code)
    window.meeting_theirs_language.setFixedWidth(240)
    models_form.addRow(t("The other side's speech"),
                       window.meeting_theirs_language)
    window.meeting_cleanup = QCheckBox(t("Clean the transcript up first"))
    window.meeting_cleanup.setToolTip(t(
        "Runs the cleanup model over the transcript before the minutes are "
        "written, keeping the timestamps and the speaker labels."))
    models_form.addRow("", window.meeting_cleanup)
    outer.addWidget(models)

    recording = QGroupBox(t("Recording"))
    recording_form = QFormLayout(recording)
    recording_form.setContentsMargins(20, 16, 20, 12)
    window.meeting_max_minutes = QSpinBox()
    window.meeting_max_minutes.setRange(5, 600)
    window.meeting_max_minutes.setSuffix(t(" min"))
    recording_form.addRow(t("Longest meeting"), window.meeting_max_minutes)
    window.meeting_keep_audio = QCheckBox(
        t("Keep the recording after the minutes are written"))
    window.meeting_keep_audio.setToolTip(t(
        "A run that fails keeps its recording either way, so it can be tried "
        "again from the Minutes tab. This is about the ones that worked."))
    recording_form.addRow("", window.meeting_keep_audio)
    window.meeting_retention = QSpinBox()
    window.meeting_retention.setRange(0, 365)
    window.meeting_retention.setSuffix(t(" days"))
    window.meeting_retention.setSpecialValueText(t("Never"))
    window.meeting_retention.setFixedWidth(160)
    window.meeting_retention.setToolTip(t(
        "Recordings older than this are deleted when the app starts and "
        "after each meeting. The written minutes are never touched."))
    recording_form.addRow(t("Delete recordings after"),
                          window.meeting_retention)
    window._shortcut_row(
        recording_form, "meeting", t("Shortcut"),
        t("No global shortcut installed. The tray menu starts a meeting too."),
    )
    outer.addWidget(recording)

    prompt_label = QLabel(t("System instruction given to the minutes model."))
    prompt_label.setWordWrap(True)
    outer.addWidget(prompt_label)
    window.meeting_prompt = QPlainTextEdit()
    window.meeting_prompt.setMinimumHeight(200)
    outer.addWidget(window.meeting_prompt, 1)
    reset = btn(t("Reset to default"))
    reset.clicked.connect(
        lambda: window.meeting_prompt.setPlainText(cfg.default_meeting_prompt()))
    outer.addWidget(reset, 0, Qt.AlignmentFlag.AlignRight)

    return scrolled(body)

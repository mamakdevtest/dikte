"""Meeting page: sound sources, speakers, the minutes model and recording."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSizePolicy, QSpinBox, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import InfoNote, SectionCard, SettingRow, btn
from . import page, scrolled


def _expanding(widget, min_width):
    """Minimum width + Expanding: grows for long TR labels, never truncates."""
    widget.setMinimumWidth(min_width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class _CardForm:
    """QFormLayout-compatible shim over a SectionCard.

    window._shortcut_row() calls addRow(); settings_ui.py calls
    setRowVisible for the gateway-only model row. The shim maps each inner
    widget to its SettingRow wrapper and toggles both.
    """

    def __init__(self, card):
        self._card = card
        self._map = {}

    def _register(self, widget, row):
        self._map[id(widget)] = (widget, row)

    def addRow(self, *args):
        if len(args) == 1:
            (widget,) = args
            if isinstance(widget, QLabel):
                wrap = QWidget()
                lay = QHBoxLayout(wrap)
                lay.setContentsMargins(20, 0, 20, 8)
                lay.addWidget(widget, 1)
                self._card.add(wrap)
                self._register(widget, wrap)
            else:
                self._card.add(widget)
                self._register(widget, None)
            return
        if len(args) == 2:
            label, field = args
            if isinstance(label, str):
                row = SettingRow(label, "", field)
                self._card.add(row)
                self._register(field, row)
                return
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(20, 4, 20, 4)
            lay.setSpacing(8)
            lay.addWidget(label, 0)
            lay.addWidget(field, 1)
            self._card.add(wrap)
            self._register(label, wrap)
            self._register(field, wrap)
            return
        raise TypeError("addRow takes 1 or 2 arguments")

    def setRowVisible(self, widget, visible):
        entry = self._map.get(id(widget))
        try:
            widget.setVisible(bool(visible))
        except Exception:
            pass
        if entry is not None:
            _, row = entry
            if row is not None and row is not widget:
                try:
                    row.setVisible(bool(visible))
                except Exception:
                    pass

    def isRowVisible(self, widget):
        entry = self._map.get(id(widget))
        if entry is not None:
            _, row = entry
            if row is not None and row is not widget:
                try:
                    if row.isHidden():
                        return False
                except Exception:
                    pass
        try:
            return not widget.isHidden()
        except Exception:
            return True


def _setting(card, form, label, help_text, control):
    row = SettingRow(label, help_text, control)
    card.add(row)
    form._register(control, row)
    return row


def _note(card, form, widget):
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(20, 0, 20, 8)
    lay.addWidget(widget, 1)
    card.add(wrap)
    form._register(widget, wrap)
    return wrap


def build(window):
    from settings_ui import LANGUAGES, MEETING_MODELS, REASONING_LEVELS

    body, outer = page(
        t("Meeting"),
        t("A meeting is recorded from two devices at once: your microphone and "
          "whatever comes out of your speakers. Nothing has to guess who was "
          "speaking, because the two never share a channel."),
    )

    # --- sound sources (combos filled asynchronously) ----------------------
    sources = SectionCard(t("Sound"))
    outer.addWidget(sources)
    sources_form = _CardForm(sources)
    window.meeting_mic = _expanding(QComboBox(), 300)
    window.meeting_mic.addItem(t("Same as dictation"), "")
    # Sources filled asynchronously via SettingsWindow._load_audio_devices
    _setting(sources, sources_form, t("Microphone"),
             t("Your voice, from this input."),
             window.meeting_mic)

    window.meeting_system = _expanding(QComboBox(), 300)
    window.meeting_system.addItem(t("Current output"), "")
    # Monitors filled asynchronously via SettingsWindow._load_audio_devices
    _setting(sources, sources_form, t("The other participants"),
             t("Speaker sound, from this output."),
             window.meeting_system)

    # macOS loopback note deferred until audio probes complete; show placeholder
    try:
        import audio as _audio

        if _audio.sound() is _audio.COREAUDIO:
            _note(sources, sources_form, InfoNote(t(
                "macOS does not offer what the speakers are playing as something "
                "to record. Install BlackHole or Loopback, send the meeting's "
                "sound through it, and pick it above."), variant="info"))
    except Exception:
        pass

    _note(sources, sources_form, InfoNote(t(
        "Wear headphones if you can. Through speakers your microphone hears "
        "the other side as well, and although a line that lands on both "
        "channels at once is dropped again, the repair is never as clean as "
        "not needing it."), variant="info"))

    # --- speakers ----------------------------------------------------------
    people = SectionCard(t("Who is talking"))
    outer.addWidget(people)
    people_form = _CardForm(people)
    window.meeting_self_name = _expanding(QLineEdit(), 240)
    window.meeting_self_name.setPlaceholderText(t("Me"))
    _setting(people, people_form, t("You"),
             t("What the minutes call you."),
             window.meeting_self_name)
    window.meeting_other_name = _expanding(QLineEdit(), 240)
    window.meeting_other_name.setPlaceholderText(t("Other side"))
    _setting(people, people_form, t("The other end"),
             t("One label for the whole far end."),
             window.meeting_other_name)
    window.meeting_participants = QPlainTextEdit()
    window.meeting_participants.setMaximumHeight(70)
    window.meeting_participants.setPlaceholderText(t("One name per line"))
    _setting(people, people_form, t("Expected"),
             t("One name per line, for spelling."),
             window.meeting_participants)
    _note(people, people_form, InfoNote(t(
        "Everyone on the far end shares one label: they reach you as a single "
        "mixed signal. The names go to the transcription model so they come "
        "out spelled right, and to the minutes, which may use one for a line "
        "only when the conversation itself makes clear who was speaking."),
        variant="info"))

    # --- minutes model -----------------------------------------------------
    models = SectionCard(t("Minutes"))
    outer.addWidget(models)
    models_form = window.meeting_form = _CardForm(models)
    window.meeting_provider = _expanding(QComboBox(), 280)
    for label, value in window._meeting_choices():
        window.meeting_provider.addItem(label, value)
    window.meeting_provider.currentIndexChanged.connect(
        window._meeting_provider_changed)
    _setting(models, models_form, t("Runs on"),
             t("Which model writes the minutes."),
             window.meeting_provider)
    window.meeting_model = QComboBox()
    window.meeting_model.setEditable(True)
    window.meeting_model.addItems(MEETING_MODELS)
    window.refresh_meeting_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_meeting_models.clicked.connect(window._load_meeting_models)
    window.meeting_model_row = window._row(window.meeting_model,
                                           window.refresh_meeting_models)
    _setting(models, models_form, t("Model"),
             t("Gateway model id for the minutes."),
             window.meeting_model_row)
    window.meeting_models_label = QLabel("")
    window.meeting_models_label.setWordWrap(True)
    _note(models, models_form, window.meeting_models_label)
    window.meeting_reasoning = _expanding(QComboBox(), 240)
    for label, value in REASONING_LEVELS:
        window.meeting_reasoning.addItem(t(label), value)
    window.meeting_reasoning.setToolTip(t(
        "Unlike cleanup, this one is worth some thinking: it has to hold a "
        "whole meeting in its head and work out what was actually decided."))
    _setting(models, models_form, t("Thinking"),
             t("Worth it: it holds the whole meeting."),
             window.meeting_reasoning)
    window.meeting_language = _expanding(QComboBox(), 240)
    window.meeting_language.addItem(t("Same as dictation"), "")
    for label, code in LANGUAGES:
        window.meeting_language.addItem(t(label), code)
    _setting(models, models_form, t("Speech language"),
             t("What both sides are heard as."),
             window.meeting_language)
    window.meeting_mine_language = _expanding(QComboBox(), 240)
    window.meeting_mine_language.addItem(t("Same as the meeting language"), "")
    for label, code in LANGUAGES:
        window.meeting_mine_language.addItem(t(label), code)
    _setting(models, models_form, t("Your speech"),
             t("Empty follows the meeting language."),
             window.meeting_mine_language)
    window.meeting_theirs_language = _expanding(QComboBox(), 240)
    window.meeting_theirs_language.addItem(t("Same as the meeting language"), "")
    for label, code in LANGUAGES:
        window.meeting_theirs_language.addItem(t(label), code)
    _setting(models, models_form, t("The other side's speech"),
             t("Empty follows the meeting language."),
             window.meeting_theirs_language)
    window.meeting_cleanup = QCheckBox()
    window.meeting_cleanup.setToolTip(t(
        "Runs the cleanup model over the transcript before the minutes are "
        "written, keeping the timestamps and the speaker labels."))
    _setting(models, models_form, t("Clean the transcript up first"),
             t("Keeps stamps and speaker labels."),
             window.meeting_cleanup)

    # --- recording ---------------------------------------------------------
    recording = SectionCard(t("Recording"))
    outer.addWidget(recording)
    recording_form = _CardForm(recording)
    window.meeting_max_minutes = QSpinBox()
    window.meeting_max_minutes.setRange(5, 600)
    window.meeting_max_minutes.setSuffix(t(" min"))
    _setting(recording, recording_form, t("Longest meeting"),
             t("Stops on its own at this length."),
             window.meeting_max_minutes)
    window.meeting_keep_audio = QCheckBox()
    window.meeting_keep_audio.setToolTip(t(
        "A run that fails keeps its recording either way, so it can be tried "
        "again from the Minutes tab. This is about the ones that worked."))
    _setting(recording, recording_form,
             t("Keep the recording after the minutes are written"),
             t("Failed runs keep it either way."),
             window.meeting_keep_audio)
    window.meeting_retention = _expanding(QSpinBox(), 160)
    window.meeting_retention.setRange(0, 365)
    window.meeting_retention.setSuffix(t(" days"))
    window.meeting_retention.setSpecialValueText(t("Never"))
    window.meeting_retention.setToolTip(t(
        "Recordings older than this are deleted when the app starts and "
        "after each meeting. The written minutes are never touched."))
    _setting(recording, recording_form, t("Delete recordings after"),
             t("Minutes are never touched."),
             window.meeting_retention)
    window._shortcut_row(
        recording_form, "meeting", t("Shortcut"),
        t("No global shortcut installed. The tray menu starts a meeting too."),
    )

    prompt_label = QLabel(t("System instruction given to the minutes model."))
    prompt_label.setWordWrap(True)
    outer.addWidget(prompt_label)
    window.meeting_prompt = QPlainTextEdit()
    window.meeting_prompt.setMinimumHeight(120)
    window.meeting_prompt.setMaximumHeight(180)
    outer.addWidget(window.meeting_prompt, 1)
    reset = btn(t("Reset to default"), "secondary", "sm")
    reset.clicked.connect(
        lambda: window.meeting_prompt.setPlainText(cfg.default_meeting_prompt()))
    outer.addWidget(reset, 0, Qt.AlignmentFlag.AlignRight)

    return scrolled(body)

"""Agent page: how the ask shortcut runs, the conversation and the answer."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
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

    window._shortcut_row() calls addRow(); settings_ui.py and tests call
    setRowVisible/isRowVisible. The shim maps each inner widget to its
    SettingRow wrapper and toggles both.
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


def _provider_card(card, title):
    """Attach QGroupBox-like title()/setTitle() to a SectionCard."""
    title_label = card.findChild(QLabel, "cardTitle")

    def _title():
        try:
            return title_label.text() if title_label is not None else title
        except Exception:
            return title

    def _set_title(text):
        try:
            if title_label is not None:
                title_label.setText(text)
        except Exception:
            pass

    card.title = _title
    card.setTitle = _set_title
    return card


def build(window):
    from settings_ui import (
        AGY_ASSISTANT_MODELS, ASSISTANT_MODELS, CODEX_MODELS, CODEX_SANDBOXES,
        PERMISSION_MODES, REASONING_LEVELS,
    )

    body, outer = page(
        t("Agent"),
        t("This shortcut records the same way dictation does, but the "
          "transcript is not what gets pasted. It goes to an agent as a "
          "command, and what comes back is pasted instead: the answer to a "
          "question, or a sentence saying what was done. Claude Code and "
          "Codex run as the session you would have opened yourself, with your "
          "skills, your connected services and your account."),
    )

    window.assistant_found = QLabel("")
    window.assistant_found.setWordWrap(True)
    outer.addWidget(window.assistant_found)

    how = SectionCard(t("How it runs"))
    outer.addWidget(how)
    how_form = window.how_form = _CardForm(how)
    window._shortcut_row(
        how_form, "ask", t("Shortcut"),
        t("No global shortcut installed. The tray menu asks it too."),
    )

    window.assistant_provider = _expanding(QComboBox(), 280)
    for label, value in window._assistant_choices():
        window.assistant_provider.addItem(label, value)
    window.assistant_provider.currentIndexChanged.connect(
        window._assistant_provider_changed)
    _setting(how, how_form, t("Runs on"),
             t("Which agent answers."),
             window.assistant_provider)

    window.assistant_dir = QLineEdit()
    window.assistant_dir.setPlaceholderText(os.path.expanduser("~"))
    browse = btn(t("Choose…"), "secondary", "sm")
    browse.clicked.connect(window._choose_assistant_dir)
    _setting(how, how_form, t("Working directory"),
             t("Which project it can see."),
             window._row(window.assistant_dir, browse))
    _note(how, how_form, InfoNote(t(
        "Your own skills and services are there whichever directory it is."),
        variant="info"))

    window.assistant_reasoning = _expanding(QComboBox(), 240)
    for label, value in REASONING_LEVELS:
        window.assistant_reasoning.addItem(t(label), value)
    window.assistant_reasoning.setToolTip(t("More thinking is slower."))
    _setting(how, how_form, t("Thinking"),
             t("Worth it for a job to work out, not look up."),
             window.assistant_reasoning)

    window.assistant_timeout = QSpinBox()
    window.assistant_timeout.setRange(15, 3600)
    window.assistant_timeout.setSuffix(t(" s"))
    window.assistant_timeout.setToolTip(t("A command running longer is given up on."))
    _setting(how, how_form, t("Give up after"),
             t("The tray menu can stop one earlier."),
             window.assistant_timeout)

    # --- per-provider boxes ---------------------------------------------
    window.claude_box = _provider_card(SectionCard(t("Claude Code")), t("Claude Code"))
    outer.addWidget(window.claude_box)
    window.assistant_model = QComboBox()
    window.assistant_model.setEditable(True)
    window.assistant_model.addItems(ASSISTANT_MODELS)
    window.assistant_model.setToolTip(t("“sonnet” always means the newest of that line."))
    window.refresh_assistant_claude_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_claude_models.clicked.connect(window._load_claude_models)
    _setting(window.claude_box, how_form, t("Model"),
             t("Opus thinks harder and answers slower."),
             window._row(window.assistant_model,
                          window.refresh_assistant_claude_models))
    # Model holder registered under how_form above is wrong card; re-register
    # under a dedicated map is unnecessary: visibility is via the whole box.
    window.assistant_permission = _expanding(QComboBox(), 320)
    for label, value in PERMISSION_MODES:
        window.assistant_permission.addItem(t(label), value)
    _setting(window.claude_box, how_form, t("Permissions"),
             t("What the agent may do unsupervised."),
             window.assistant_permission)

    window.codex_box = _provider_card(SectionCard(t("Codex")), t("Codex"))
    outer.addWidget(window.codex_box)
    window.assistant_codex_model = QComboBox()
    window.assistant_codex_model.setEditable(True)
    window.assistant_codex_model.addItem(t("Codex's own default"), "")
    for name in CODEX_MODELS:
        window.assistant_codex_model.addItem(name, name)
    window.refresh_assistant_codex_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_codex_models.clicked.connect(window._load_codex_models)
    _setting(window.codex_box, how_form, t("Model"),
             t("Codex model, or its own default."),
             window._row(window.assistant_codex_model,
                          window.refresh_assistant_codex_models))
    window.assistant_codex_sandbox = _expanding(QComboBox(), 320)
    for label, value in CODEX_SANDBOXES:
        window.assistant_codex_sandbox.addItem(t(label), value)
    _setting(window.codex_box, how_form, t("Sandbox"),
             t("What the agent may touch."),
             window.assistant_codex_sandbox)

    window.agy_box = _provider_card(SectionCard(t("Antigravity")), t("Antigravity"))
    outer.addWidget(window.agy_box)
    window.assistant_agy_model = QComboBox()
    window.assistant_agy_model.setEditable(True)
    window.assistant_agy_model.addItems(AGY_ASSISTANT_MODELS)
    window.refresh_assistant_agy_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_agy_models.clicked.connect(window._load_agy_models)
    _setting(window.agy_box, how_form, t("Model"),
             t("Slug carries the effort; shared thinking may not apply."),
             window._row(window.assistant_agy_model,
                          window.refresh_assistant_agy_models))
    window.agy_box.add(InfoNote(t(
        "Runs as the account you are signed in with, on this computer."),
        variant="info"))

    window.gateway_box = _provider_card(SectionCard(t("Gateway")), "")
    outer.addWidget(window.gateway_box)
    window.assistant_gateway_model = QComboBox()
    window.assistant_gateway_model.setEditable(True)
    window.refresh_assistant_gateway_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_gateway_models.clicked.connect(window._load_assistant_gateway_models)
    _setting(window.gateway_box, how_form, t("Model"),
             t("Plain question and answer over this gateway's key."),
             window._row(window.assistant_gateway_model,
                          window.refresh_assistant_gateway_models))
    window.gateway_box.add(InfoNote(t(
        "Runs no commands and opens no files; working directory and "
        "permissions above mean nothing here."), variant="info"))

    # --- conversation ----------------------------------------------------
    thread = SectionCard(t("The conversation"))
    outer.addWidget(thread)
    thread_form = _CardForm(thread)
    window.assistant_session_minutes = QSpinBox()
    window.assistant_session_minutes.setRange(0, 1440)
    window.assistant_session_minutes.setSuffix(t(" min"))
    window.assistant_session_minutes.setSpecialValueText(t("every command on its own"))
    _setting(thread, thread_form, t("Carry on for"),
             t("Commands this close are one conversation."),
             window.assistant_session_minutes)
    thread.add(InfoNote(t(
        "“and move that to Thursday” knows what “that” is; after it, fresh."),
        variant="info"))
    reset = btn(t("Start a new conversation now"), "secondary", "sm")
    reset.clicked.connect(window._reset_assistant_session)
    window.assistant_session_status = QLabel("")
    window.assistant_session_status.setWordWrap(True)
    thread_form.addRow(window._row(reset), window.assistant_session_status)

    # --- answer ----------------------------------------------------------
    answer = SectionCard(t("The answer"))
    outer.addWidget(answer)
    answer_form = _CardForm(answer)
    window.assistant_paste = QCheckBox()
    _setting(answer, answer_form, t("Paste it into the focused window"),
             t("Copied to the clipboard either way."),
             window.assistant_paste)
    window.assistant_cleanup = QCheckBox()
    _setting(answer, answer_form, t("Clean the transcript up before sending it"),
             t("Off saves an API call and a second or two."),
             window.assistant_cleanup)

    # --- prompt ----------------------------------------------------------
    prompt_label = QLabel(t(
        "Told to the agent alongside every command, on top of whatever your "
        "own configuration already says."))
    prompt_label.setWordWrap(True)
    outer.addWidget(prompt_label)
    window.assistant_prompt = QPlainTextEdit()
    window.assistant_prompt.setMinimumHeight(180)
    outer.addWidget(window.assistant_prompt, 1)
    reset_prompt = btn(t("Reset to default"), "secondary", "sm")
    reset_prompt.clicked.connect(
        lambda: window.assistant_prompt.setPlainText(cfg.default_assistant_prompt()))
    outer.addWidget(reset_prompt, 0, Qt.AlignmentFlag.AlignRight)

    return scrolled(body)

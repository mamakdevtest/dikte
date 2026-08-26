"""Agent page: how the ask shortcut runs, the conversation and the answer."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import btn
from . import page, scrolled


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

    how = QGroupBox(t("How it runs"))
    how_form = window.how_form = QFormLayout(how)
    how_form.setContentsMargins(20, 16, 20, 12)
    window._shortcut_row(
        how_form, "ask", t("Shortcut"),
        t("No global shortcut installed. The tray menu asks it too."),
    )

    window.assistant_provider = QComboBox()
    for label, value in window._assistant_choices():
        window.assistant_provider.addItem(label, value)
    window.assistant_provider.setFixedWidth(280)
    window.assistant_provider.currentIndexChanged.connect(
        window._assistant_provider_changed)
    how_form.addRow(t("Runs on"), window.assistant_provider)

    window.assistant_dir = QLineEdit()
    window.assistant_dir.setPlaceholderText(os.path.expanduser("~"))
    browse = btn(t("Choose…"), "secondary", "sm")
    browse.clicked.connect(window._choose_assistant_dir)
    how_form.addRow(t("Working directory"), window._row(window.assistant_dir, browse))
    dir_note = QLabel(t(
        "The directory the command runs in, which decides which project's "
        "instructions and files it can see. Your own skills and services "
        "are there whichever one it is."))
    dir_note.setWordWrap(True)
    how_form.addRow(dir_note)

    window.assistant_reasoning = QComboBox()
    for label, value in REASONING_LEVELS:
        window.assistant_reasoning.addItem(t(label), value)
    window.assistant_reasoning.setFixedWidth(240)
    window.assistant_reasoning.setToolTip(t(
        "More thinking is slower, and you are standing in front of the "
        "screen while it happens. Worth it for a job that has to be worked "
        "out rather than looked up."))
    how_form.addRow(t("Thinking"), window.assistant_reasoning)

    window.assistant_timeout = QSpinBox()
    window.assistant_timeout.setRange(15, 3600)
    window.assistant_timeout.setSuffix(t(" s"))
    window.assistant_timeout.setToolTip(t(
        "A command still running after this is given up on. The tray menu "
        "can stop one earlier."))
    how_form.addRow(t("Give up after"), window.assistant_timeout)
    outer.addWidget(how)

    # --- per-provider boxes ---------------------------------------------
    window.claude_box = QGroupBox(t("Claude Code"))
    claude_form = QFormLayout(window.claude_box)
    claude_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_model = QComboBox()
    window.assistant_model.setEditable(True)
    window.assistant_model.addItems(ASSISTANT_MODELS)
    window.assistant_model.setToolTip(t(
        "A name like “sonnet” always means the newest model of that line. "
        "Opus thinks harder and answers slower, which is felt here more "
        "than anywhere else: you are standing in front of the screen."))
    window.refresh_assistant_claude_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_claude_models.clicked.connect(window._load_claude_models)
    claude_form.addRow(t("Model"), window._row(
        window.assistant_model, window.refresh_assistant_claude_models))
    window.assistant_permission = QComboBox()
    for label, value in PERMISSION_MODES:
        window.assistant_permission.addItem(t(label), value)
    window.assistant_permission.setFixedWidth(320)
    claude_form.addRow(t("Permissions"), window.assistant_permission)
    outer.addWidget(window.claude_box)

    window.codex_box = QGroupBox(t("Codex"))
    codex_form = QFormLayout(window.codex_box)
    codex_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_codex_model = QComboBox()
    window.assistant_codex_model.setEditable(True)
    window.assistant_codex_model.addItem(t("Codex's own default"), "")
    for name in CODEX_MODELS:
        window.assistant_codex_model.addItem(name, name)
    window.refresh_assistant_codex_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_codex_models.clicked.connect(window._load_codex_models)
    codex_form.addRow(t("Model"), window._row(
        window.assistant_codex_model, window.refresh_assistant_codex_models))
    window.assistant_codex_sandbox = QComboBox()
    for label, value in CODEX_SANDBOXES:
        window.assistant_codex_sandbox.addItem(t(label), value)
    window.assistant_codex_sandbox.setFixedWidth(320)
    codex_form.addRow(t("Sandbox"), window.assistant_codex_sandbox)
    outer.addWidget(window.codex_box)

    window.agy_box = QGroupBox(t("Antigravity"))
    agy_form = QFormLayout(window.agy_box)
    agy_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_agy_model = QComboBox()
    window.assistant_agy_model.setEditable(True)
    window.assistant_agy_model.addItems(AGY_ASSISTANT_MODELS)
    window.refresh_assistant_agy_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_assistant_agy_models.clicked.connect(window._load_agy_models)
    agy_form.addRow(t("Model"), window._row(window.assistant_agy_model,
                                            window.refresh_assistant_agy_models))
    agy_note = QLabel(t(
        "Antigravity runs as the account you are signed in with, on the "
        "computer it is installed on. Its model names are slugs that carry "
        "the effort, so the shared thinking setting only applies to the "
        "ones that left it out."))
    agy_note.setWordWrap(True)
    agy_form.addRow(agy_note)
    outer.addWidget(window.agy_box)

    window.gateway_box = QGroupBox("")
    gateway_form = QFormLayout(window.gateway_box)
    gateway_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_gateway_model = QComboBox()
    window.assistant_gateway_model.setEditable(True)
    gateway_form.addRow(t("Model"), window.assistant_gateway_model)
    gateway_note = QLabel(t(
        "A plain question and a plain answer, over this gateway's own key. "
        "It runs no commands, opens no files and reaches none of your "
        "services, so it can tell you what the capital of Peru is but not "
        "what is in your calendar. Working directory and permissions above "
        "mean nothing here."))
    gateway_note.setWordWrap(True)
    gateway_form.addRow(gateway_note)
    outer.addWidget(window.gateway_box)

    # --- conversation ----------------------------------------------------
    thread = QGroupBox(t("The conversation"))
    thread_form = QFormLayout(thread)
    thread_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_session_minutes = QSpinBox()
    window.assistant_session_minutes.setRange(0, 1440)
    window.assistant_session_minutes.setSuffix(t(" min"))
    window.assistant_session_minutes.setSpecialValueText(t("every command on its own"))
    thread_form.addRow(t("Carry on for"), window.assistant_session_minutes)
    thread_note = QLabel(t(
        "Commands within this long of each other are one conversation, so "
        "“and move that to Thursday” knows what “that” is. After it, the "
        "next command starts fresh."))
    thread_note.setWordWrap(True)
    thread_form.addRow(thread_note)
    reset = btn(t("Start a new conversation now"), "secondary", "sm")
    reset.clicked.connect(window._reset_assistant_session)
    window.assistant_session_status = QLabel("")
    window.assistant_session_status.setWordWrap(True)
    thread_form.addRow(window._row(reset), window.assistant_session_status)
    outer.addWidget(thread)

    # --- answer ----------------------------------------------------------
    answer = QGroupBox(t("The answer"))
    answer_form = QFormLayout(answer)
    answer_form.setContentsMargins(20, 16, 20, 12)
    window.assistant_paste = QCheckBox(t("Paste it into the focused window"))
    window.assistant_paste.setToolTip(t("It is copied to the clipboard either way."))
    answer_form.addRow("", window.assistant_paste)
    window.assistant_cleanup = QCheckBox(t("Clean the transcript up before sending it"))
    window.assistant_cleanup.setToolTip(t(
        "Off by default: Claude reads through “erm” and “you know” without "
        "help, and cleanup costs an API call and a second or two."))
    answer_form.addRow("", window.assistant_cleanup)
    outer.addWidget(answer)

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

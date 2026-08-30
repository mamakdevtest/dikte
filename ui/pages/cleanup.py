"""Cleanup rules page: the two prompt sets and the names/terms glossary."""

from PyQt6.QtWidgets import QLabel, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

import config as cfg
from i18n import t

from . import page, scrolled


def build(window):
    body, outer = page(
        t("Cleanup rules"),
        t("System instructions given to the cleanup model; this is where you "
          "decide how much it may touch your words."),
    )

    # --- AI Text Processing controls — single Editing Level only ---
    from PyQt6.QtWidgets import QGroupBox, QFormLayout, QHBoxLayout, QSpinBox, QLabel
    ai_box = QGroupBox(t("AI Text Processing"))
    ai_form = QFormLayout(ai_box)
    ai_form.setContentsMargins(20, 16, 20, 12)
    # Editing Level 1..5 — sole policy (Shortening Freedom removed, folded into level)
    from ..widgets import SegmentedControl
    window.ai_edit_level = SegmentedControl([
        (t("1 Minimum"), 1), (t("2 Light"), 2), (t("3 Balanced"), 3), (t("4 Free"), 4), (t("5 Intensive"), 5)
    ], on_change=lambda v: window._ai_edit_changed(v) if hasattr(window, "_ai_edit_changed") else None)
    # Also keep a spin for accessibility / test
    window.ai_edit_spin = QSpinBox()
    window.ai_edit_spin.setRange(1, 5)
    window.ai_edit_spin.setVisible(False)
    ai_form.addRow(t("Editing Level"), window.ai_edit_level)
    window.ai_edit_desc = QLabel("")
    window.ai_edit_desc.setWordWrap(True)
    window.ai_edit_desc.setProperty("note", "info")
    ai_form.addRow(window.ai_edit_desc)
    outer.addWidget(ai_box)

    inner = QTabWidget()
    inner.setDocumentMode(True)
    window.cleanup_prompt = window._prompt_page(
        inner, t("Dictation"),
        t("System instruction given to the cleanup model. This is where you "
          "decide how much it may touch your words."),
        cfg.default_cleanup_prompt,
    )
    window.file_cleanup_prompt = window._prompt_page(
        inner, t("Audio file"),
        t("Used instead when an audio or video file is cleaned up. It is "
          "written for subtitles: lines stay where they are, nothing is "
          "shortened, and misheard words are repaired from the context."),
        cfg.default_file_cleanup_prompt,
    )
    outer.addWidget(inner, 1)

    hint = QLabel(t("Names and terms you say often (optional). They go to the "
                    "transcription model as a hint, and to the cleanup model as a "
                    "glossary, so it can repair the ones that still come out wrong."))
    hint.setWordWrap(True)
    hint.setProperty("note", "info")
    outer.addWidget(hint)
    window.transcribe_prompt = QPlainTextEdit()
    window.transcribe_prompt.setMaximumHeight(90)
    outer.addWidget(window.transcribe_prompt)

    return scrolled(body)

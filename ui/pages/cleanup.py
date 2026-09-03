"""Cleanup rules page: the two prompt sets and the names/terms glossary."""

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QSpinBox, QTabWidget, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import (
    InfoNote, SectionCard, SegmentedControl, SettingRow, ToggleSwitch,
)
from . import page, scrolled


def _padded(widget):
    """Card-body padding for widgets that carry none of their own."""
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(20, 0, 20, 8)
    lay.addWidget(widget, 1)
    return wrap


def build(window):
    body, outer = page(
        t("Cleanup rules"),
        t("System instruction given to the cleanup model. This is where you "
          "decide how much it may touch your words."),
    )

    # --- Custom-prompt opt-in: single gate for both editors ---
    window.cleanup_custom_enabled = ToggleSwitch()
    outer.addWidget(SectionCard(
        t("Do you want to create a custom prompt?"),
        t("Off: the default correction runs. On: your prompts below run."),
        window.cleanup_custom_enabled,
    ))

    # --- AI Text Processing controls — single Editing Level only ---
    # Editing Level 1..5 — sole policy (Shortening Freedom removed, folded into level)
    ai_card = SectionCard(t("AI Text Processing"))
    outer.addWidget(ai_card)
    window.ai_edit_level = SegmentedControl([
        (t("1 Minimum"), 1), (t("2 Light"), 2), (t("3 Balanced"), 3),
        (t("4 Free"), 4), (t("5 Intensive"), 5),
    ], on_change=lambda v: window._ai_edit_changed(v)
        if hasattr(window, "_ai_edit_changed") else None)
    ai_card.add(SettingRow(
        t("Editing Level"),
        t("How much the model may rewrite your words.")))
    # Full-width row below the label: five segments never fit beside it.
    ai_card.add(_padded(window.ai_edit_level))
    # Accessibility / test mirror of the segmented control; never shown.
    window.ai_edit_spin = QSpinBox()
    window.ai_edit_spin.setRange(1, 5)
    window.ai_edit_spin.setParent(body)
    window.ai_edit_spin.hide()
    window.ai_edit_desc = QLabel("")
    window.ai_edit_desc.setWordWrap(True)
    window.ai_edit_desc.setProperty("note", "info")
    ai_card.add(_padded(window.ai_edit_desc))

    inner = QTabWidget()
    inner.setDocumentMode(True)
    window.cleanup_prompt_tabs = inner
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
    inner.setEnabled(window.cleanup_custom_enabled.isChecked())
    try:
        window.cleanup_custom_enabled.toggled.connect(inner.setEnabled)
    except Exception:
        pass

    glossary = SectionCard(t("Names and terms"))
    outer.addWidget(glossary)
    glossary.add(_padded(InfoNote(
        t("Names and terms you say often (optional). They go to the "
          "transcription model as a hint, and to the cleanup model as a "
          "glossary, so it can repair the ones that still come out wrong."),
        variant="info")))
    window.transcribe_prompt = QPlainTextEdit()
    window.transcribe_prompt.setMaximumHeight(90)
    glossary.add(_padded(window.transcribe_prompt))

    return scrolled(body)

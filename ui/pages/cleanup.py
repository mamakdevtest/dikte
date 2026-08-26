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

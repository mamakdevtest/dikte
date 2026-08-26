"""Audio file page: pick a file, choose options, run and export."""

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from i18n import t

from ..widgets import btn
from . import page, scrolled


def build(window):
    body, outer = page(
        t("Audio file"),
        t("Transcribe an existing audio or video file with the same models."),
    )

    pick = btn(t("Choose file…"), "secondary")
    pick.clicked.connect(window._choose_file)
    window.file_label = QLabel(t("No file selected"))
    window.file_label.setWordWrap(True)
    row = QHBoxLayout()
    row.addWidget(pick)
    row.addWidget(window.file_label, 1)
    outer.addLayout(row)

    window.file_timestamps = QCheckBox(t("Add timestamps"))
    window.file_timestamps.setToolTip(
        t("Prefixes every segment with [mm:ss]. Uses whisper-1 on whichever "
          "provider you picked, the only model that returns segment times."))
    outer.addWidget(window.file_timestamps)

    window.file_cleanup = QCheckBox(t("Run the cleanup model afterwards"))
    window.file_cleanup.setToolTip(
        t("With its own rules, under Cleanup rules: written for subtitles, so "
          "the lines keep their place and nothing is shortened."))
    outer.addWidget(window.file_cleanup)

    window.file_run = btn(t("Transcribe"), "ink")
    window.file_run.clicked.connect(window._run_file)
    window.file_stop = btn(t("Stop"), "secondary")
    window.file_stop.clicked.connect(window._stop_file)
    window.file_stop.setEnabled(False)
    run_row = QHBoxLayout()
    run_row.addWidget(window.file_run)
    run_row.addWidget(window.file_stop)
    run_row.addStretch(1)
    outer.addLayout(run_row)

    window.file_status = QLabel("")
    window.file_status.setWordWrap(True)
    outer.addWidget(window.file_status)

    window.file_output = QPlainTextEdit()
    window.file_output.setPlaceholderText("…")
    outer.addWidget(window.file_output, 1)

    copy = btn(t("Copy"), "secondary", "sm")
    copy.clicked.connect(
        lambda: QGuiApplication.clipboard().setText(window.file_output.toPlainText()))
    save = btn(t("Save as .txt"), "secondary", "sm")
    save.clicked.connect(window._save_transcript)
    window.file_save_srt = btn(t("Save as .srt"), "secondary", "sm")
    window.file_save_srt.setToolTip(
        t("Subtitles, timed from the segments. Needs the timestamps option."))
    window.file_save_srt.setEnabled(False)
    window.file_save_srt.clicked.connect(window._save_subtitles)
    out_row = QHBoxLayout()
    out_row.addWidget(copy)
    out_row.addWidget(save)
    out_row.addWidget(window.file_save_srt)
    out_row.addStretch(1)
    outer.addLayout(out_row)

    return scrolled(body)

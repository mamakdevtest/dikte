"""Audio file page: pick a file, choose options, run and export."""

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QWidget,
)

from i18n import t

from ..widgets import InfoNote, SectionCard, SettingRow, btn
from . import page, scrolled


def _padded(widget):
    """A card-body row with the same 20/12 padding SettingRow uses."""
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(20, 12, 20, 12)
    lay.setSpacing(8)
    lay.addWidget(widget, 1)
    return wrap


def build(window):
    body, outer = page(
        t("Audio file"),
        t("Transcribe an existing audio or video file with the same models."),
    )
    if not hasattr(window, "file_path"):
        window.file_path = ""

    # --- source ---------------------------------------------------------
    source = SectionCard(t("Source file"))
    outer.addWidget(source)
    pick = btn(t("Choose file…"), "secondary")
    pick.clicked.connect(window._choose_file)
    window.file_label = QLabel(t("No file selected"))
    window.file_label.setWordWrap(True)
    row = QWidget()
    row_lay = QHBoxLayout(row)
    row_lay.setContentsMargins(20, 12, 20, 12)
    row_lay.setSpacing(8)
    row_lay.addWidget(pick)
    row_lay.addWidget(window.file_label, 1)
    source.add(row)

    # --- options (per-file; persisted without Save) ----------------------
    options = SectionCard(t("Options"))
    outer.addWidget(options)
    window.file_timestamps = QCheckBox()
    window.file_timestamps.setToolTip(
        t("Prefixes every segment with [mm:ss]. Uses whisper-1 on whichever "
          "provider you picked, the only model that returns segment times."))
    options.add(SettingRow(
        t("Add timestamps"),
        t("Prefixes every segment with [mm:ss]. Uses whisper-1 on whichever "
          "provider you picked, the only model that returns segment times."),
        window.file_timestamps))

    window.file_cleanup = QCheckBox()
    window.file_cleanup.setToolTip(
        t("With its own rules, under Cleanup rules: written for subtitles, so "
          "the lines keep their place and nothing is shortened."))
    options.add(SettingRow(
        t("Run the cleanup model afterwards"),
        t("With its own rules, under Cleanup rules: written for subtitles, so "
          "the lines keep their place and nothing is shortened."),
        window.file_cleanup))

    # --- transcription ---------------------------------------------------
    result = SectionCard(t("Transcript"))
    outer.addWidget(result)

    window.file_run = btn(t("Transcribe"), "ink")
    window.file_run.clicked.connect(window._run_file)
    window.file_stop = btn(t("Stop"), "secondary")
    window.file_stop.clicked.connect(window._stop_file)
    window.file_stop.setEnabled(False)
    run_row = QWidget()
    run_lay = QHBoxLayout(run_row)
    run_lay.setContentsMargins(20, 12, 20, 4)
    run_lay.setSpacing(8)
    run_lay.addWidget(window.file_run)
    run_lay.addWidget(window.file_stop)
    run_lay.addStretch(1)
    result.add(run_row)

    window.file_status = QLabel("")
    window.file_status.setWordWrap(True)
    result.add(_padded(window.file_status))

    window.file_output = QPlainTextEdit()
    window.file_output.setPlaceholderText("…")
    window.file_output.setMinimumHeight(160)
    result.add(_padded(window.file_output))

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
    out_row = QWidget()
    out_lay = QHBoxLayout(out_row)
    out_lay.setContentsMargins(20, 4, 20, 4)
    out_lay.setSpacing(8)
    out_lay.addWidget(copy)
    out_lay.addWidget(save)
    out_lay.addWidget(window.file_save_srt)
    out_lay.addStretch(1)
    result.add(out_row)
    result.add(InfoNote(
        t("Subtitles, timed from the segments. Needs the timestamps option."),
        variant="info"))

    return scrolled(body)

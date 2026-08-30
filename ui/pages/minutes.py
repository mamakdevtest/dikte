"""Minutes page: the meeting list and the minutes viewer."""

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QPlainTextEdit,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import btn
from . import page, scrolled


class MarkdownView(QTextBrowser):
    """The minutes viewer: renders Markdown in Preview mode, raw source in Source mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._md_raw = ""
        self._md_source = False
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)

    def set_markdown(self, text):
        """Remember the raw Markdown and show it (rendered, unless Source mode is on)."""
        self._md_raw = text or ""
        if self._md_source:
            self.setPlainText(self._md_raw)
        else:
            self.setMarkdown(self._md_raw)

    def set_source_mode(self, on):
        """Preview → rendered Markdown; Source → the raw text as it was fed in."""
        self._md_source = bool(on)
        if self._md_source:
            self.setPlainText(self._md_raw)
        else:
            self.setMarkdown(self._md_raw)

    def clear(self):
        self._md_raw = ""
        super().clear()


def build(window):
    body, outer = page(
        t("Minutes"),
        t("Recorded meetings and the minutes written from them."),
    )

    window.minutes_list = QListWidget()
    window.minutes_list.setWordWrap(True)
    window.minutes_list.setMaximumHeight(170)
    window.minutes_list.currentItemChanged.connect(window._show_minutes)
    outer.addWidget(window.minutes_list)

    # Style picker + AI-auto + Preview/Source toggle
    style_row = QHBoxLayout()
    window.minutes_style_label = QLabel("")
    window.minutes_style_label.setObjectName("meta")
    style_row.addWidget(window.minutes_style_label)
    style_row.addStretch(1)
    window.minutes_auto = QCheckBox(t("AI picks the best format"))
    window.minutes_auto.setChecked(True)
    window.minutes_style = QComboBox()
    for key in cfg.STYLE_KEYS:
        window.minutes_style.addItem(
            cfg.STYLE_LABELS_TR.get(key, key), key)
    window.minutes_style.setEnabled(False)

    def _on_auto_toggled(checked):
        window.minutes_style.setEnabled(not checked)

    window.minutes_auto.toggled.connect(_on_auto_toggled)
    style_row.addWidget(window.minutes_auto)
    style_row.addWidget(QLabel(t("Format")))
    style_row.addWidget(window.minutes_style)
    window.minutes_view_toggle = QComboBox()
    window.minutes_view_toggle.addItem(t("Preview"), "preview")
    window.minutes_view_toggle.addItem(t("Source"), "source")
    window.minutes_view_toggle.setCurrentIndex(0)
    window.minutes_view_toggle.currentIndexChanged.connect(
        lambda: window.minutes_view.set_source_mode(
            window.minutes_view_toggle.currentData() == "source"))
    style_row.addWidget(window.minutes_view_toggle)
    outer.addLayout(style_row)

    window.minutes_status = QLabel("")
    window.minutes_status.setWordWrap(True)
    outer.addWidget(window.minutes_status)

    tabs = QTabWidget()
    window.minutes_view = MarkdownView()
    window.minutes_view.setPlaceholderText(t("Pick a meeting to read it."))
    window.minutes_raw_view = QPlainTextEdit()
    window.minutes_raw_view.setReadOnly(True)
    window.minutes_raw_view.setPlaceholderText(t("Raw transcript (hammadde) — original before AI cleanup."))
    tabs.addTab(window.minutes_view, t("Minutes"))
    tabs.addTab(window.minutes_raw_view, t("Raw (hammadde)"))
    window.minutes_tabs = tabs
    outer.addWidget(tabs, 1)

    copy = btn(t("Copy"), "secondary", "sm")
    copy.clicked.connect(
        lambda: QGuiApplication.clipboard().setText(window.minutes_view.toPlainText()))
    window.minutes_retry = btn(t("Write it up"), "secondary", "sm")
    window.minutes_retry.clicked.connect(window._retry_minutes)
    window.minutes_retry.setEnabled(False)
    try:
        window.minutes_polish = btn(t("Polish with AI"), "secondary", "sm")
        window.minutes_polish.clicked.connect(window._polish_minutes)
        window.minutes_polish.setEnabled(False)
        outer.addWidget(window.minutes_polish)
    except Exception:
        pass
    save_md = btn(t("Save as .md"), "secondary", "sm")
    save_md.clicked.connect(window._save_minutes_md)
    folder = btn(t("Open the folder"), "secondary", "sm")
    folder.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(cfg.MEETINGS_DIR))))
    delete = btn(t("Delete selected"), "danger", "sm")
    delete.clicked.connect(window._delete_minutes)
    reload_ = btn(t("Reload"), "secondary", "sm")
    reload_.clicked.connect(window._load_minutes)
    row = QHBoxLayout()
    row.addWidget(copy)
    row.addWidget(window.minutes_retry)
    row.addWidget(save_md)
    row.addStretch(1)
    row.addWidget(folder)
    row.addWidget(delete)
    row.addWidget(reload_)
    outer.addLayout(row)

    return scrolled(body)
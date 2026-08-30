"""Minutes page: the meeting list and the minutes viewer."""

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QPlainTextEdit, QVBoxLayout, QWidget,
)

import config as cfg
from i18n import t

from ..widgets import btn
from . import page, scrolled


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

    window.minutes_status = QLabel("")
    window.minutes_status.setWordWrap(True)
    outer.addWidget(window.minutes_status)

    from PyQt6.QtWidgets import QTabWidget
    tabs = QTabWidget()
    window.minutes_view = QPlainTextEdit()
    window.minutes_view.setReadOnly(True)
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

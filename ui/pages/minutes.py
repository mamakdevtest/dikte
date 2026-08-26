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

    window.minutes_view = QPlainTextEdit()
    window.minutes_view.setReadOnly(True)
    window.minutes_view.setPlaceholderText(t("Pick a meeting to read it."))
    outer.addWidget(window.minutes_view, 1)

    copy = btn(t("Copy"), "secondary", "sm")
    copy.clicked.connect(
        lambda: QGuiApplication.clipboard().setText(window.minutes_view.toPlainText()))
    window.minutes_retry = btn(t("Write it up"), "secondary", "sm")
    window.minutes_retry.clicked.connect(window._retry_minutes)
    window.minutes_retry.setEnabled(False)
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
    row.addStretch(1)
    row.addWidget(folder)
    row.addWidget(delete)
    row.addWidget(reload_)
    outer.addLayout(row)

    return scrolled(body)

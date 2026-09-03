"""History page: the entry list, the limit and the batch actions."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QListWidget, QSpinBox, QWidget,
)

from i18n import t

from ..widgets import SectionCard, SettingRow, btn
from . import page, scrolled


def build(window):
    body, outer = page(
        t("History"),
        t("Every dictation and agent command, kept on this computer."),
    )

    # Voice jobs retry section (failed but recoverable jobs)
    try:
        jobs = SectionCard(t("Failed but recoverable"))
        window._voice_jobs_group = jobs
        window.voice_jobs_list = QListWidget()
        window.voice_jobs_list.setWordWrap(True)
        window.voice_jobs_list.setMaximumHeight(110)
        jobs.add(_padded(window.voice_jobs_list))
        window.voice_jobs_retry_btn = btn(t("Retry"), "secondary", "sm")
        window.voice_jobs_retry_btn.clicked.connect(
            lambda: getattr(window, "_retry_voice_job", lambda: None)())
        window.voice_jobs_refresh_btn = btn(t("Reload"), "secondary", "sm")
        window.voice_jobs_refresh_btn.clicked.connect(
            lambda: getattr(window, "_load_voice_jobs", lambda: None)())
        vj_row = QWidget()
        vj_lay = QHBoxLayout(vj_row)
        vj_lay.setContentsMargins(20, 4, 20, 12)
        vj_lay.setSpacing(8)
        vj_lay.addWidget(window.voice_jobs_retry_btn)
        vj_lay.addWidget(window.voice_jobs_refresh_btn)
        vj_lay.addStretch(1)
        jobs.add(vj_row)
        outer.addWidget(jobs)
    except Exception:
        pass

    entries = SectionCard()
    outer.addWidget(entries)

    window.history = QListWidget()
    window.history.setWordWrap(True)
    window.history.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    window.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history.customContextMenuRequested.connect(window._history_menu)
    window.history.itemDoubleClicked.connect(window._show_history_details)
    delete_key = QShortcut(QKeySequence.StandardKey.Delete, window.history)
    delete_key.setContext(Qt.ShortcutContext.WidgetShortcut)
    delete_key.activated.connect(window._delete_history)
    entries.add(_padded(window.history, top=12, bottom=4))

    window.history_limit = QSpinBox()
    window.history_limit.setRange(0, 10000)
    window.history_limit.setSpecialValueText(t("no limit"))
    window.history_limit.setSuffix(t(" entries"))
    window.history_limit.setToolTip(t(
        "Once the history passes this many entries, the oldest one is dropped "
        "every time a new one arrives. Set it to 0 to keep everything."))
    entries.add(SettingRow(
        t("Keep at most"),
        t("Once the history passes this many entries, the oldest one is dropped "
          "every time a new one arrives. Set it to 0 to keep everything."),
        window.history_limit))

    copy = btn(t("Copy selected to clipboard"), "secondary", "sm")
    copy.clicked.connect(window._copy_history)
    delete = btn(t("Delete selected"), "danger", "sm")
    delete.clicked.connect(window._delete_history)
    clear = btn(t("Clear history"), "danger", "sm")
    clear.clicked.connect(window._clear_history)
    reload_ = btn(t("Reload"), "secondary", "sm")
    reload_.clicked.connect(window._load_history)
    row = QWidget()
    row_lay = QHBoxLayout(row)
    row_lay.setContentsMargins(20, 12, 20, 12)
    row_lay.setSpacing(8)
    row_lay.addWidget(copy)
    row_lay.addWidget(delete)
    row_lay.addStretch(1)
    row_lay.addWidget(clear)
    row_lay.addWidget(reload_)
    entries.add(row)

    return scrolled(body)


def _padded(widget, top=12, bottom=12):
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(20, top, 20, bottom)
    lay.setSpacing(8)
    lay.addWidget(widget, 1)
    return wrap

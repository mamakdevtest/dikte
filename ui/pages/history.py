"""History page: the entry list, the limit and the batch actions."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QSpinBox, QVBoxLayout,
    QWidget,
)

from i18n import t

from ..widgets import btn
from . import page, scrolled


def build(window):
    body, outer = page(
        t("History"),
        t("Every dictation and agent command, kept on this computer."),
    )

    # Voice jobs retry section (failed but recoverable jobs)
    try:
        from PyQt6.QtWidgets import QGroupBox
        window._voice_jobs_group = QGroupBox(t("Failed but recoverable"))
        vj_layout = QVBoxLayout(window._voice_jobs_group)
        from PyQt6.QtWidgets import QListWidget as _LW
        window.voice_jobs_list = _LW()
        window.voice_jobs_list.setWordWrap(True)
        window.voice_jobs_list.setMaximumHeight(110)
        vj_layout.addWidget(window.voice_jobs_list)
        from PyQt6.QtWidgets import QHBoxLayout as _HL
        vj_row = _HL()
        window.voice_jobs_retry_btn = btn(t("Retry"), "secondary", "sm")
        window.voice_jobs_retry_btn.clicked.connect(
            lambda: getattr(window, "_retry_voice_job", lambda: None)())
        window.voice_jobs_refresh_btn = btn(t("Reload"), "secondary", "sm")
        window.voice_jobs_refresh_btn.clicked.connect(
            lambda: getattr(window, "_load_voice_jobs", lambda: None)())
        vj_row.addWidget(window.voice_jobs_retry_btn)
        vj_row.addWidget(window.voice_jobs_refresh_btn)
        vj_row.addStretch(1)
        vj_layout.addLayout(vj_row)
        outer.addWidget(window._voice_jobs_group)
    except Exception:
        pass

    window.history = QListWidget()
    window.history.setWordWrap(True)
    window.history.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    window.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history.customContextMenuRequested.connect(window._history_menu)
    window.history.itemDoubleClicked.connect(window._show_history_details)
    delete_key = QShortcut(QKeySequence.StandardKey.Delete, window.history)
    delete_key.setContext(Qt.ShortcutContext.WidgetShortcut)
    delete_key.activated.connect(window._delete_history)
    outer.addWidget(window.history, 1)

    window.history_limit = QSpinBox()
    window.history_limit.setRange(0, 10000)
    window.history_limit.setSpecialValueText(t("no limit"))
    window.history_limit.setSuffix(t(" entries"))
    window.history_limit.setToolTip(t(
        "Once the history passes this many entries, the oldest one is dropped "
        "every time a new one arrives. Set it to 0 to keep everything."))
    limit_row = QHBoxLayout()
    limit_row.addWidget(QLabel(t("Keep at most")))
    limit_row.addWidget(window.history_limit)
    limit_row.addStretch(1)
    outer.addLayout(limit_row)

    copy = btn(t("Copy selected to clipboard"), "secondary", "sm")
    copy.clicked.connect(window._copy_history)
    delete = btn(t("Delete selected"), "danger", "sm")
    delete.clicked.connect(window._delete_history)
    clear = btn(t("Clear history"), "danger", "sm")
    clear.clicked.connect(window._clear_history)
    reload_ = btn(t("Reload"), "secondary", "sm")
    reload_.clicked.connect(window._load_history)
    row = QHBoxLayout()
    row.addWidget(copy)
    row.addWidget(delete)
    row.addStretch(1)
    row.addWidget(clear)
    row.addWidget(reload_)
    outer.addLayout(row)

    return scrolled(body)

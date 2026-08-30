"""Settings window.

The window is a QDialog hosting the two-column AppShell from ``ui.shell``: a
sidebar (brand, nav, engine card, theme toggle) drives a hidden-tab QTabWidget
whose pages are built by the ``ui.pages`` modules. All the behaviour — the
provider registry, the save/load round trip, the fetches and tests — stays on
``SettingsWindow``, so the widget attributes the tests reach are unchanged.
"""

import json
import os
import re
import shutil
import sys
import threading

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
    QInputDialog,
)

# Prevent accidental wheel changes when hovering dropdowns without focus
try:
    _orig_combo_wheel = QComboBox.wheelEvent
    def _combo_wheel_no_accidental(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        _orig_combo_wheel(self, event)
    QComboBox.wheelEvent = _combo_wheel_no_accidental
except Exception:
    pass

import api
import assistant
import audio
import cleanup
import config as cfg
import filetranscribe
import ggml
import hotkey
import ipc
import meeting
import paste
import providers
from filetranscribe import FileTranscriber
from i18n import t

from ui import theme as _theme
from ui.local_models import LocalModelBox
from ui.shell import AppShell, NAV as _NAV
from ui.pages import (
    agent as agent_page,
    audiofile as audiofile_page,
    cleanup as cleanup_page,
    general as general_page,
    history as history_page,
    meeting as meeting_page,
    minutes as minutes_page,
    providers as providers_page,
    shortcuts as shortcuts_page,
)

UI_LANGUAGES = [("Automatic (system)", "auto"), ("Turkish", "tr"), ("English", "en")]
LANGUAGES = [
    ("Detect automatically", "auto"), ("Turkish", "tr"), ("English", "en"),
    ("German", "de"), ("French", "fr"), ("Spanish", "es"), ("Arabic", "ar"),
]
CORNERS = ["bottom-left", "bottom-right", "top-left", "top-right"]
TRANSCRIBE_MODELS = {
    "openai": ["gpt-4o-transcribe", "gpt-4o-mini-transcribe", "whisper-1"],
    "groq": ["whisper-large-v3-turbo", "whisper-large-v3"],
    "deepgram": ["nova-3", "nova-2", "base", "enhanced"],
}
CLEANUP_MODELS = [
    "google/gemini-3.5-flash-lite", "google/gemini-3.1-flash-lite",
    "google/gemini-2.5-flash-lite", "anthropic/claude-haiku-4.5",
    "openai/gpt-5-mini", "meta-llama/llama-3.3-70b-instruct",
]
CLEANUP_CLAUDE_MODELS = ["haiku", "sonnet", "opus", "fable"]
MEETING_MODELS = [
    "google/gemini-3.5-flash", "google/gemini-3.1-pro-preview",
    "anthropic/claude-sonnet-5", "openai/gpt-5.4", "x-ai/grok-4.5",
]
AGY_CLEANUP_MODELS = [
    "gemini-3.6-flash-medium", "gemini-3.6-flash-low", "gemini-3.6-flash-high",
]
AGY_ASSISTANT_MODELS = [
    "gemini-3.1-pro-high", "gemini-3.1-pro-medium", "gemini-3.1-pro-low",
]
ASSISTANT_MODELS = ["sonnet", "opus", "haiku", "fable"]
CODEX_MODELS = providers.CODEX_FIXED_MODELS
PERMISSION_MODES = [
    ("Decide on its own, with the safety checks on", "auto"),
    ("Allow everything", "bypassPermissions"),
    ("Only what needs no permission", "manual"),
]
CODEX_SANDBOXES = [
    ("Read anything, write in the working directory", "workspace-write"),
    ("Read only", "read-only"),
    ("No sandbox at all", "danger-full-access"),
]
MEETING_STATUS = {
    "recorded": "waiting to be written up",
    "transcribed": "transcript ready, minutes missing",
    "failed": "failed",
}
REASONING_LEVELS = [
    ("Model's own default", ""), ("Off", "none"), ("Minimal", "minimal"),
    ("Low", "low"), ("Medium", "medium"), ("High", "high"),
    ("Very high", "xhigh"), ("Maximum", "max"),
]
SHORTCUTS = [
    "Ctrl+Space", "Ctrl+Alt+Space", "Ctrl+Shift+Space", "Meta+Space",
    "Ctrl+Alt+A", "Ctrl+Alt+D", "Ctrl+Alt+M", "Ctrl+Alt+Q",
    "Meta+A", "Meta+D", "Meta+M",
    "Ctrl+Alt+F1", "Ctrl+Alt+F2", "Ctrl+Alt+F3",
]
WIN_SHORTCUTS = [
    "Ctrl+Space", "Ctrl+Alt+Space", "Ctrl+Shift+Space",
    "Alt+Space", "Ctrl+Alt+M", "F8", "F9",
]
MAC_SHORTCUTS = [
    "Ctrl+Option+Space", "Cmd+Shift+Space", "Ctrl+Shift+Space",
    "Ctrl+Option+A", "Ctrl+Option+D", "Ctrl+Option+M",
    "Cmd+Option+A", "Cmd+Option+D", "Cmd+Option+M",
]
AUDIO_FILTER = ("*.mp3 *.wav *.m4a *.ogg *.opus *.flac *.aac *.wma "
                "*.mp4 *.mkv *.webm *.mov *.avi")
KEY_SETTINGS = {
    "openai": "openai_api_key",
    "groq": "groq_api_key",
    "deepgram": "deepgram_api_key",
}


def _app_icon():
    """Application and window icon from shipped assets or system theme."""
    icon = QIcon.fromTheme("dikte")
    if not icon.isNull():
        return icon
    base = os.path.dirname(__file__)
    for cand in (
        os.path.join(base, "icons", "dikte.ico"),
        os.path.join(base, "icons", "dikte.png"),
    ):
        if os.path.isfile(cand):
            icon = QIcon(cand)
            if not icon.isNull():
                return icon
    return QIcon()


class _ConfView(cfg.Config):
    """The settings as the provider registry reads them, typed keys folded in."""

    def __init__(self, data):
        self.data = dict(data)  # no load: everything to show is handed in


class ProviderDialog(QDialog):
    """Name and base URL of a new OpenAI-compatible gateway."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Add provider"))
        self.setWindowIcon(_app_icon())
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("My gateway"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com/v1")
        form.addRow(t("Name"), self.name)
        form.addRow(t("Base URL"), self.url)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)


class ProviderKeysDialog(QDialog):
    """The named keys of a custom provider: add, rename, replace, choose, drop."""

    def __init__(self, conf, pid, parent=None):
        super().__init__(parent)
        self.conf = conf
        self.pid = pid
        who = providers.provider(conf, pid)
        self.setWindowTitle(t("Keys") + " — " + (who.name if who else pid))
        self.setWindowIcon(_app_icon())
        layout = QVBoxLayout(self)
        self.listw = QListWidget()
        layout.addWidget(self.listw)
        row = QHBoxLayout()
        add = QPushButton(t("Add key"))
        add.clicked.connect(self._add)
        self.rename = QPushButton(t("Rename key"))
        self.rename.clicked.connect(self._rename)
        self.replace = QPushButton(t("Replace key"))
        self.replace.clicked.connect(self._replace)
        self.use = QPushButton(t("Set active"))
        self.use.clicked.connect(self._use)
        self.remove = QPushButton(t("Remove"))
        self.remove.clicked.connect(self._remove)
        for button in (add, self.rename, self.replace, self.use, self.remove):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        close = QPushButton(t("Close"))
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self.listw.currentRowChanged.connect(lambda *_: self._refresh_buttons())
        self._reload()

    def _selected(self):
        item = self.listw.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else ""

    def _reload(self):
        self.listw.clear()
        active = providers.active_credential(self.conf, self.pid)
        for cred in providers.credentials(self.conf, self.pid):
            masked = providers.mask(
                providers.credential(self.conf, self.pid, cred["id"]))
            label = f"{cred['label'] or cred['id']}  ·  {masked}"
            if cred["id"] == active:
                label += f"  ·  {t('Active')}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cred["id"])
            self.listw.addItem(item)
        self._refresh_buttons()

    def _refresh_buttons(self):
        picked = bool(self._selected())
        for button in (self.rename, self.replace, self.use, self.remove):
            button.setEnabled(picked)

    def _persist(self):
        try:
            self.conf.save()
        except OSError as exc:
            QMessageBox.warning(self, t("Dikte Settings"),
                                t("Could not save the settings: {error}", error=exc))
        self._reload()

    def _add(self):
        label, ok = QInputDialog.getText(self, t("Add key"), t("Key label"))
        if not ok:
            return
        secret, ok = QInputDialog.getText(self, t("Add key"), t("API key"),
                                          QLineEdit.EchoMode.Password)
        if not ok or not secret.strip():
            return
        providers.add_credential(self.conf, self.pid, label, secret)
        self._persist()

    def _rename(self):
        cred = self._selected()
        if not cred:
            return
        current = next((c["label"] for c in providers.credentials(self.conf, self.pid)
                        if c["id"] == cred), "")
        label, ok = QInputDialog.getText(self, t("Rename key"), t("Key label"),
                                         text=current)
        if ok:
            providers.rename_credential(self.conf, self.pid, cred, label)
            self._persist()

    def _replace(self):
        cred = self._selected()
        if not cred:
            return
        secret, ok = QInputDialog.getText(self, t("Replace key"), t("API key"),
                                          QLineEdit.EchoMode.Password)
        if ok and secret.strip():
            providers.replace_credential(self.conf, self.pid, cred, secret)
            self._persist()

    def _use(self):
        cred = self._selected()
        if cred:
            providers.set_active_credential(self.conf, self.pid, cred)
            self._persist()

    def _remove(self):
        cred = self._selected()
        if cred:
            providers.remove_credential(self.conf, self.pid, cred)
            self._persist()


class HistoryDetailsDialog(QDialog):
    """Detailed properties and execution metadata for a dictation history entry."""

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row or {}
        self.setWindowTitle(t("Dictation Details"))
        self.setWindowIcon(_app_icon())
        self.resize(620, 530)

        layout = QVBoxLayout(self)

        summary_group = QGroupBox(t("Properties"))
        grid = QGridLayout(summary_group)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        ts = self.row.get("ts", "-")
        duration = f"{self.row.get('duration', 0):.1f} s" if "duration" in self.row else "-"
        elapsed = f"{self.row.get('elapsed', 0):.1f} s" if self.row.get("elapsed") is not None else "-"
        mode_str = t("Agent Ask") if self.row.get("mode") == "ask" else t("Dictation")
        lang = self.row.get("language") or "-"

        transcribe_prov = self.row.get("transcribe_provider") or "-"
        transcribe_mdl = self.row.get("model") or self.row.get("transcribe_model") or "-"

        cleanup_mdl = self.row.get("cleanup_model") or t("None / Disabled")
        cleanup_prov = self.row.get("cleanup_provider") or "-"
        if cleanup_prov == "-" and cleanup_mdl != t("None / Disabled"):
            if "/" in cleanup_mdl:
                cleanup_prov = cleanup_mdl.split("/")[0]

        status_err = self.row.get("cleanup_error") or t("Success")

        def _val_label(txt, is_error=False):
            lbl = QLabel(str(txt))
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if is_error:
                try:
                    from ui import theme as _theme
                    err = _theme.palette().get("err", "#DF8582")
                except Exception:
                    err = "#DF8582"
                lbl.setStyleSheet(f"color: {err};")
            return lbl

        row_idx = 0
        grid.addWidget(QLabel(f"<b>{t('Timestamp')}:</b>"), row_idx, 0)
        grid.addWidget(_val_label(ts), row_idx, 1)
        grid.addWidget(QLabel(f"<b>{t('Mode')}:</b>"), row_idx, 2)
        grid.addWidget(_val_label(mode_str), row_idx, 3)

        row_idx += 1
        grid.addWidget(QLabel(f"<b>{t('Audio duration')}:</b>"), row_idx, 0)
        grid.addWidget(_val_label(duration), row_idx, 1)
        grid.addWidget(QLabel(f"<b>{t('Processing time')}:</b>"), row_idx, 2)
        grid.addWidget(_val_label(elapsed), row_idx, 3)

        row_idx += 1
        grid.addWidget(QLabel(f"<b>{t('Speech language')}:</b>"), row_idx, 0)
        grid.addWidget(_val_label(lang), row_idx, 1)
        grid.addWidget(QLabel(f"<b>{t('Status / Error')}:</b>"), row_idx, 2)
        grid.addWidget(_val_label(status_err, is_error=bool(self.row.get("cleanup_error"))), row_idx, 3)

        row_idx += 1
        grid.addWidget(QLabel(f"<b>{t('Transcription')}:</b>"), row_idx, 0)
        transcribe_summary = f"{transcribe_prov} ({transcribe_mdl})" if transcribe_prov != "-" else transcribe_mdl
        grid.addWidget(_val_label(transcribe_summary), row_idx, 1, 1, 3)

        row_idx += 1
        grid.addWidget(QLabel(f"<b>{t('Cleanup AI')}:</b>"), row_idx, 0)
        cleanup_summary = f"{cleanup_prov} ({cleanup_mdl})" if cleanup_prov != "-" and cleanup_mdl != t("None / Disabled") else cleanup_mdl
        grid.addWidget(_val_label(cleanup_summary), row_idx, 1, 1, 3)

        if self.row.get("mode") == "ask":
            row_idx += 1
            asst_prov = self.row.get("assistant_provider") or "-"
            asst_mdl = self.row.get("assistant_model") or "-"
            asst_summary = f"{asst_prov} ({asst_mdl})" if asst_prov != "-" else asst_mdl
            grid.addWidget(QLabel(f"<b>{t('Agent / Assistant')}:</b>"), row_idx, 0)
            grid.addWidget(_val_label(asst_summary), row_idx, 1, 1, 3)

        layout.addWidget(summary_group)

        tabs = QTabWidget()

        self.final_text_box = QPlainTextEdit()
        self.final_text_box.setReadOnly(True)
        self.final_text_box.setPlainText(self.row.get("text", ""))
        tabs.addTab(self.final_text_box, t("Final text"))

        self.raw_text_box = QPlainTextEdit()
        self.raw_text_box.setReadOnly(True)
        self.raw_text_box.setPlainText(self.row.get("raw", ""))
        tabs.addTab(self.raw_text_box, t("Raw transcript"))

        if self.row.get("mode") == "ask" or self.row.get("question"):
            self.question_box = QPlainTextEdit()
            self.question_box.setReadOnly(True)
            self.question_box.setPlainText(self.row.get("question", ""))
            tabs.addTab(self.question_box, t("Question"))

        self.json_box = QPlainTextEdit()
        self.json_box.setReadOnly(True)
        self.json_box.setPlainText(json.dumps(self.row, ensure_ascii=False, indent=2))
        tabs.addTab(self.json_box, t("Metadata (JSON)"))

        layout.addWidget(tabs, 1)

        btn_layout = QHBoxLayout()
        copy_final_btn = QPushButton(t("Copy final text"))
        copy_final_btn.clicked.connect(self._copy_final)
        btn_layout.addWidget(copy_final_btn)

        copy_raw_btn = QPushButton(t("Copy raw transcript"))
        copy_raw_btn.clicked.connect(self._copy_raw)
        btn_layout.addWidget(copy_raw_btn)

        copy_json_btn = QPushButton(t("Copy JSON"))
        copy_json_btn.clicked.connect(self._copy_json)
        btn_layout.addWidget(copy_json_btn)

        btn_layout.addStretch(1)

        close_btn = QPushButton(t("Close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _copy_final(self):
        QGuiApplication.clipboard().setText(self.row.get("text", ""))

    def _copy_raw(self):
        QGuiApplication.clipboard().setText(self.row.get("raw", ""))

    def _copy_json(self):
        QGuiApplication.clipboard().setText(json.dumps(self.row, ensure_ascii=False, indent=2))


class SettingsWindow(QDialog):
    applied = pyqtSignal()

    _models_loaded = pyqtSignal(list, str)
    _transcribe_models_loaded = pyqtSignal(list, str)
    _agy_models_loaded = pyqtSignal(list, str)
    _claude_models_loaded = pyqtSignal(list, str)
    _codex_models_loaded = pyqtSignal(list, str)
    _meeting_models_loaded = pyqtSignal(list, str)
    _assistant_gateway_models_loaded = pyqtSignal(list, str)
    _provider_versions_done = pyqtSignal(dict)
    _provider_test_done = pyqtSignal(str, bool, str)
    _model_test_done = pyqtSignal(bool, str)
    _audio_sources_loaded = pyqtSignal(list)
    _audio_monitors_loaded = pyqtSignal(list)
    _audio_defaults_loaded = pyqtSignal(str, str)

    def __init__(self, conf, meetings=None, parent=None):
        super().__init__(parent)
        self.conf = conf
        self.meetings = meetings
        self._theme = conf.get("ui_theme", "dark") or "dark"
        self._shortcut_rows = {}
        self._models = dict.fromkeys(cfg.TRANSCRIBERS, "")
        self._key_fields = {}
        self._testers = {}
        self._shown_provider = ""
        self._provider_tests = {}
        self._provider_versions = {}
        self._provider_creds = {}
        self._custom_row_widgets = []
        self._versions_busy = False
        self._versions_thread = None
        self._pending_transcribe_provider = ""
        self._pending_cleanup_provider = ""
        self._pending_meeting_provider = ""
        self._pending_gateway_provider = ""
        self.transcriber = FileTranscriber(conf, self)
        self.setWindowTitle(t("Dikte Settings"))
        self.setWindowIcon(_app_icon())
        self.resize(1000, 700)
        self.setMinimumSize(720, 560)

        self.shell = AppShell(parent=self)
        self.tabs = self.shell.tabs
        self.shell.add_page(t("General"), self._general_tab(), "sliders")
        self.api_tab_index = self.shell.add_page(t("API and models"), self._api_tab(), "plug")
        self.shell.add_page(t("Cleanup rules"), self._prompt_tab(), "eraser")
        self.shell.add_page(t("Agent"), self._assistant_tab(), "terminal")
        self.shell.add_page(t("Meeting"), self._meeting_tab(), "users")
        self.shell.add_page(t("Minutes"), self._minutes_tab(), "fileText")
        self.shell.add_page(t("Audio file"), self._file_tab(), "fileAudio")
        self.shell.add_page(t("Shortcuts"), self._shortcut_tab(), "keyboard")
        self.shell.add_page(t("History"), self._history_tab(), "history")
        # Overlay is 10th tab per prototype (last)
        try:
            from ui.pages import overlay as overlay_page
            self.shell.add_page(t("Overlay/Indicator"), overlay_page.build(self), "pip")
        except Exception:
            pass
        self.shell.theme_toggled.connect(self._toggle_theme)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(t("Save"))
        buttons.accepted.connect(self._save)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 10, 20, 12)
        bl.addStretch(1)
        bl.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.shell, 1)
        layout.addWidget(bar)

        self._models_loaded.connect(self._on_models_loaded)
        self._transcribe_models_loaded.connect(self._on_transcribe_models_loaded)
        self._agy_models_loaded.connect(self._on_agy_models_loaded)
        self._claude_models_loaded.connect(self._on_claude_models_loaded)
        self._codex_models_loaded.connect(self._on_codex_models_loaded)
        self._meeting_models_loaded.connect(self._on_meeting_models_loaded)
        self._assistant_gateway_models_loaded.connect(self._on_assistant_gateway_models_loaded)
        self._provider_versions_done.connect(self._on_provider_versions_done)
        self._provider_test_done.connect(self._on_provider_test_done)
        self._model_test_done.connect(self._on_model_test_done)
        self._audio_sources_loaded.connect(self._on_audio_sources_loaded)
        self._audio_monitors_loaded.connect(self._on_audio_monitors_loaded)
        self._audio_defaults_loaded.connect(self._on_audio_defaults_loaded)
        self.transcriber.progress.connect(self._on_file_progress)
        self.transcriber.finished.connect(self._on_file_finished)
        self.transcriber.failed.connect(self._on_file_failed)
        if self.meetings is not None:
            self.meetings.progress.connect(self._on_minutes_progress)
            self.meetings.finished.connect(self._on_minutes_finished)
            self.meetings.failed.connect(self._on_minutes_failed)

        _theme.apply(self._theme)
        self.shell.set_theme(self._theme)
        self._load()
        self._baseline = self._snapshot_settings()
        self._navigating = False
        self._pending_index = -1
        self._prev_index = self.tabs.currentIndex()
        try:
            self.tabs.currentChanged.connect(self._on_tab_change_requested)
            self.shell.tabs.currentChanged.connect(self._on_tab_change_requested)
        except Exception:
            pass
        # Apply persisted sidebar compact (manual preference) — auto responsive overrides at <920
        try:
            initial_compact = bool(self.conf.get("sidebar_compact", False)) or self.width() < 920
            self.shell.setCompact(initial_compact)
            self._user_compact = bool(self.conf.get("sidebar_compact", False))
            self.shell.compactToggled.connect(self._on_sidebar_compact_toggled)
        except Exception:
            pass
        self.file_timestamps.toggled.connect(self._remember_file_choices)
        self.file_cleanup.toggled.connect(self._remember_file_choices)
        # Engine card reflects selected transcribe provider/model
        try:
            self.transcribe_provider.currentIndexChanged.connect(lambda *_: self._refresh_engine_card())
            self.transcribe_model.currentTextChanged.connect(lambda *_: self._refresh_engine_card())
            if hasattr(self, "local_whisper"):
                self.local_whisper.changed.connect(self._refresh_engine_card)
        except Exception:
            pass
        try:
            self._refresh_engine_card()
        except Exception:
            pass
        if not conf.transcribe_ready():
            self.tabs.setCurrentIndex(self.api_tab_index)

    # ---- tabs ----------------------------------------------------------

    def _general_tab(self):
        return general_page.build(self)

    def _api_tab(self):
        return providers_page.build(self)

    def _prompt_tab(self):
        return cleanup_page.build(self)

    def _assistant_tab(self):
        return agent_page.build(self)

    def _meeting_tab(self):
        return meeting_page.build(self)

    def _minutes_tab(self):
        return minutes_page.build(self)

    def _file_tab(self):
        return audiofile_page.build(self)

    def _shortcut_tab(self):
        return shortcuts_page.build(self)

    def _history_tab(self):
        return history_page.build(self)

    # ---- the provider registry -------------------------------------------

    KEY_PLACEHOLDERS = {
        "openai": "sk-… (falls back to OPENAI_API_KEY)",
        "groq": "gsk_… (falls back to GROQ_API_KEY)",
        "deepgram": "(falls back to DEEPGRAM_API_KEY)",
    }

    def _providers_group(self):
        """Every provider in one place, one row each."""
        box = QGroupBox(t("Providers"))
        layout = QVBoxLayout(box)
        layout.setContentsMargins(20, 16, 20, 12)
        self.provider_grid = QGridLayout()
        self.provider_grid.setColumnStretch(1, 1)
        self.provider_grid.setColumnStretch(2, 1)
        layout.addLayout(self.provider_grid)
        self._first_custom_row = self._built_in_rows()
        row = QHBoxLayout()
        add = QPushButton(t("Add provider"))
        add.clicked.connect(self._add_provider)
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)
        return box

    def _built_in_rows(self):
        """A row per built-in the registry offers, in its order; how many were
        drawn."""
        row = 0
        for pid, who in providers.definitions(self.conf).items():
            if who.custom:
                continue
            name = QLabel(who.name)
            self.provider_grid.addWidget(name, row, 0)
            button = QPushButton(t("Test"))
            button.clicked.connect(
                lambda *_, pid=pid: self._test_provider(pid))
            answer = QLabel("")
            answer.setWordWrap(True)
            if pid in self.KEY_PLACEHOLDERS:
                name.setToolTip(providers.base_url(self.conf, pid))
                field = QLineEdit()
                field.setEchoMode(QLineEdit.EchoMode.Password)
                field.setPlaceholderText(t(self.KEY_PLACEHOLDERS[pid]))
                self.provider_grid.addWidget(field, row, 1)
                self.provider_grid.addWidget(answer, row, 2)
                self.provider_grid.addWidget(button, row, 3)
                self._key_fields[pid] = field
                self._testers[pid] = (button, answer)
            else:
                self.provider_grid.addWidget(answer, row, 1, 1, 2)
                self.provider_grid.addWidget(button, row, 3)
                self._testers[pid] = (button, answer)
            row += 1
        return row

    def _rebuild_custom_rows(self, defs):
        """The user's own gateways, row by row, from whatever the registry
        holds now."""
        for widget in self._custom_row_widgets:
            self.provider_grid.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._custom_row_widgets = []
        for pid in [p for p in self._testers
                    if p.startswith("user/") and p not in defs]:
            del self._testers[pid]
            self._provider_creds.pop(pid, None)
        row = self._first_custom_row
        for pid, who in defs.items():
            if not who.custom:
                continue
            name = QLabel(who.name)
            cred = QLabel(providers.mask(providers.credential(self.conf, pid))
                          or t("no key"))
            answer = QLabel(self._provider_tests.get(pid, "") or who.base_url)
            answer.setWordWrap(True)
            keys = QPushButton(t("Keys…"))
            keys.clicked.connect(
                lambda *_, pid=pid: self._edit_provider_keys(pid))
            url = QPushButton(t("Base URL…"))
            url.clicked.connect(
                lambda *_, pid=pid: self._edit_provider_url(pid))
            rename = QPushButton(t("Rename…"))
            rename.clicked.connect(
                lambda *_, pid=pid: self._rename_provider(pid))
            remove = QPushButton(t("Remove"))
            remove.clicked.connect(
                lambda *_, pid=pid: self._remove_provider(pid))
            test = QPushButton(t("Test"))
            test.clicked.connect(
                lambda *_, pid=pid: self._test_provider(pid))
            self.provider_grid.addWidget(name, row, 0)
            self.provider_grid.addWidget(cred, row, 1)
            self.provider_grid.addWidget(answer, row, 2)
            for column, button in enumerate((keys, url, rename, remove, test),
                                            start=3):
                self.provider_grid.addWidget(button, row, column)
                self._custom_row_widgets.append(button)
            self._custom_row_widgets += [name, cred, answer]
            self._provider_creds[pid] = cred
            self._testers[pid] = (test, answer)
            row += 1

    def _refresh_providers(self):
        """Redraw the registry rows, and offer what the registry holds in every
        provider box, wherever a compatible one fits."""
        defs = providers.definitions(self.conf)
        self._rebuild_custom_rows(defs)
        self._update_local_rows()
        self._update_cli_rows(defs)
        # CLI version fetch is deferred off the GUI thread via _deferred_load
        self._fill_providers(self.transcribe_provider, self._transcribe_choices())
        self._fill_providers(self.cleanup_provider, self._cleanup_choices())
        self._fill_providers(self.meeting_provider, self._meeting_choices())
        self._fill_providers(self.assistant_provider, self._assistant_choices())
        self._cleanup_provider_changed()

    def _update_local_rows(self):
        """The two local rows: whichever model each one is set to run, or the
        last Test verdict when there is one."""
        conf = self.conf
        for pid, setting in (("local", "local_model"),
                             ("local-llm", "local_llm_model")):
            model = conf[setting]
            self._testers[pid][1].setText(
                self._provider_tests.get(pid, "") or (
                    t("Ready: {model}", model=model) if model
                    else t("Not configured")))

    def _update_cli_rows(self, defs):
        """The CLI rows: the last Test verdict, else the version line a
        refresh found, else nothing while the first one is still asking."""
        for pid, who in defs.items():
            if who.transport != "cli":
                continue
            if pid in self._provider_tests:
                self._testers[pid][1].setText(self._provider_tests[pid])
            elif pid in self._provider_versions:
                version = self._provider_versions[pid]
                self._testers[pid][1].setText(
                    t("{service} found: {version}", service=who.name,
                      version=version) if version
                    else t("{service} is not installed.", service=who.name))

    def _fetch_cli_versions(self, defs):
        """Ask the CLI providers for their version lines, once per refresh."""
        if self._versions_busy:
            return
        pids = [pid for pid, who in defs.items() if who.transport == "cli"]
        self._versions_busy = True

        def work():
            self._provider_versions_done.emit(
                {pid: providers.executable_version(pid) for pid in pids})

        self._versions_thread = threading.Thread(target=work, daemon=True)
        self._versions_thread.start()

    def _on_provider_versions_done(self, found):
        self._versions_busy = False
        self._provider_versions.update(found)
        self._update_cli_rows(providers.definitions(self.conf))

    # ---- the provider boxes ------------------------------------------------

    def _transcribe_choices(self):
        """(label, value) for speech to text: whoever the registry says can
        hear, this machine first."""
        out = []
        for pid, who in providers.definitions(self.conf).items():
            if providers.TRANSCRIPTION not in who.capabilities:
                continue
            label = t("This machine (whisper.cpp)") if pid == "local" else who.name
            out.append((label, pid))
        return out

    def _cleanup_choices(self):
        """(label, value) for cleanup: everyone cleanup.py can dispatch to."""
        out = []
        for pid, who in providers.definitions(self.conf).items():
            if pid == "local-llm":
                out.append((t("This machine (llama.cpp)"), "local"))
            elif pid != "local" and (pid in cleanup.PROVIDERS or who.custom):
                out.append((who.name, pid))
        return out

    def _meeting_choices(self):
        """(label, value) for the minutes: the local model, the user's own
        gateways, nothing else."""
        out = [(t("This machine (llama.cpp)"), "local")]
        for pid, who in providers.definitions(self.conf).items():
            if who.custom:
                out.append((who.name, pid))
        return out

    def _assistant_choices(self):
        """(label, value) for the agent: everyone assistant.py dispatches to,
        the user's own gateways included."""
        return [(who.name, pid)
                for pid, who in providers.definitions(self.conf).items()
                if pid in assistant.PROVIDERS or who.custom]

    def _fill_providers(self, combo, choices):
        """A provider box redrawn from the registry: what it holds now, with
        whoever was chosen kept chosen."""
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, value in choices:
            combo.addItem(label, value)
        combo.setCurrentIndex(max(combo.findData(current), 0))
        combo.blockSignals(False)

    def _persist_providers(self):
        """A provider created or changed here is kept at once: the Save button
        is for the settings, not for a key somebody just pasted in."""
        try:
            self.conf.save()
        except OSError as exc:
            QMessageBox.warning(self, t("Dikte Settings"),
                                t("Could not save the settings: {error}", error=exc))
        self._refresh_providers()

    def _add_provider(self):
        dialog = ProviderDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        providers.add_provider(self.conf, dialog.name.text(), dialog.url.text())
        self._persist_providers()

    def _remove_provider(self, pid):
        who = providers.provider(self.conf, pid)
        if who is None or not who.custom:
            return
        if not self._confirm(t("Remove {name}?", name=who.name), t("Providers")):
            return
        providers.remove_provider(self.conf, pid)
        self._provider_tests.pop(pid, None)
        self._testers.pop(pid, None)
        self._provider_creds.pop(pid, None)
        self._persist_providers()

    def _rename_provider(self, pid):
        who = providers.provider(self.conf, pid)
        if who is None or not who.custom:
            return
        name, ok = QInputDialog.getText(self, t("Rename…"), t("Name"),
                                        text=who.name)
        if ok:
            providers.rename_provider(self.conf, pid, name)
            self._persist_providers()

    def _edit_provider_url(self, pid):
        who = providers.provider(self.conf, pid)
        if who is None or not who.custom:
            return
        url, ok = QInputDialog.getText(self, t("Base URL"), t("Base URL"),
                                       text=providers.base_url(self.conf, pid))
        if ok:
            providers.set_base_url(self.conf, pid, url)
            self._persist_providers()

    def _edit_provider_keys(self, pid):
        """Named keys are a custom provider's; a built-in's one key lives in
        the field of its own row above."""
        who = providers.provider(self.conf, pid)
        if who is None or not who.custom:
            return
        ProviderKeysDialog(self.conf, pid, self).exec()
        self._persist_providers()

    def _test_provider(self, pid):
        """A row's own verdict, off the interface thread like the key tests."""
        if not providers.provider(self.conf, pid):
            return
        conf = self._conf_view(pid)
        button, answer = self._testers[pid]
        button.setEnabled(False)
        answer.setText(t("Trying…"))

        def work():
            try:
                self._provider_test_done.emit(pid, True,
                                              providers.test_provider(conf, pid))
            except api.ApiError as exc:
                self._provider_test_done.emit(pid, False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_provider_test_done(self, pid, ok, message):
        line = ("✓ " if ok else "✗ ") + message
        self._provider_tests[pid] = line
        entry = self._testers.get(pid)
        if entry is not None:
            button, answer = entry
            button.setEnabled(True)
            answer.setText(line)

    # ---- api helpers -----------------------------------------------------

    def _provider_changed(self):
        """Swap the model box over to the newly chosen provider's own model."""
        if (self._shown_provider in TRANSCRIBE_MODELS
                or self._shown_provider.startswith("user/")):
            self._models[self._shown_provider] = self.transcribe_model.currentText().strip()
        provider = self.transcribe_provider.currentData() or "local"
        self._shown_provider = provider
        local = provider == "local"
        self.stt_form.setRowVisible(self.transcribe_model_row, not local)
        self.stt_form.setRowVisible(self.transcribe_status, not local)
        self.stt_form.setRowVisible(self.local_whisper, local)
        self.stt_form.setRowVisible(self.local_options, local)
        if local:
            try:
                self._refresh_engine_card()
            except Exception:
                pass
            return
        self.transcribe_model.clear()
        self.transcribe_model.addItems(TRANSCRIBE_MODELS.get(provider, []))
        self.transcribe_model.setCurrentText(self._models.setdefault(provider, ""))
        self.transcribe_status.setText("")
        try:
            self._refresh_engine_card()
        except Exception:
            pass

    def _conf_view(self, pid):
        """What the registry should read: the stored settings, plus the key
        typed into this provider's field, if it has one and is not empty."""
        data = dict(self.conf.data)
        field = self._key_fields.get(pid)
        if field is not None and field.text().strip():
            data[KEY_SETTINGS[pid]] = field.text().strip()
        return _ConfView(data)

    def _load_transcribe_models(self):
        """The model list of whichever provider is selected."""
        provider = self.transcribe_provider.currentData() or "openai"
        self._pending_transcribe_provider = provider
        self.refresh_transcribe_models.setEnabled(False)
        self.transcribe_status.setText(t("Fetching model list…"))
        conf = self._conf_view(provider)
        captured = provider
        current_text = self.transcribe_model.currentText().strip() if hasattr(self, "transcribe_model") else ""

        def work():
            try:
                models = providers.fetch_models(conf, captured,
                                                providers.TRANSCRIPTION)
                # Deduplicate and preserve current value
                if current_text and current_text not in models:
                    models = [current_text] + models
                # Ensure deterministic natural sorting for generic lists
                try:
                    models = providers.normalize_models(models, current_text)
                except Exception:
                    pass
                self._transcribe_models_loaded.emit(models, "")
            except api.ApiError as exc:
                self._transcribe_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_transcribe_models_loaded(self, models, error):
        self.refresh_transcribe_models.setEnabled(True)
        # Stale-result guard: ignore if provider changed since fetch started
        current_provider = self.transcribe_provider.currentData() or "openai"
        if current_provider != getattr(self, "_pending_transcribe_provider", current_provider):
            if error:
                self.transcribe_status.setText(t("Could not fetch the list: {error}", error=error))
            return
        if error:
            self.transcribe_status.setText(t("Could not fetch the list: {error}", error=error))
            return
        current = self.transcribe_model.currentText()
        # Preserve custom value even if not in discovered list
        if current and current not in models:
            models = [current] + [m for m in models if m != current]
        # Deduplicate deterministically
        try:
            models = providers.normalize_models(models, current)
        except Exception:
            models = list(dict.fromkeys(models))
        self.transcribe_model.clear()
        self.transcribe_model.addItems(models)
        self.transcribe_model.setCurrentText(current)
        self.transcribe_status.setText(t("{count} models loaded.", count=len(models)))

    def _load_models(self):
        self.refresh_models.setEnabled(False)
        self.models_label.setText(t("Fetching model list…"))
        provider = self.cleanup_provider.currentData() or "local"
        self._pending_cleanup_provider = provider
        conf = self._conf_view(provider)
        captured = provider
        current_text = self.cleanup_model.currentText().strip() if hasattr(self, "cleanup_model") else ""

        def work():
            try:
                if captured == "local":
                    # Local LLM models: use installed list, not remote
                    models = sorted(api.ggml.installed_llm_models())
                    if current_text and current_text not in models:
                        models = [current_text] + models
                    try:
                        models = providers.normalize_models(models, current_text)
                    except Exception:
                        pass
                else:
                    models = providers.fetch_models(conf, captured, providers.TEXT)
                    if current_text and current_text not in models:
                        models = [current_text] + [m for m in models if m != current_text]
                    try:
                        models = providers.normalize_models(models, current_text)
                    except Exception:
                        models = list(dict.fromkeys(models))
                self._models_loaded.emit(models, "")
            except api.ApiError as exc:
                self._models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _load_agy_models(self):
        """The slugs `agy models` prints, for whichever Antigravity row asked."""
        self.refresh_agy_models.setEnabled(False)
        self.refresh_assistant_agy_models.setEnabled(False)
        self.models_label.setText(t("Fetching model list…"))

        def work():
            try:
                self._agy_models_loaded.emit(providers.agy_models(), "")
            except api.ApiError as exc:
                self._agy_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_agy_models_loaded(self, models, error):
        self.refresh_agy_models.setEnabled(True)
        self.refresh_assistant_agy_models.setEnabled(True)
        if error:
            self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        for combo in (self.cleanup_agy_model, self.assistant_agy_model):
            current = combo.currentText()
            combo.clear()
            combo.addItems(models)
            combo.setCurrentText(current)
        self.models_label.setText(t("{count} models loaded.", count=len(models)))

    def _load_claude_models(self):
        """The models the user's own Claude Code settings name, for whichever
        Claude row asked."""
        self.refresh_claude_models.setEnabled(False)
        self.refresh_assistant_claude_models.setEnabled(False)
        self.models_label.setText(t("Fetching model list…"))

        def work():
            try:
                self._claude_models_loaded.emit(providers.claude_models(), "")
            except Exception as exc:
                self._claude_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_claude_models_loaded(self, models, error):
        self.refresh_claude_models.setEnabled(True)
        self.refresh_assistant_claude_models.setEnabled(True)
        if error:
            self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        if models:
            for combo in (self.cleanup_claude_model, self.assistant_model):
                current = combo.currentText()
                combo.clear()
                combo.addItems(models)
                combo.setCurrentText(current)
            self.models_label.setText(t("{count} models loaded.", count=len(models)))
        else:
            self.models_label.setText(
                t("No models named in your own settings; the standing list stays."))

    def _load_codex_models(self):
        """The model the user's own Codex is set to, for whichever Codex row
        asked, ahead of the standing suggestions."""
        self.refresh_codex_models.setEnabled(False)
        self.refresh_assistant_codex_models.setEnabled(False)
        self.models_label.setText(t("Fetching model list…"))

        def work():
            try:
                self._codex_models_loaded.emit(providers.codex_models(), "")
            except Exception as exc:
                self._codex_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_codex_models_loaded(self, models, error):
        self.refresh_codex_models.setEnabled(True)
        self.refresh_assistant_codex_models.setEnabled(True)
        if error:
            self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        if models:
            for combo in (self.cleanup_codex_model, self.assistant_codex_model):
                current = combo.currentText()
                combo.clear()
                combo.addItem(t("Codex's own default"))
                combo.addItems(models)
                combo.setCurrentText(current)
            self.models_label.setText(t("{count} models loaded.", count=len(models)))
        else:
            self.models_label.setText(
                t("No models named in your own settings; the standing list stays."))

    def _on_models_loaded(self, models, error):
        self.refresh_models.setEnabled(True)
        # Stale guard: ignore if provider changed
        cur_provider = self.cleanup_provider.currentData() or "local"
        pending = getattr(self, "_pending_cleanup_provider", cur_provider)
        if cur_provider != pending:
            if error:
                self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        if error:
            self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        provider = cur_provider
        combos = [self.cleanup_model]
        for box, chosen in ((self.meeting_model, self.meeting_provider),
                            (self.assistant_gateway_model,
                             self.assistant_provider)):
            if chosen.currentData() == provider:
                combos.append(box)
        for combo in combos:
            current = combo.currentText()
            # Preserve custom value and deduplicate
            normalized = list(models)
            if current and current not in normalized:
                normalized = [current] + normalized
            try:
                normalized = providers.normalize_models(normalized, current)
            except Exception:
                normalized = list(dict.fromkeys(normalized))
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(normalized)
            combo.setCurrentText(current)
            combo.blockSignals(False)
        self.models_label.setText(t("{count} models loaded.", count=len(models)))

    def _load_meeting_models(self):
        """Fetch TEXT models for the meeting provider (gateway) or local LLM list."""
        provider = self.meeting_provider.currentData() or "local"
        self._pending_meeting_provider = provider
        if hasattr(self, "refresh_meeting_models"):
            self.refresh_meeting_models.setEnabled(False)
        if hasattr(self, "meeting_models_label"):
            self.meeting_models_label.setText(t("Fetching model list…"))
        else:
            self.models_label.setText(t("Fetching model list…"))
        captured = provider
        current_text = self.meeting_model.currentText().strip() if hasattr(self, "meeting_model") else ""
        conf = self._conf_view(captured) if captured.startswith("user/") else self.conf

        def work():
            try:
                if captured == "local":
                    models = sorted(api.ggml.installed_llm_models())
                elif captured.startswith("user/"):
                    models = providers.fetch_models(conf, captured, providers.TEXT)
                else:
                    # meeting provider local case already handled; fallback to empty
                    models = []
                if current_text and current_text not in models:
                    models = [current_text] + models
                try:
                    models = providers.normalize_models(models, current_text)
                except Exception:
                    models = list(dict.fromkeys(models))
                self._meeting_models_loaded.emit(models, "")
            except api.ApiError as exc:
                self._meeting_models_loaded.emit([], str(exc))
            except Exception as exc:
                self._meeting_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_meeting_models_loaded(self, models, error):
        if hasattr(self, "refresh_meeting_models"):
            self.refresh_meeting_models.setEnabled(True)
        # Stale guard
        cur = self.meeting_provider.currentData() or "local"
        pending = getattr(self, "_pending_meeting_provider", cur)
        if cur != pending:
            if error and hasattr(self, "meeting_models_label"):
                self.meeting_models_label.setText(t("Could not fetch the list: {error}", error=error))
            elif error:
                self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        label = self.meeting_models_label if hasattr(self, "meeting_models_label") else self.models_label
        if error:
            label.setText(t("Could not fetch the list: {error}", error=error))
            return
        if not models:
            label.setText(t("No models found."))
            return
        current = self.meeting_model.currentText()
        normalized = list(models)
        if current and current not in normalized:
            normalized = [current] + normalized
        try:
            normalized = providers.normalize_models(normalized, current)
        except Exception:
            normalized = list(dict.fromkeys(normalized))
        self.meeting_model.blockSignals(True)
        self.meeting_model.clear()
        self.meeting_model.addItems(normalized)
        self.meeting_model.setCurrentText(current)
        self.meeting_model.blockSignals(False)
        label.setText(t("{count} models loaded.", count=len(models)))

    def _load_assistant_gateway_models(self):
        """Fetch models for the assistant gateway (user/*) provider."""
        provider = self.assistant_provider.currentData() or "claude"
        self._pending_gateway_provider = provider
        if hasattr(self, "refresh_assistant_gateway_models"):
            self.refresh_assistant_gateway_models.setEnabled(False)
        self.models_label.setText(t("Fetching model list…"))
        captured = provider
        current_text = self.assistant_gateway_model.currentText().strip() if hasattr(self, "assistant_gateway_model") else ""
        conf = self._conf_view(captured)

        def work():
            try:
                if not captured.startswith("user/"):
                    self._assistant_gateway_models_loaded.emit([], t("This provider does not list models."))
                    return
                models = providers.fetch_models(conf, captured, providers.TEXT)
                if current_text and current_text not in models:
                    models = [current_text] + models
                try:
                    models = providers.normalize_models(models, current_text)
                except Exception:
                    models = list(dict.fromkeys(models))
                self._assistant_gateway_models_loaded.emit(models, "")
            except api.ApiError as exc:
                self._assistant_gateway_models_loaded.emit([], str(exc))
            except Exception as exc:
                self._assistant_gateway_models_loaded.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_assistant_gateway_models_loaded(self, models, error):
        if hasattr(self, "refresh_assistant_gateway_models"):
            self.refresh_assistant_gateway_models.setEnabled(True)
        cur = self.assistant_provider.currentData() or "claude"
        pending = getattr(self, "_pending_gateway_provider", cur)
        if cur != pending:
            if error:
                self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        if error:
            self.models_label.setText(t("Could not fetch the list: {error}", error=error))
            return
        current = self.assistant_gateway_model.currentText()
        normalized = list(models)
        if current and current not in normalized:
            normalized = [current] + normalized
        try:
            normalized = providers.normalize_models(normalized, current)
        except Exception:
            normalized = list(dict.fromkeys(normalized))
        self.assistant_gateway_model.blockSignals(True)
        self.assistant_gateway_model.clear()
        self.assistant_gateway_model.addItems(normalized)
        self.assistant_gateway_model.setCurrentText(current)
        self.assistant_gateway_model.blockSignals(False)
        self.models_label.setText(t("{count} models loaded.", count=len(models)))

    def _cleanup_conf_view(self):
        """The cleanup settings as they sit on screen right now, key, provider,
        model and all, for the Test button to run through."""
        provider = self.cleanup_provider.currentData() or "local"
        conf = self._conf_view(provider)
        conf.data["cleanup_provider"] = provider
        conf.data["cleanup_reasoning"] = self.cleanup_reasoning.currentData() or ""
        models = {"claude": (self.cleanup_claude_model, "cleanup_claude_model"),
                  "codex": (self.cleanup_codex_model, "cleanup_codex_model"),
                  "antigravity": (self.cleanup_agy_model, "cleanup_agy_model")}
        if provider.startswith("user/"):
            conf.data["providers"] = json.loads(
                json.dumps(self.conf.data.get("providers") or []))
            providers.set_custom_model(conf, provider, "text",
                                       self.cleanup_model.currentText().strip())
        elif provider == "local":
            conf.data["local_llm_model"] = self.local_llm.selected()
            conf.data["local_llm_reasoning"] = (
                self.local_llm_reasoning.currentData() or "")
        elif provider in models:
            box, setting = models[provider]
            text = box.currentText().strip()
            if provider == "codex" and text == t("Codex's own default"):
                text = ""
            conf.data[setting] = text
        return conf

    def _test_cleanup_model(self):
        """One minimal run through the cleanup provider and model set above,
        off the interface thread."""
        conf = self._cleanup_conf_view()
        self.cleanup_test.setEnabled(False)
        self.cleanup_test_status.setText(t("Trying…"))

        def work():
            try:
                self._model_test_done.emit(True, cleanup.test_model(conf))
            except api.ApiError as exc:   # CleanupError is one of these
                self._model_test_done.emit(False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_model_test_done(self, ok, message):
        self.cleanup_test.setEnabled(True)
        self.cleanup_test_status.setText(("✓ " if ok else "✗ ") + message)

    # ---- audio file ------------------------------------------------------

    def _choose_file(self):
        start = self.conf["file_last_dir"] or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, t("Select an audio file"), start,
            f"{t('Audio and video files')} ({AUDIO_FILTER});;{t('All files')} (*)",
        )
        if not path:
            return
        self.file_path = path
        self.file_label.setText(os.path.basename(path))
        self.conf["file_last_dir"] = os.path.dirname(path)
        self._remember_file_choices()

    def _remember_file_choices(self):
        """Keep this tab's choices without waiting for the Save button."""
        self.conf["file_timestamps"] = self.file_timestamps.isChecked()
        self.conf["file_cleanup"] = self.file_cleanup.isChecked()
        self.conf.save()

    def _run_file(self):
        if not getattr(self, "file_path", "") or self.transcriber.busy:
            return
        self.file_output.clear()
        self.file_segments = []
        self.file_save_srt.setEnabled(False)
        self.file_run.setEnabled(False)
        self.file_stop.setEnabled(True)
        self.transcriber.start(
            self.file_path,
            self.file_timestamps.isChecked(),
            self.file_cleanup.isChecked(),
        )

    def _stop_file(self):
        self.file_stop.setEnabled(False)
        self.file_status.setText(t("Stopping…"))
        self.transcriber.stop()

    def _on_file_progress(self, message):
        self.file_status.setText(message)
        if message == t("Stopped."):
            self._file_idle()

    def _on_file_finished(self, text, segments):
        self.file_output.setPlainText(text)
        self.file_segments = segments
        self.file_save_srt.setEnabled(bool(segments))
        self.file_status.setText(t("Done: {chars} characters.", chars=len(text)))
        self._file_idle()

    def _on_file_failed(self, error):
        self.file_status.setText(t("Failed: {error}", error=error))
        self._file_idle()

    def _file_idle(self):
        self.file_run.setEnabled(True)
        self.file_stop.setEnabled(False)

    def _save_transcript(self):
        self._write_transcript(self.file_output.toPlainText(), ".txt",
                               f"{t('Text files')} (*.txt)")

    def _save_subtitles(self):
        srt = filetranscribe.to_srt(self.file_output.toPlainText(),
                                    getattr(self, "file_segments", []))
        if not srt:
            self.file_status.setText(t("No timestamped lines to turn into subtitles."))
            return
        self._write_transcript(srt, ".srt", f"{t('Subtitle files')} (*.srt)")

    def _write_transcript(self, text, suffix, file_filter):
        if not text:
            return
        base = os.path.splitext(os.path.basename(getattr(self, "file_path", "")))[0]
        start = os.path.join(self.conf["file_last_dir"] or os.path.expanduser("~"),
                             f"{base or 'transcript'}{suffix}")
        path, _ = QFileDialog.getSaveFileName(
            self, t("Save transcript"), start, file_filter
        )
        if not path:
            return
        if not path.lower().endswith(suffix):
            path += suffix
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.file_status.setText(t("Saved: {path}", path=path))
        except OSError as exc:
            self.file_status.setText(t("Failed: {error}", error=exc))

    # ---- shortcuts -------------------------------------------------------

    def _install_shortcut(self, which):
        spec = hotkey.SHORTCUTS[which]
        box, _status, _missing = self._shortcut_rows[which]
        combo = box.currentText().strip() or spec.fallback
        if not combo:
            QMessageBox.information(self, t("Shortcut"),
                                    t("Type a key combination first."))
            return
        clashes = hotkey.conflicting_shortcuts(combo, spec.desktop_id)
        if clashes:
            answer = QMessageBox.question(
                self, t("Shortcut conflict"),
                t("{shortcut} is also used by:\n\n{list}\n\nInstall anyway?",
                  shortcut=combo, list="\n".join(clashes[:6])),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        ok, message = hotkey.install_shortcut(
            combo, ipc.command_for(spec.verb), name=spec.name,
            desktop_id=spec.desktop_id,
        )
        QMessageBox.information(self, t("Shortcut"), message)
        if ok:
            self.conf[spec.setting] = combo
            self.conf.save()
        self._refresh_shortcut_status(which)

    def _remove_shortcut(self, which):
        hotkey.remove_shortcut(hotkey.SHORTCUTS[which].desktop_id)
        self._refresh_shortcut_status(which)

    def _refresh_shortcut_status(self, which):
        # Update canonical status
        try:
            _box, status, missing = self._shortcut_rows[which]
            current = hotkey.shortcut_status(hotkey.SHORTCUTS[which].desktop_id)
            text = (t("Registered in {desktop}: {shortcut}",
                      desktop=hotkey.desktop_name(), shortcut=current) if current
                    else missing)
            status.setText(text)
            # Also update any extra rows for same which (e.g. duplicate ask/meeting in Shortcuts tab)
            if hasattr(self, "_shortcut_rows_extra") and which in self._shortcut_rows_extra:
                for _, extra_status, extra_missing in self._shortcut_rows_extra[which]:
                    extra_status.setText(text if current else extra_missing)
        except Exception:
            pass

    def _cleanup_provider_changed(self):
        provider = self.cleanup_provider.currentData() or "local"
        custom = providers.provider(self.conf, provider)
        gateway = custom is not None and custom.custom
        self.cleanup_form.setRowVisible(self.cleanup_model_row, gateway)
        self.cleanup_form.setRowVisible(self.cleanup_claude_model_row,
                                        provider == "claude")
        self.cleanup_form.setRowVisible(self.cleanup_codex_model_row,
                                        provider == "codex")
        self.cleanup_form.setRowVisible(self.cleanup_agy_model_row,
                                        provider == "antigravity")
        self.cleanup_form.setRowVisible(self.cleanup_reasoning,
                                        provider not in ("local",
                                                         "antigravity"))
        self.cleanup_form.setRowVisible(self.local_llm, provider == "local")
        self.cleanup_form.setRowVisible(self.local_llm_options, provider == "local")
        self.refresh_models.setVisible(gateway)
        binary = cleanup.executable(provider)
        found = shutil.which(binary) if binary else ""
        if provider == "local":
            self.models_label.setText(t("Runs on this machine, on llama.cpp."))
        elif gateway:
            self.models_label.setText(t("Runs on {name}.", name=custom.name))
        elif found:
            self.models_label.setText(t("Found: {path}", path=found))
        else:
            self.models_label.setText(t(
                "{binary} is not on your PATH, so cleanup would fail and the raw "
                "transcript would be pasted. Install it, or pick another one "
                "above.", binary=binary,
            ))

    def _assistant_provider_changed(self):
        provider = self.assistant_provider.currentData() or "claude"
        who = providers.provider(self.conf, provider)
        self.claude_box.setVisible(provider == "claude")
        self.codex_box.setVisible(provider == "codex")
        self.agy_box.setVisible(provider == "antigravity")
        gateway = provider.startswith("user/")
        self.gateway_box.setVisible(gateway)
        if gateway and who is not None:
            self.gateway_box.setTitle(who.name)
        self.how_form.setRowVisible(self.assistant_reasoning,
                                    provider != "antigravity")
        self._refresh_assistant_status()

    def _meeting_provider_changed(self):
        provider = self.meeting_provider.currentData() or "local"
        is_gateway = provider.startswith("user/")
        # The row widget is the container with combo+fetch; fall back to combo for older builds
        row_widget = getattr(self, "meeting_model_row", self.meeting_model)
        try:
            self.meeting_form.setRowVisible(row_widget, is_gateway)
        except Exception:
            try:
                self.meeting_form.setRowVisible(self.meeting_model, is_gateway)
            except Exception:
                pass
        # Ensure combo itself reflects hidden state for test compatibility (isHidden checks own flag)
        try:
            self.meeting_model.setVisible(is_gateway)
        except Exception:
            pass
        # Toggle fetch button visibility as well (row hides it, but keep explicit)
        if hasattr(self, "refresh_meeting_models"):
            try:
                self.refresh_meeting_models.setVisible(is_gateway)
            except Exception:
                pass
        if hasattr(self, "meeting_models_label"):
            try:
                self.meeting_models_label.setVisible(is_gateway)
            except Exception:
                pass
        if is_gateway:
            pass

    def _refresh_assistant_status(self):
        provider = self.assistant_provider.currentData() or "claude"
        who = providers.provider(self.conf, provider)
        binary = assistant.executable(provider)
        found = shutil.which(binary) if binary else ""
        if who is not None and who.custom:
            self.assistant_found.setText(
                t("Needs no program installed, only the {service} key.",
                  service=who.name)
            )
        elif found:
            self.assistant_found.setText(t("Found: {path}", path=found))
        else:
            self.assistant_found.setText(t(
                "{binary} is not on your PATH, so this cannot run yet. Install "
                "it, or pick another one above.", binary=binary,
            ))
        age = assistant.session_age()
        if age is None:
            self.assistant_session_status.setText(t("No conversation going."))
        else:
            self.assistant_session_status.setText(
                t("Last used {minutes} min ago.", minutes=int(age // 60))
            )

    def _refresh_engine_card(self):
        """Update the sidebar engine card to show the selected transcribe provider/model."""
        try:
            provider = self.transcribe_provider.currentData() if hasattr(self, "transcribe_provider") else "local"
            # Resolve provider label
            try:
                who = providers.provider(self.conf, provider)
                label = who.name if who else provider
            except Exception:
                label = provider or "local"
            # Resolve model text
            model_text = ""
            try:
                if provider == "local":
                    model_text = self.local_whisper.selected() if hasattr(self, "local_whisper") else self.conf.get("local_model", "")
                elif provider in ("openai", "groq", "deepgram"):
                    # per-provider model setting
                    model_key = cfg.TRANSCRIBERS.get(provider).model if provider in cfg.TRANSCRIBERS else ""
                    model_text = self._models.get(provider, "") or self.conf.get(model_key, "")
                    # Also try current combo text if visible
                    if hasattr(self, "transcribe_model") and self.transcribe_model.isVisible():
                        model_text = self.transcribe_model.currentText().strip() or model_text
                elif provider.startswith("user/"):
                    model_text = providers.custom_model(self.conf, provider, "transcription")
                    if hasattr(self, "transcribe_model") and self.transcribe_model.isVisible():
                        # If combo visible, use its current text
                        cur = self.transcribe_model.currentText().strip()
                        if cur:
                            model_text = cur
                else:
                    # fallback
                    if hasattr(self, "transcribe_model"):
                        model_text = self.transcribe_model.currentText().strip()
            except Exception:
                pass
            if hasattr(self, "shell") and hasattr(self.shell, "set_engine_model"):
                self.shell.set_engine_model(label, model_text)
        except Exception:
            pass

    def _on_sidebar_compact_toggled(self, compact):
        compact = bool(compact)
        self._user_compact = compact
        try:
            self.conf["sidebar_compact"] = compact
            self.conf.save()
        except Exception:
            pass
        # keep responsive: if window is narrow, stay compact regardless
        try:
            if self.width() < 920 and not compact:
                # user expanded while narrow — allow but will re-compact on next resize
                pass
        except Exception:
            pass

    def _ai_edit_changed(self, level):
        try:
            level = max(1, min(5, int(level)))
        except Exception:
            level = 3
        try:
            if hasattr(self, "ai_edit_spin"):
                self.ai_edit_spin.blockSignals(True)
                self.ai_edit_spin.setValue(level)
                self.ai_edit_spin.blockSignals(False)
            if hasattr(self, "ai_edit_level") and hasattr(self.ai_edit_level, "set_active"):
                self.ai_edit_level.set_active(level)
        except Exception:
            pass
        self._update_ai_descriptions()

    def _ai_shortening_changed(self, value):
        """Deprecated: Shortening Freedom removed, folded into Editing Level. No-op for compat."""
        self._update_ai_descriptions()

    def _update_ai_descriptions(self):
        try:
            edit = 3
            if hasattr(self, "ai_edit_spin"):
                try:
                    edit = int(self.ai_edit_spin.value())
                except Exception:
                    try:
                        # fallback from segmented
                        for b in getattr(self.ai_edit_level, "buttons", []):
                            if b.isChecked():
                                edit = int(b.property("value") or 3)
                                break
                    except Exception:
                        pass
            elif hasattr(self, "ai_edit_level"):
                for b in getattr(self.ai_edit_level, "buttons", []):
                    if b.isChecked():
                        try:
                            edit = int(b.property("value") or 3)
                        except Exception:
                            pass
                        break
            # descriptions — shortening folded into level:
            # L1 minimum preserve length, L2 light no shortening, L3 balanced no summarization,
            # L4 free bounded shortening allowed, L5 intensive but no unlimited summarization
            descs = {
                1: t("Only filler sounds, stutters, punctuation and obvious ASR errors are fixed. Length and structure are preserved."),
                2: t("In addition to Minimum, obvious filler words and tiny grammar glitches are cleaned. No shortening."),
                3: t("Balanced readability: sentences may be restructured, but meaning and important details are kept. No real summarization."),
                4: t("Stronger rewriting, merging redundancies, polished written language. Bounded shortening is allowed but important details must remain."),
                5: t("Intensive rewriting and moderate shortening allowed. Important facts must remain; level alone does not grant unrestricted summarization."),
            }
            if hasattr(self, "ai_edit_desc"):
                self.ai_edit_desc.setText(descs.get(edit, descs[3]))
        except Exception:
            pass

    def _reset_assistant_session(self):
        assistant.clear_session()
        self._refresh_assistant_status()

    def _choose_assistant_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self, t("Working directory"),
            self.assistant_dir.text().strip() or os.path.expanduser("~"),
        )
        if chosen:
            self.assistant_dir.setText(chosen)

    # ---- minutes ---------------------------------------------------------

    def _load_minutes(self):
        self.minutes_list.clear()
        for row in reversed(cfg.read_meetings()):
            ts = row.get("ts", "")
            title = row.get("title") or t("Meeting")
            head = meeting.format_when(ts, short=True)
            head = f"{head}  ·  {meeting.length_label(row.get('duration', 0))}"
            state = MEETING_STATUS.get(row.get("status", ""), "")
            if state:
                head += "  ·  " + t(state)
            item = QListWidgetItem(f"{title}\n{head}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.minutes_list.addItem(item)
        if not self.minutes_list.count():
            self.minutes_view.clear()
            self.minutes_retry.setEnabled(False)

    def _selected_meeting(self):
        item = self.minutes_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _show_minutes(self, *_):
        row = self._selected_meeting()
        if not row:
            self.minutes_view.clear()
            if hasattr(self, "minutes_raw_view"):
                self.minutes_raw_view.clear()
            self.minutes_retry.setEnabled(False)
            return
        doc_path, _wav = cfg.meeting_paths(row["base"])
        try:
            full = doc_path.read_text(encoding="utf-8")
        except OSError:
            self.minutes_view.setPlainText(
                row.get("error") or t("Nothing has been written yet.")
            )
            if hasattr(self, "minutes_raw_view"):
                try:
                    from meeting import read_transcript as _rt
                    # Try orphan read even when status != done/transcribed
                    raw = _rt(full) if 'full' in locals() else ""
                except Exception:
                    raw = ""
                self.minutes_raw_view.setPlainText(raw or t("Nothing has been written yet."))
            busy = self.meetings is not None and self.meetings.busy
            self.minutes_retry.setEnabled(
                self.meetings is not None and not busy and row.get("status") != "done"
            )
            return
        # Split doc into minutes vs raw via marker
        try:
            from meeting import read_transcript as _rt, TRANSCRIPT_MARKER as _TM
            raw = _rt(full)
            if _TM in full:
                minutes_part = full.split(_TM)[0].strip()
            else:
                minutes_part = full.strip()
                raw = ""
        except Exception:
            minutes_part, raw = full, ""
        self.minutes_view.setPlainText(minutes_part or t("Nothing has been written yet."))
        if hasattr(self, "minutes_raw_view"):
            self.minutes_raw_view.setPlainText(raw or t("Nothing has been written yet."))
        busy = self.meetings is not None and self.meetings.busy
        self.minutes_retry.setEnabled(
            self.meetings is not None and not busy and row.get("status") != "done"
        )

    def _retry_minutes(self):
        row = self._selected_meeting()
        if not row or self.meetings is None or self.meetings.busy:
            return
        self.meetings.run(row)
        self.minutes_retry.setEnabled(False)
        self.minutes_status.setText(t("Working…"))

    def _delete_minutes(self):
        row = self._selected_meeting()
        if not row:
            return
        if self.meetings is not None and self.meetings.running_base == row["base"]:
            QMessageBox.information(self, t("Minutes"),
                                    t("This one is being written up right now."))
            return
        if not self._confirm(
            t("Delete this meeting, its minutes and its recording?"), t("Minutes")
        ):
            return
        try:
            cfg.delete_meetings([row["base"]])
        except OSError as exc:
            QMessageBox.warning(self, t("Minutes"), t("Failed: {error}", error=exc))
        self._load_minutes()

    def _save_minutes_md(self):
        """Save the selected meeting's canonical Markdown document."""
        row = self._selected_meeting()
        if not row:
            self.minutes_status.setText(t("Pick a meeting first."))
            return
        base = row.get("base", "")
        if not base:
            self.minutes_status.setText(t("Nothing has been written yet."))
            return
        doc_path, _wav = cfg.meeting_paths(base)
        try:
            content = doc_path.read_text(encoding="utf-8")
        except OSError as exc:
            # If no generated minutes but transcript exists, read whatever is there
            # The canonical document is the file itself; missing means nothing to export
            if isinstance(exc, FileNotFoundError):
                self.minutes_status.setText(t("Nothing has been written yet."))
            else:
                self.minutes_status.setText(t("Failed: {error}", error=exc))
            return
        if not content.strip():
            self.minutes_status.setText(t("Nothing has been written yet."))
            return
        # Filesystem-safe default filename from title or base
        import re
        title = row.get("title") or base
        # Remove filesystem-unsafe characters, keep alnum, dash, underscore, space
        safe = re.sub(r'[\\/:*?"<>|]+', "_", title).strip()
        safe = re.sub(r'\s+', " ", safe).strip()[:60] or base
        if not safe.lower().endswith(".md"):
            safe += ".md"
        # Default directory: meetings dir
        try:
            default_dir = str(cfg.MEETINGS_DIR)
        except Exception:
            default_dir = os.path.expanduser("~")
        start = os.path.join(default_dir, safe)
        path, _ = QFileDialog.getSaveFileName(
            self, t("Save as .md"), start, f"{t('Markdown files')} (*.md);;{t('All files')} (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".md"):
            path += ".md"
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self.minutes_status.setText(t("Saved: {path}", path=path))
        except OSError as exc:
            self.minutes_status.setText(t("Failed: {error}", error=exc))
            QMessageBox.warning(self, t("Minutes"), t("Failed: {error}", error=exc))

    def _on_minutes_progress(self, _base, message):
        self.minutes_status.setText(message)

    def _on_minutes_finished(self, _base, title):
        self.minutes_status.setText(t("Done: {title}", title=title))
        self._load_minutes()

    def _on_minutes_failed(self, _base, error):
        self.minutes_status.setText(t("Failed: {error}", error=error))
        self._load_minutes()

    # ---- history ---------------------------------------------------------

    def _load_history(self):
        # Also refresh voice jobs list
        try:
            self._load_voice_jobs()
        except Exception:
            pass
        self.history.clear()
        for row in reversed(cfg.read_history(self.conf["history_limit"])):
            text = (row.get("text") or "").replace("\n", " ")
            preview = text[:110] + ("…" if len(text) > 110 else "")
            header = t("{ts}  ({duration} s)",
                       ts=row.get("ts", ""), duration=row.get("duration", 0))
            if row.get("mode") == "ask":
                asked = (row.get("question") or row.get("raw") or "").replace("\n", " ")
                header += t("  ·  asked Claude: {question}",
                            question=asked[:60] + ("…" if len(asked) > 60 else ""))
            item = QListWidgetItem(f"{header}\n{preview}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.history.addItem(item)

    def _selected_rows(self):
        """Selected entries, newest first, the order they are listed in."""
        items = sorted(self.history.selectedItems(), key=self.history.row)
        return [item.data(Qt.ItemDataRole.UserRole) for item in items]

    def _copy_history(self):
        rows = self._selected_rows()
        if rows:
            QGuiApplication.clipboard().setText(
                "\n\n".join(row.get("text", "") for row in rows)
            )

    def _delete_history(self):
        rows = self._selected_rows()
        if not rows:
            return
        if len(rows) > 1 and not self._confirm(
            t("Delete the {count} selected entries?", count=len(rows))
        ):
            return
        self._rewrite_history(lambda: cfg.delete_history(rows))

    def _clear_history(self):
        if not self.history.count():
            return
        if not self._confirm(t("Delete the whole history? This cannot be undone.")):
            return
        self._rewrite_history(cfg.clear_history)

    def _confirm(self, question, title=None):
        answer = QMessageBox.question(
            self, title or t("History"), question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _rewrite_history(self, action):
        try:
            action()
        except OSError as exc:
            QMessageBox.warning(self, t("History"), t("Failed: {error}", error=exc))
        self._load_history()

    # ---- voice jobs retry ------------------------------------------------

    def _load_voice_jobs(self):
        """Populate the Failed but recoverable voice jobs list."""
        if not hasattr(self, "voice_jobs_list"):
            return
        self.voice_jobs_list.clear()
        try:
            import voice_jobs as _vj
            jobs = [j for j in _vj.read_voice_jobs() if _vj.is_retryable(j)]
        except Exception:
            jobs = []
        for job in reversed(jobs):
            kind = job.get("kind", "?")
            ts = job.get("ts", "")
            err_stage = job.get("error_stage", "")
            err_msg = (job.get("error_message") or "")[:60]
            label = f"{kind} · {ts} · {err_stage}: {err_msg}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, job)
            self.voice_jobs_list.addItem(item)
        if hasattr(self, "voice_jobs_retry_btn"):
            self.voice_jobs_retry_btn.setEnabled(bool(jobs))

    def _retry_voice_job(self):
        """Retry the selected failed voice job via the controller if available."""
        if not hasattr(self, "voice_jobs_list"):
            return
        item = self.voice_jobs_list.currentItem()
        if item is None:
            items = [self.voice_jobs_list.item(i) for i in range(self.voice_jobs_list.count())]
            if not items:
                return
            item = items[0]
            self.voice_jobs_list.setCurrentItem(item)
        job = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not job or not job.get("id"):
            return
        job_id = job["id"]
        # Prefer app controller (dikte.py retry helpers); fallback to pipeline directly
        for attr in ("dashboard_window",):
            pass
        ctrl = None
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                for w in app.topLevelWidgets():
                    if hasattr(w, "retry_voice_job"):
                        ctrl = w
                        break
        except Exception:
            pass
        # Fallback: try to find Dikte controller via parent chain
        if ctrl is None:
            try:
                # settings_ui is hosted; check if caller passed controller
                ctrl = getattr(self, "_controller", None)
            except Exception:
                ctrl = None
        # Try controller first
        ok = False
        if ctrl is not None and hasattr(ctrl, "retry_voice_job"):
            try:
                ok = bool(ctrl.retry_voice_job(job_id))
            except Exception:
                ok = False
        if not ok:
            # Direct pipeline retry (no controller available in test)
            try:
                import voice_jobs as _vj
                kind = job.get("kind") or "dictation"
                cp = _vj.retry_checkpoint(job)
                if cp is None:
                    self.voice_jobs_list.clearSelection()
                    return
                # Show working state on the list item
                item.setText(item.text() + f"  ·  {t('Retrying…')}")
            except Exception:
                pass
        # Refresh list in a moment
        from PyQt6.QtCore import QTimer as _Q
        _Q.singleShot(800, self._load_voice_jobs)

    def _show_history_details(self, item=None):
        if item is None:
            items = self.history.selectedItems()
            if not items:
                return
            item = items[0]
        row = item.data(Qt.ItemDataRole.UserRole)
        if row is not None:
            dlg = HistoryDetailsDialog(row, self)
            dlg.exec()

    # ---- dirty guard (T-1) ------------------------------------------

    def _snapshot_settings(self):
        """Project current widget values into a dict snapshot for dirty check."""
        out = {}
        try:
            out["ui_language"] = (self.ui_language.currentData() or "auto") if hasattr(self, "ui_language") else "auto"
            out["mic_target"] = (self.mic.currentData() or "") if hasattr(self, "mic") else ""
            out["language"] = (self.language.currentData() or "auto") if hasattr(self, "language") else "auto"
            out["auto_paste"] = bool(self.auto_paste.isChecked()) if hasattr(self, "auto_paste") else False
            out["paste_shortcut"] = (self.paste_shortcut.currentText().strip() if hasattr(self, "paste_shortcut") else "")
            out["restore_clipboard"] = bool(self.restore_clipboard.isChecked()) if hasattr(self, "restore_clipboard") else False
            out["overlay_corner"] = (self.corner.currentData() or "bottom-left") if hasattr(self, "corner") else "bottom-left"
            out["max_seconds"] = int(self.max_seconds.value()) if hasattr(self, "max_seconds") else 300
            out["skip_silent"] = bool(self.skip_silent.isChecked()) if hasattr(self, "skip_silent") else True
            out["live_transcript"] = bool(self.live_transcript.isChecked()) if hasattr(self, "live_transcript") else True
            out["keep_audio"] = bool(self.keep_audio.isChecked()) if hasattr(self, "keep_audio") else False
            out["transcribe_provider"] = (self.transcribe_provider.currentData() or "local") if hasattr(self, "transcribe_provider") else "local"
            out["transcribe_model"] = (self.transcribe_model.currentText().strip() if hasattr(self, "transcribe_model") else "")
            out["cleanup_enabled"] = bool(self.cleanup_enabled.isChecked()) if hasattr(self, "cleanup_enabled") else True
            out["cleanup_provider"] = (self.cleanup_provider.currentData() or "local") if hasattr(self, "cleanup_provider") else "local"
            out["transcribe_prompt"] = (self.transcribe_prompt.toPlainText().strip() if hasattr(self, "transcribe_prompt") else "")
            out["cleanup_prompt"] = (self.cleanup_prompt.toPlainText().strip() if hasattr(self, "cleanup_prompt") else "")
            out["assistant_provider"] = (self.assistant_provider.currentData() or "claude") if hasattr(self, "assistant_provider") else "claude"
            out["meeting_provider"] = (self.meeting_provider.currentData() or "local") if hasattr(self, "meeting_provider") else "local"
            out["ai_edit_level"] = 3
            if hasattr(self, "ai_edit_spin"):
                try: out["ai_edit_level"] = int(self.ai_edit_spin.value())
                except Exception: pass
            elif hasattr(self, "ai_edit_level"):
                for b in getattr(self.ai_edit_level, "buttons", []):
                    if b.isChecked():
                        try: out["ai_edit_level"] = int(b.property("value") or 3)
                        except Exception: pass
                        break
            out["history_limit"] = int(self.history_limit.value()) if hasattr(self, "history_limit") else 200
        except Exception:
            pass
        return out

    def _is_dirty(self):
        try:
            baseline = getattr(self, "_baseline", None)
            if baseline is None:
                return False
            cur = self._snapshot_settings()
            return cur != baseline
        except Exception:
            return False

    def _prompt_unsaved(self):
        """Show Save/Discard/Cancel. Returns 'save'|'discard'|'cancel'."""
        from PyQt6.QtWidgets import QMessageBox as _MB
        box = _MB(self)
        box.setWindowTitle(t("Dikte Settings"))
        box.setText(t("You have unsaved changes. Save before leaving?"))
        save_btn = box.addButton(t("Save"), _MB.ButtonRole.AcceptRole)
        discard_btn = box.addButton(t("Discard"), _MB.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(t("Cancel"), _MB.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            return "save"
        if clicked == discard_btn:
            return "discard"
        return "cancel"

    def _on_tab_change_requested(self, new_index):
        if getattr(self, "_navigating", False):
            # internal navigation (our own revert or programmatic)
            self._prev_index = new_index
            return
        prev = getattr(self, "_prev_index", -1)
        if prev == new_index:
            self._prev_index = new_index
            return
        if not self._is_dirty():
            self._prev_index = new_index
            return
        # dirty — gate the switch
        self._navigating = True
        # revert visually first
        try:
            self.tabs.blockSignals(True)
            self.shell.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(prev)
            self.shell.tabs.setCurrentIndex(prev)
        finally:
            self.tabs.blockSignals(False)
            self.shell.tabs.blockSignals(False)
        choice = self._prompt_unsaved()
        if choice == "save":
            self._save()
            try:
                self._baseline = self._snapshot_settings()
            except Exception:
                pass
            self._navigating = False
            self._prev_index = prev
            # now allow the requested navigation
            self._navigating = True
            try:
                self.tabs.setCurrentIndex(new_index)
                self.shell.tabs.setCurrentIndex(new_index)
            finally:
                self._navigating = False
            self._prev_index = new_index
        elif choice == "discard":
            self._baseline = self._snapshot_settings()
            # keep current dirty values? User said discard → reload from conf
            try:
                self._load()
                self._baseline = self._snapshot_settings()
            except Exception:
                pass
            self._navigating = False
            self._prev_index = prev
            self._navigating = True
            try:
                self.tabs.setCurrentIndex(new_index)
                self.shell.tabs.setCurrentIndex(new_index)
            finally:
                self._navigating = False
            self._prev_index = new_index
        else:  # cancel
            self._navigating = False

    def closeEvent(self, event):
        if self._is_dirty():
            choice = self._prompt_unsaved()
            if choice == "save":
                self._save()
                try:
                    self._baseline = self._snapshot_settings()
                except Exception:
                    pass
                event.accept()
            elif choice == "discard":
                event.accept()
            else:
                event.ignore()
                return
        super().closeEvent(event)

    def _history_menu(self, pos):
        item = self.history.itemAt(pos)
        if item is not None and not item.isSelected():
            self.history.setCurrentItem(item)
        menu = QMenu(self)
        details = menu.addAction(t("Details…"))
        details.setEnabled(item is not None)
        menu.addSeparator()
        copy = menu.addAction(t("Copy selected to clipboard"))
        delete = menu.addAction(t("Delete selected"))
        menu.addSeparator()
        clear = menu.addAction(t("Clear history"))
        has_selection = bool(self.history.selectedItems())
        copy.setEnabled(has_selection)
        delete.setEnabled(has_selection)
        clear.setEnabled(self.history.count() > 0)
        chosen = menu.exec(self.history.viewport().mapToGlobal(pos))
        if chosen is details:
            self._show_history_details(item)
        elif chosen is copy:
            self._copy_history()
        elif chosen is delete:
            self._delete_history()
        elif chosen is clear:
            self._clear_history()

    # ---- theme -----------------------------------------------------------

    def _toggle_theme(self):
        self._theme = "light" if self._theme == "dark" else "dark"
        _theme.apply(self._theme)
        self.shell.set_theme(self._theme)
        # Refresh overlay windows (top-level, not children) so tint updates live
        try:
            from PyQt6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if w.__class__.__name__ == "Overlay" and hasattr(w, "update"):
                    w.update()
                if w.__class__.__name__ == "ThinkingPopup" and hasattr(w, "_apply_theme"):
                    try:
                        w._apply_theme()
                    except Exception:
                        pass
            # Refresh inline-styled widgets inside settings window
            for widget in self.findChildren(QWidget):
                try:
                    if hasattr(widget, "_refresh_palette"):
                        widget._refresh_palette()
                    if hasattr(widget, "_apply_active"):
                        widget._apply_active()
                    if hasattr(widget, "_apply_theme"):
                        # Avoid recursing into self
                        if widget is not self:
                            widget._apply_theme()
                except Exception:
                    pass
            # Ensure all children repolish
            for widget in self.findChildren(QWidget):
                try:
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
                except Exception:
                    pass
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            w = self.width()
            # 920: collapse sidebar (226->64) — responsive auto, but respect manual preference when wide
            if hasattr(self, "shell") and hasattr(self.shell, "setCompact"):
                auto_compact = w < 920
                if auto_compact:
                    self.shell.setCompact(True)
                else:
                    # when wide, restore user's manual choice rather than forcing expanded
                    user_compact = getattr(self, "_user_compact", None)
                    if user_compact is not None:
                        self.shell.setCompact(bool(user_compact))
                    else:
                        # fallback to persisted config
                        try:
                            self.shell.setCompact(bool(self.conf.get("sidebar_compact", False)))
                        except Exception:
                            self.shell.setCompact(False)
            # Narrow rows <760
            is_narrow = w < 760
            try:
                from ui.widgets import SettingRow
                for row in self.findChildren(SettingRow):
                    row.setNarrow(is_narrow)
            except Exception:
                pass
            # Page margins <1080
            try:
                from ui.pages import apply_page_margins_for_width
                apply_page_margins_for_width(self, w)
            except Exception:
                pass
            # Provider grid: keep key/credential column always visible; responsive stacking
            # is handled by scroll area and row wrapping, not by hiding the key editor.
            # The previous <1080 hide hid the Deepgram key field at default 1000px width.
        except Exception:
            pass

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _prompt_page(tabs, title, intro, default):
        """A tab holding one editable prompt, and returns its box."""
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(intro)
        label.setWordWrap(True)
        layout.addWidget(label)
        box = QPlainTextEdit()
        layout.addWidget(box, 1)
        reset = QPushButton(t("Reset to default"))
        reset.clicked.connect(lambda: box.setPlainText(default()))
        layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignRight)
        tabs.addTab(page, title)
        return box

    @staticmethod
    def _shortcut_box(placeholder=""):
        """The field a global shortcut is typed or picked in."""
        box = QComboBox()
        box.setEditable(True)
        name = hotkey.desktop_name()
        if name == "macOS":
            box.addItems(MAC_SHORTCUTS)
        elif name == "Windows":
            box.addItems(WIN_SHORTCUTS)
        else:
            box.addItems(SHORTCUTS)
        box.setCurrentText("")
        if placeholder:
            box.lineEdit().setPlaceholderText(placeholder)
        return box

    def _shortcut_row(self, form, which, label, missing, placeholder="",
                      tooltip=""):
        """One global shortcut: the combination, Install, Remove, and a line
        saying what the desktop has registered."""
        box = self._shortcut_box(placeholder or t("none"))
        if tooltip:
            box.setToolTip(tooltip)
        form.addRow(label, self._row(box, *self._install_buttons(
            lambda: self._install_shortcut(which),
            lambda: self._remove_shortcut(which),
        )))
        status = QLabel("")
        status.setWordWrap(True)
        form.addRow(status)
        # Handle duplicate which (e.g. ask/meeting appear both in their own page and in Shortcuts tab):
        # keep the first as canonical for save, but sync the second to it.
        if which in self._shortcut_rows:
            # Existing canonical row for this shortcut
            canonical_box, canonical_status, _ = self._shortcut_rows[which]
            # Sync new box to canonical initially
            try:
                box.blockSignals(True)
                box.setCurrentText(canonical_box.currentText())
                box.blockSignals(False)
            except Exception:
                pass
            # Bidirectional sync without recursion
            def _sync_from_canonical(text):
                if box.currentText() != text:
                    box.blockSignals(True)
                    box.setCurrentText(text)
                    box.blockSignals(False)
            def _sync_to_canonical(text):
                if canonical_box.currentText() != text:
                    canonical_box.blockSignals(True)
                    canonical_box.setCurrentText(text)
                    canonical_box.blockSignals(False)
            try:
                canonical_box.currentTextChanged.connect(_sync_from_canonical)
                box.currentTextChanged.connect(_sync_to_canonical)
            except Exception:
                pass
            # Also sync status labels via refresh
            # Keep canonical in dict, store extra for refresh
            if not hasattr(self, "_shortcut_rows_extra"):
                self._shortcut_rows_extra = {}
            self._shortcut_rows_extra.setdefault(which, []).append((box, status, missing))
        else:
            self._shortcut_rows[which] = (box, status, missing)
        return box

    @staticmethod
    def _install_buttons(install_handler, remove_handler):
        """Install and Remove, where this system has somewhere to install into."""
        if not hotkey.installs_shortcuts():
            return []
        install = QPushButton(t("Install as a {desktop} shortcut",
                                desktop=hotkey.desktop_name()))
        install.clicked.connect(install_handler)
        remove = QPushButton(t("Remove"))
        remove.clicked.connect(remove_handler)
        return [install, remove]

    @staticmethod
    def _row(*widgets):
        """Widgets side by side in one form row; the first one takes the space."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for index, widget in enumerate(widgets):
            layout.addWidget(widget, 1 if index == 0 else 0)
        holder = QWidget()
        holder.setLayout(layout)
        return holder

    # ---- load / save ----------------------------------------------------

    def _load(self):
        conf = self.conf
        self._select_data(self.ui_language, conf["ui_language"])
        self._select_data(self.mic, conf["mic_target"])
        self._select_data(self.language, conf["language"])
        self.auto_paste.setChecked(conf["auto_paste"])
        self.paste_shortcut.setCurrentText(conf["paste_shortcut"])
        self.restore_clipboard.setChecked(conf["restore_clipboard"])
        self._select_data(self.corner, conf["overlay_corner"])
        self.max_seconds.setValue(conf["max_seconds"])
        self.skip_silent.setChecked(conf["skip_silent"])
        self.live_transcript.setChecked(conf["live_transcript"])
        self.silence_db.setValue(int(conf["silence_db"]))
        self.filter_hallucinations.setChecked(conf["filter_hallucinations"])
        self.keep_audio.setChecked(conf["keep_audio"])

        for pid, field in self._key_fields.items():
            field.setText(conf[KEY_SETTINGS[pid]])
        for name, who in cfg.TRANSCRIBERS.items():
            self._models[name] = conf[who.model]
        self._refresh_providers()
        for pid, who in providers.definitions(conf).items():
            if who.custom:
                self._models[pid] = providers.custom_model(
                    conf, pid, "transcription")
        self._shown_provider = ""
        self._select_data(self.transcribe_provider, conf["transcribe_provider"])
        self._provider_changed()  # selecting index 0 fires no signal
        self.local_gpu.setChecked(conf["local_gpu"])
        self.local_preload.setChecked(conf["local_preload"])
        self.local_threads.setValue(int(conf["local_threads"]))
        self.local_whisper.load(conf["local_model"])

        self.cleanup_enabled.setChecked(conf["cleanup_enabled"])
        chosen_cleanup = conf["cleanup_provider"]
        self.cleanup_model.setCurrentText(
            providers.custom_model(conf, chosen_cleanup, "text")
            if chosen_cleanup.startswith("user/") else conf["cleanup_model"])
        self.cleanup_claude_model.setCurrentText(conf["cleanup_claude_model"])
        self.cleanup_codex_model.setCurrentText(
            conf["cleanup_codex_model"] or t("Codex's own default")
        )
        self.cleanup_agy_model.setCurrentText(
            conf["cleanup_agy_model"] or cfg.DEFAULTS["cleanup_agy_model"])
        self._select_data(self.cleanup_provider, conf["cleanup_provider"])
        self._cleanup_provider_changed()  # selecting index 0 fires no signal
        self._select_data(self.cleanup_reasoning, conf["cleanup_reasoning"])
        self.local_llm_gpu.setChecked(conf["local_llm_gpu"])
        self.local_llm_preload.setChecked(conf["local_llm_preload"])
        self._select_data(self.local_llm_reasoning, conf["local_llm_reasoning"])
        self.local_llm.load(conf["local_llm_model"], conf["local_llm_repo"])
        self.cleanup_prompt.setPlainText(conf["cleanup_prompt"] or cfg.default_cleanup_prompt())
        self.file_cleanup_prompt.setPlainText(
            conf["file_cleanup_prompt"] or cfg.default_file_cleanup_prompt()
        )
        self.transcribe_prompt.setPlainText(conf["transcribe_prompt"])
        # AI Text Processing — single Editing Level (shortening folded into level)
        try:
            edit_level = max(1, min(5, int(conf.get("ai_edit_level", 3))))
        except Exception:
            edit_level = 3
        try:
            if hasattr(self, "ai_edit_level") and hasattr(self.ai_edit_level, "set_active"):
                self.ai_edit_level.set_active(edit_level)
        except Exception:
            pass
        try:
            if hasattr(self, "ai_edit_spin"):
                self.ai_edit_spin.blockSignals(True)
                self.ai_edit_spin.setValue(edit_level)
                self.ai_edit_spin.blockSignals(False)
        except Exception:
            pass
        # Old shortening is ignored; no UI to load
        try:
            self._update_ai_descriptions()
        except Exception:
            pass

        self._select_data(self.assistant_provider, conf["assistant_provider"])
        self.assistant_model.setCurrentText(conf["assistant_model"])
        self._select_data(self.assistant_permission, conf["assistant_permission_mode"])
        self.assistant_codex_model.setCurrentText(conf["assistant_codex_model"])
        self.assistant_agy_model.setCurrentText(
            conf["assistant_agy_model"] or cfg.DEFAULTS["assistant_agy_model"])
        self._select_data(self.assistant_codex_sandbox, conf["assistant_codex_sandbox"])
        self.assistant_gateway_model.setCurrentText(
            providers.custom_model(conf, conf["assistant_provider"], "assistant"))
        self._assistant_provider_changed()  # selecting index 0 fires no signal
        self._select_data(self.assistant_reasoning, conf["assistant_reasoning"])
        self.assistant_dir.setText(conf["assistant_dir"])
        self.assistant_timeout.setValue(int(conf["assistant_timeout"]))
        self.assistant_session_minutes.setValue(int(conf["assistant_session_minutes"]))
        self.assistant_paste.setChecked(conf["assistant_paste"])
        self.assistant_cleanup.setChecked(conf["assistant_cleanup"])
        self.assistant_prompt.setPlainText(
            conf["assistant_prompt"] or cfg.default_assistant_prompt()
        )

        self._select_data(self.meeting_mic, conf["meeting_mic_target"])
        self._select_data(self.meeting_system, conf["meeting_system_target"])
        self.meeting_self_name.setText(conf["meeting_self_name"])
        self.meeting_other_name.setText(conf["meeting_other_name"])
        self.meeting_participants.setPlainText(conf["meeting_participants"])
        self._select_data(self.meeting_provider, conf["meeting_provider"])
        chosen_minutes = conf["meeting_provider"]
        self.meeting_model.setCurrentText(
            providers.custom_model(conf, chosen_minutes, "minutes")
            if chosen_minutes.startswith("user/") else conf["meeting_model"])
        self._meeting_provider_changed()  # selecting index 0 fires no signal
        self._select_data(self.meeting_reasoning, conf["meeting_reasoning"])
        self._select_data(self.meeting_language, conf["meeting_language"])
        self._select_data(self.meeting_mine_language,
                          conf["meeting_mine_language"])
        self._select_data(self.meeting_theirs_language,
                          conf["meeting_theirs_language"])
        self.meeting_cleanup.setChecked(conf["meeting_cleanup"])
        self.meeting_max_minutes.setValue(max(5, int(conf["meeting_max_seconds"]) // 60))
        self.meeting_keep_audio.setChecked(conf["meeting_keep_audio"])
        self.meeting_retention.setValue(int(conf["meeting_audio_retention_days"]))
        self.meeting_prompt.setPlainText(
            conf["meeting_prompt"] or cfg.default_meeting_prompt()
        )

        self.file_timestamps.setChecked(conf["file_timestamps"])
        self.file_cleanup.setChecked(conf["file_cleanup"])
        self.file_path = ""

        try:
            if hasattr(self, "result_overlay_enabled"):
                self.result_overlay_enabled.setChecked(bool(conf.get("result_overlay_enabled", True)))
        except Exception:
            pass

        for which, (box, _status, _missing) in self._shortcut_rows.items():
            box.setCurrentText(conf[hotkey.SHORTCUTS[which].setting])
        self.evdev_enabled.setChecked(conf["evdev_hotkey"])

        self.history_limit.setValue(max(0, int(conf["history_limit"])))

        QTimer.singleShot(0, self._deferred_load)

    def _deferred_load(self):
        for which in self._shortcut_rows:
            self._refresh_shortcut_status(which)
        self._refresh_assistant_status()
        self._load_history()
        self._load_minutes()
        # Deferred work off the GUI thread: CLI versions and audio devices
        try:
            self._fetch_cli_versions(providers.definitions(self.conf))
        except Exception:
            pass
        QTimer.singleShot(0, self._load_audio_devices)

    def _load_audio_devices(self):
        """Enumerate microphones/monitors off the GUI thread."""
        def work():
            try:
                sources = audio.cached_list_sources()
            except Exception:
                sources = []
            try:
                monitors = audio.cached_list_monitors()
            except Exception:
                monitors = []
            try:
                mic_default = audio.default_input()
            except Exception:
                mic_default = ""
            try:
                out_default = audio.default_monitor()
            except Exception:
                out_default = ""
            try:
                self._audio_sources_loaded.emit(sources)
                self._audio_monitors_loaded.emit(monitors)
                self._audio_defaults_loaded.emit(mic_default, out_default)
            except RuntimeError:
                # The window went away while the enumeration was running;
                # there is nobody left to hand the answer to.
                pass
        threading.Thread(target=work, daemon=True).start()

    def _on_audio_defaults_loaded(self, mic_default, out_default):
        """Name the automatic choices: which device they resolve to."""
        try:
            if hasattr(self, "mic") and mic_default:
                self.mic.setItemText(
                    0, f"{t('Default microphone')} — {mic_default}")
            if hasattr(self, "meeting_mic"):
                resolved = self.conf["mic_target"] or mic_default
                label = t("Same as dictation") + (
                    f" — {resolved}" if resolved else "")
                self.meeting_mic.setItemText(0, label)
            if hasattr(self, "meeting_system") and out_default:
                self.meeting_system.setItemText(
                    0, f"{t('Current output')} — {out_default}")
        except Exception:
            pass

    def _on_audio_sources_loaded(self, sources):
        # Fill mic combos: General mic + Meeting mic (if present)
        # Preserve current selection
        try:
            cur_mic = self.mic.currentData() if hasattr(self, "mic") else ""
            cur_meet_mic = self.meeting_mic.currentData() if hasattr(self, "meeting_mic") else ""
            # General mic
            if hasattr(self, "mic"):
                cur = cur_mic
                self.mic.blockSignals(True)
                # keep first entry (default), rebuild rest
                while self.mic.count() > 1:
                    self.mic.removeItem(1)
                for name, desc in sources:
                    self.mic.addItem(desc, name)
                idx = self.mic.findData(cur)
                if idx >= 0:
                    self.mic.setCurrentIndex(idx)
                self.mic.blockSignals(False)
            # Meeting mic
            if hasattr(self, "meeting_mic"):
                cur = cur_meet_mic
                self.meeting_mic.blockSignals(True)
                while self.meeting_mic.count() > 1:
                    self.meeting_mic.removeItem(1)
                for name, desc in sources:
                    self.meeting_mic.addItem(desc, name)
                idx = self.meeting_mic.findData(cur)
                if idx >= 0:
                    self.meeting_mic.setCurrentIndex(idx)
                self.meeting_mic.blockSignals(False)
        except Exception:
            pass

    def _on_audio_monitors_loaded(self, monitors):
        try:
            if not hasattr(self, "meeting_system"):
                return
            cur = self.meeting_system.currentData() if hasattr(self, "meeting_system") else ""
            self.meeting_system.blockSignals(True)
            while self.meeting_system.count() > 1:
                self.meeting_system.removeItem(1)
            for name, desc in monitors:
                self.meeting_system.addItem(desc, name)
            idx = self.meeting_system.findData(cur)
            if idx >= 0:
                self.meeting_system.setCurrentIndex(idx)
            self.meeting_system.blockSignals(False)
        except Exception:
            pass

    def _save(self):
        conf = self.conf
        conf["ui_theme"] = self._theme
        conf["ui_language"] = self.ui_language.currentData() or "auto"
        conf["mic_target"] = self.mic.currentData() or ""
        conf["language"] = self.language.currentData() or "auto"
        conf["auto_paste"] = self.auto_paste.isChecked()
        conf["paste_shortcut"] = self.paste_shortcut.currentText().strip()
        conf["restore_clipboard"] = self.restore_clipboard.isChecked()
        conf["overlay_corner"] = self.corner.currentData() or "bottom-left"
        conf["max_seconds"] = self.max_seconds.value()
        conf["skip_silent"] = self.skip_silent.isChecked()
        conf["live_transcript"] = self.live_transcript.isChecked()
        conf["silence_db"] = float(self.silence_db.value())
        conf["filter_hallucinations"] = self.filter_hallucinations.isChecked()
        conf["keep_audio"] = self.keep_audio.isChecked()

        provider = self.transcribe_provider.currentData() or "local"
        if provider in self._models or provider.startswith("user/"):
            self._models[provider] = self.transcribe_model.currentText().strip()
        conf["transcribe_provider"] = provider
        if provider.startswith("user/"):
            providers.set_custom_model(conf, provider, "transcription",
                                       self._models[provider])
        for name, who in cfg.TRANSCRIBERS.items():
            conf[who.model] = self._models[name].strip() or cfg.DEFAULTS[who.model]
        for pid, setting in KEY_SETTINGS.items():
            if pid in self._key_fields:
                conf[setting] = self._key_fields[pid].text().strip()
        conf["local_model"] = self.local_whisper.selected()
        conf["local_gpu"] = self.local_gpu.isChecked()
        conf["local_preload"] = self.local_preload.isChecked()
        conf["local_threads"] = self.local_threads.value()

        conf["cleanup_enabled"] = self.cleanup_enabled.isChecked()
        cleanup_provider = self.cleanup_provider.currentData() or "local"
        conf["cleanup_provider"] = cleanup_provider
        if cleanup_provider.startswith("user/"):
            providers.set_custom_model(conf, cleanup_provider, "text",
                                       self.cleanup_model.currentText().strip())
        else:
            conf["cleanup_model"] = self.cleanup_model.currentText().strip()
        conf["cleanup_claude_model"] = (self.cleanup_claude_model.currentText().strip()
                                        or cfg.DEFAULTS["cleanup_claude_model"])
        codex_cleanup_model = self.cleanup_codex_model.currentText().strip()
        conf["cleanup_codex_model"] = (
            "" if codex_cleanup_model == t("Codex's own default") else codex_cleanup_model
        )
        conf["cleanup_agy_model"] = (self.cleanup_agy_model.currentText().strip()
                                     or cfg.DEFAULTS["cleanup_agy_model"])
        conf["cleanup_reasoning"] = self.cleanup_reasoning.currentData() or ""
        conf["local_llm_model"] = self.local_llm.selected()
        conf["local_llm_repo"] = self.local_llm.repository()
        conf["local_llm_gpu"] = self.local_llm_gpu.isChecked()
        conf["local_llm_preload"] = self.local_llm_preload.isChecked()
        conf["local_llm_reasoning"] = self.local_llm_reasoning.currentData() or ""

        prompt = self.cleanup_prompt.toPlainText().strip()
        conf["cleanup_prompt"] = "" if prompt == cfg.default_cleanup_prompt() else prompt
        file_prompt = self.file_cleanup_prompt.toPlainText().strip()
        conf["file_cleanup_prompt"] = ("" if file_prompt == cfg.default_file_cleanup_prompt()
                                       else file_prompt)
        conf["transcribe_prompt"] = self.transcribe_prompt.toPlainText().strip()

        assistant_provider = self.assistant_provider.currentData() or "claude"
        conf["assistant_provider"] = assistant_provider
        if assistant_provider.startswith("user/"):
            providers.set_custom_model(
                conf, assistant_provider, "assistant",
                self.assistant_gateway_model.currentText().strip())
        conf["assistant_model"] = (self.assistant_model.currentText().strip()
                                   or cfg.DEFAULTS["assistant_model"])
        conf["assistant_permission_mode"] = (self.assistant_permission.currentData()
                                             or "auto")
        codex_model = self.assistant_codex_model.currentText().strip()
        conf["assistant_codex_model"] = (
            "" if codex_model == t("Codex's own default") else codex_model
        )
        conf["assistant_agy_model"] = (self.assistant_agy_model.currentText().strip()
                                       or cfg.DEFAULTS["assistant_agy_model"])
        conf["assistant_codex_sandbox"] = (self.assistant_codex_sandbox.currentData()
                                           or "workspace-write")
        conf["assistant_reasoning"] = self.assistant_reasoning.currentData() or ""
        conf["assistant_dir"] = self.assistant_dir.text().strip()
        conf["assistant_timeout"] = self.assistant_timeout.value()
        conf["assistant_session_minutes"] = self.assistant_session_minutes.value()
        conf["assistant_paste"] = self.assistant_paste.isChecked()
        conf["assistant_cleanup"] = self.assistant_cleanup.isChecked()
        assistant_prompt = self.assistant_prompt.toPlainText().strip()
        conf["assistant_prompt"] = ("" if assistant_prompt == cfg.default_assistant_prompt()
                                    else assistant_prompt)

        conf["meeting_mic_target"] = self.meeting_mic.currentData() or ""
        conf["meeting_system_target"] = self.meeting_system.currentData() or ""
        conf["meeting_self_name"] = self.meeting_self_name.text().strip()
        conf["meeting_other_name"] = self.meeting_other_name.text().strip()
        conf["meeting_participants"] = self.meeting_participants.toPlainText().strip()
        conf["meeting_provider"] = self.meeting_provider.currentData() or "local"
        if conf["meeting_provider"].startswith("user/"):
            providers.set_custom_model(conf, conf["meeting_provider"], "minutes",
                                       self.meeting_model.currentText().strip())
        else:
            conf["meeting_model"] = (self.meeting_model.currentText().strip()
                                     or cfg.DEFAULTS["meeting_model"])
        conf["meeting_reasoning"] = self.meeting_reasoning.currentData() or ""
        conf["meeting_language"] = self.meeting_language.currentData() or ""
        conf["meeting_mine_language"] = (
            self.meeting_mine_language.currentData() or "")
        conf["meeting_theirs_language"] = (
            self.meeting_theirs_language.currentData() or "")
        conf["meeting_cleanup"] = self.meeting_cleanup.isChecked()
        conf["meeting_max_seconds"] = self.meeting_max_minutes.value() * 60
        conf["meeting_keep_audio"] = self.meeting_keep_audio.isChecked()
        conf["meeting_audio_retention_days"] = self.meeting_retention.value()
        meeting_prompt = self.meeting_prompt.toPlainText().strip()
        conf["meeting_prompt"] = ("" if meeting_prompt == cfg.default_meeting_prompt()
                                  else meeting_prompt)

        conf["file_timestamps"] = self.file_timestamps.isChecked()
        conf["file_cleanup"] = self.file_cleanup.isChecked()

        # AI Text Processing — single Editing Level (shortening not persisted)
        try:
            edit_val = 3
            if hasattr(self, "ai_edit_spin"):
                edit_val = int(self.ai_edit_spin.value())
            elif hasattr(self, "ai_edit_level"):
                for b in getattr(self.ai_edit_level, "buttons", []):
                    if b.isChecked():
                        edit_val = int(b.property("value") or 3)
                        break
            conf["ai_edit_level"] = max(1, min(5, int(edit_val)))
        except Exception:
            pass
        # Do NOT write ai_shortening_freedom — deprecated, removed from UI

        try:
            if hasattr(self, "result_overlay_enabled"):
                conf["result_overlay_enabled"] = bool(self.result_overlay_enabled.isChecked())
        except Exception:
            pass
        try:
            # sidebar_compact persists manual toggle; auto-compact <920 is transient
            if hasattr(self, "_user_compact"):
                conf["sidebar_compact"] = bool(self._user_compact)
            elif hasattr(self, "shell"):
                conf["sidebar_compact"] = bool(getattr(self.shell, "_compact", False))
        except Exception:
            pass

        for which, (box, _status, _missing) in self._shortcut_rows.items():
            spec = hotkey.SHORTCUTS[which]
            conf[spec.setting] = box.currentText().strip() or spec.fallback
        conf["evdev_hotkey"] = self.evdev_enabled.isChecked()
        conf["history_limit"] = self.history_limit.value()

        try:
            conf.save()
        except OSError as exc:
            QMessageBox.warning(
                self, t("Dikte Settings"),
                t("Could not save the settings: {error}", error=exc))
            return
        try:
            cfg.trim_history(conf["history_limit"])
        except OSError as exc:
            print(f"dikte: could not trim the history ({exc})", file=sys.stderr)
        self._load_history()  # the trim may just have dropped rows from the list

        try:
            self._baseline = self._snapshot_settings()
        except Exception:
            pass
        try:
            self.applied.emit()
        except Exception as exc:
            print(f"dikte: settings saved but apply failed: {exc}", file=sys.stderr)

        QMessageBox.information(self, t("Dikte Settings"), t("Saved successfully."))

    @staticmethod
    def _select_data(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

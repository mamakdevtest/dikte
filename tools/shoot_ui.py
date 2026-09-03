"""Deterministic offscreen screenshot tour (stdlib + PyQt6 only).

Builds every visible surface once per theme x language, freezes timers, and
saves one PNG per screen under --out as <theme>_<lang>_<screen>.png.

Usage:
    python tools/shoot_ui.py --out /tmp/dikte-shots \\
        --themes blue,orange --langs en,tr
"""

import atexit
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"

_SANDBOX = tempfile.mkdtemp(prefix="dikte-shots-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SANDBOX, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "data")
os.environ["HOME"] = os.path.join(_SANDBOX, "home")
os.makedirs(os.environ["HOME"], exist_ok=True)
atexit.register(shutil.rmtree, _SANDBOX, True)

for _var in ("OPENAI_API_KEY", "GROQ_API_KEY", "DEEPGRAM_API_KEY",
             "OPENROUTER_API_KEY", "LLMAPI_API_KEY", "LLM_API_KEY"):
    os.environ.pop(_var, None)
for _var in ("LC_ALL", "LC_MESSAGES", "LANG"):
    os.environ.pop(_var, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import contextlib
import urllib.request
from unittest import mock

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import config as cfg
import ggml
import hotkey
import i18n
import overlay as overlay_module
import providers
import settings_ui
from dikte import HintMenu
from ui import theme
from ui.app_window import DashboardWindow
from ui.live_popup import LivePopup
from ui.result_overlay import ResultOverlay
from ui.thinking import ThinkingPopup

# Same seed as tests/test_ui.py CHANGED: a valid non-default value for every
# setting the window shows.
CHANGED = {
    "ui_language": "tr",
    "language": "tr",
    "auto_paste": False,
    "paste_shortcut": "ctrl+shift+v",
    "restore_clipboard": True,
    "overlay_corner": "top-right",
    "max_seconds": 120,
    "skip_silent": False,
    "silence_db": -42.0,
    "filter_hallucinations": False,
    "keep_audio": True,
    "openai_api_key": "sk-test-key",
    "groq_api_key": "gsk-test-key",
    "transcribe_provider": "openai",
    "transcribe_model": "whisper-1",
    "groq_transcribe_model": "whisper-large-v3",
    "cleanup_enabled": False,
    "cleanup_provider": "local",
    "cleanup_model": "some/other-model",
    "cleanup_claude_model": "opus",
    "cleanup_codex_model": "gpt-5",
    "cleanup_agy_model": "gemini-3.5-flash-low",
    "cleanup_reasoning": "high",
    "local_model": "ggml-small.bin",
    "local_gpu": False,
    "local_preload": False,
    "local_threads": 6,
    "local_llm_model": "gemma-3-4b-it-Q4_K_M.gguf",
    "local_llm_repo": "ggml-org/gemma-4-E2B-it-GGUF",
    "local_llm_gpu": False,
    "local_llm_preload": True,
    "local_llm_reasoning": "low",
    "cleanup_prompt": "Only fix the punctuation.",
    "file_cleanup_prompt": "Keep the stamps where they are.",
    "transcribe_prompt": "Paraşüt, OpenFrame",
    "assistant_provider": "codex",
    "assistant_model": "opus",
    "assistant_permission_mode": "manual",
    "assistant_codex_model": "gpt-5",
    "assistant_codex_sandbox": "read-only",
    "assistant_agy_model": "gemini-3.1-pro-medium",
    "assistant_reasoning": "high",
    "assistant_dir": "/tmp",
    "assistant_timeout": 600,
    "assistant_session_minutes": 90,
    "assistant_paste": False,
    "assistant_cleanup": True,
    "assistant_prompt": "Answer in one sentence.",
    "assistant_shortcut": "Meta+A",
    "meeting_self_name": "Yusuf",
    "meeting_other_name": "Ayşe",
    "meeting_participants": "Mehmet",
    "meeting_model": "some/meeting-model",
    "meeting_reasoning": "medium",
    "meeting_language": "tr",
    "meeting_cleanup": False,
    "meeting_max_seconds": 7200,
    "meeting_keep_audio": True,
    "meeting_shortcut": "Meta+M",
    "meeting_prompt": "Write it as bullet points.",
    "file_timestamps": True,
    "file_cleanup": False,
    "shortcut": "Ctrl+Alt+Space",
    "cancel_shortcut": "Meta+Shift+Space",
    "evdev_hotkey": True,
    "history_limit": 50,
}

HISTORY_ROW = {
    "ts": "2026-08-21 12:00:00",
    "duration": 4.5,
    "elapsed": 1.2,
    "transcribe_provider": "openai",
    "model": "whisper-1",
    "cleanup_provider": "google",
    "cleanup_model": "google/gemini-2.5-flash",
    "language": "tr",
    "cleanup_error": "",
    "raw": "merhaba dunya",
    "text": "Merhaba dünya.",
}


def _no_network(*args, **kwargs):
    raise AssertionError("shoot_ui reached the network")


def freeze(widget):
    """Stop every timer owned by the widget so the frame is deterministic."""
    for timer in widget.findChildren(QTimer):
        try:
            timer.stop()
        except Exception:
            pass


def shoot(app, widget, path, width=None, height=None):
    widget.show()
    if width is not None and height is not None:
        widget.resize(width, height)
    freeze(widget)
    widget.update()
    app.processEvents()
    app.processEvents()
    ok = widget.grab().save(path)
    if not ok:
        raise RuntimeError(f"grab().save failed for {path}")
    return path


def build_prompt_creator(parent):
    """The meeting prompt-creator dialog, built without exec()."""
    from i18n import t

    dlg = QDialog(parent)
    dlg.setWindowTitle(t("Meeting Summary Prompts"))
    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    style_combo = QComboBox()
    for key in cfg.STYLE_KEYS:
        style_combo.addItem(cfg.STYLE_LABELS_TR.get(key, key), key)
    form.addRow(t("Style"), style_combo)
    editor = QPlainTextEdit()
    editor.setMinimumSize(600, 260)
    key = style_combo.currentData()
    if key == "auto":
        editor.setPlainText(cfg.meeting_auto_pick_prompt())
    else:
        editor.setPlainText(cfg.meeting_style_template(key))
    form.addRow(editor)
    hint = QLabel(t("Custom prompts replace the built-in format template."))
    hint.setWordWrap(True)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                               | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Save).setText(t("Save"))
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    restore = QPushButton(t("Restore default"))
    buttons.addButton(restore, QDialogButtonBox.ButtonRole.ResetRole)
    layout = QVBoxLayout(dlg)
    layout.addLayout(form)
    layout.addWidget(hint)
    layout.addWidget(buttons)
    dlg.resize(640, 420)
    return dlg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--themes", default="blue,orange")
    parser.add_argument("--langs", default="en,tr")
    args = parser.parse_args()
    themes = [t for t in args.themes.split(",") if t]
    langs = [l for l in args.langs.split(",") if l]
    os.makedirs(args.out, exist_ok=True)

    app = QApplication.instance() or QApplication([])

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(urllib.request, "urlopen", _no_network))
        stack.enter_context(mock.patch.object(providers, "executable_version",
                                              return_value="9.9.9"))
        stack.enter_context(mock.patch.object(settings_ui.SettingsWindow, "_load_models",
                                              lambda self: None))
        stack.enter_context(mock.patch.object(settings_ui.SettingsWindow,
                                              "_load_transcribe_models",
                                              lambda self: None))
        stack.enter_context(mock.patch.object(settings_ui.SettingsWindow,
                                              "_fetch_cli_versions",
                                              lambda self, defs: None))
        stack.enter_context(mock.patch.object(settings_ui.SettingsWindow,
                                              "_load_audio_devices",
                                              lambda self: None))
        stack.enter_context(mock.patch.object(ggml, "installed_whisper_models",
                                              return_value=["ggml-small.bin"]))
        stack.enter_context(mock.patch.object(ggml, "installed_llm_models",
                                              return_value=["gemma-3-4b-it-Q4_K_M.gguf"]))
        stack.enter_context(mock.patch.object(ggml, "installed_program",
                                              return_value="/usr/bin/shoot"))
        stack.enter_context(mock.patch.object(ggml, "installed_version",
                                              return_value="9.9.9"))
        stack.enter_context(mock.patch.object(ggml, "llm_repos",
                                              return_value=["ggml-org/gemma-3-4b-it-GGUF"]))
        stack.enter_context(mock.patch.object(ggml, "llm_quants", return_value=[]))
        stack.enter_context(mock.patch.object(hotkey, "installs_shortcuts",
                                              return_value=True))
        stack.enter_context(mock.patch.object(QMessageBox, "information",
                                              return_value=None))
        stack.enter_context(mock.patch.object(QMessageBox, "warning",
                                              return_value=None))
        stack.enter_context(mock.patch.object(QMessageBox, "critical",
                                              return_value=None))
        stack.enter_context(mock.patch.object(QMessageBox, "question",
                                              return_value=QMessageBox.StandardButton.No))
        stack.enter_context(mock.patch.object(sys, "platform", "linux"))
        stack.enter_context(mock.patch("shutil.which", return_value=None))

        conf = cfg.Config()
        for key, value in CHANGED.items():
            conf[key] = value
        pid = providers.add_provider(conf, "ShootGateway",
                                     "https://example.com/v1")
        try:
            providers.add_credential(conf, pid, "shot", "sk-shot-secret")
        except Exception:
            pass
        conf.save()
        cfg.append_history(dict(HISTORY_ROW))
        cfg.append_history({"ts": "2026-08-21 12:05:00", "duration": 2.0,
                            "mode": "ask",
                            "question": "What is the capital of Turkey?",
                            "assistant_provider": "claude",
                            "assistant_model": "claude-3-5-sonnet",
                            "raw": "What is the capital of Turkey?",
                            "text": "Ankara."})
        cfg.save_meeting({"base": "20260821-120000", "ts": "2026-08-21 12:00:00",
                          "title": "Shot meeting", "status": "done",
                          "duration": 600})

        count = 0
        for thm in themes:
            for lang in langs:
                theme.apply(thm)
                i18n.set_language(lang)
                tag = f"{thm}_{lang}"

                window = DashboardWindow(conf)
                window.resize(1000, 700)
                pages = window.shell.tabs.count()
                for i in range(min(pages, 11)):
                    window.shell.set_page(i)
                    count += 1 if shoot(
                        app, window,
                        os.path.join(args.out, f"{tag}_page{i:02d}.png"),
                        1000, 700) else 0
                window.close()
                window.deleteLater()
                app.processEvents()

                menu = HintMenu()
                for label, hint in (("Start dictation", "Ctrl+Alt+Space"),
                                    ("Ask the agent", "Meta+A"),
                                    ("Toggle meeting", "Meta+M")):
                    action = QAction(label, menu)
                    action.setProperty("shortcutHint", hint)
                    menu.addAction(action)
                menu.addSeparator()
                menu.show()
                freeze(menu)
                app.processEvents()
                menu.grab().save(os.path.join(args.out, f"{tag}_hintmenu.png"))
                count += 1
                menu.close()

                ov = overlay_module.Overlay(interactive_live=True)
                ov.show_recording()
                ov.set_seconds(3)
                ov.push_level(0.5)
                ov._reveal_progress = 1.0
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_rec.png"))
                count += 1
                ov.show_recording(asking=True)
                ov.set_seconds(5)
                ov._reveal_progress = 1.0
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_ask.png"))
                count += 1
                ov.show_meeting()
                ov.push_levels(0.4, 0.7)
                ov.set_seconds(12)
                ov._reveal_progress = 1.0
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_meet.png"))
                count += 1
                ov.show_busy("Transcribing…")
                ov.set_thinking_status("Cleaning up…")
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_busy.png"))
                count += 1
                ov.show_done("Pasted", None)
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_done.png"))
                count += 1
                ov.show_warning("Cleanup failed", None)
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_warn.png"))
                count += 1
                ov.show_error("No microphone", None)
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_err.png"))
                count += 1
                ov.show_paused("Paused")
                ov._reveal_progress = 1.0
                shoot(app, ov, os.path.join(args.out, f"{tag}_overlay_paused.png"))
                count += 1
                ov.close()

                res = ResultOverlay()
                res.show_result("Merhaba dünya. Bu deterministik bir önizlemedir, "
                                "kısaltılmış metin burada görünür.", msec=None)
                shoot(app, res,
                      os.path.join(args.out, f"{tag}_result_collapsed.png"))
                count += 1
                res.set_expanded(True)
                shoot(app, res,
                      os.path.join(args.out, f"{tag}_result_expanded.png"))
                count += 1
                res.close()

                live = LivePopup()
                live.set_text("merhaba dünya\nbu canlı önizleme metnidir\n"
                              "üçüncü satır burada")
                shoot(app, live,
                      os.path.join(args.out, f"{tag}_live_collapsed.png"))
                count += 1
                live.set_expanded(True)
                shoot(app, live,
                      os.path.join(args.out, f"{tag}_live_expanded.png"))
                count += 1
                live.close()

                think = ThinkingPopup()
                think.show_thinking("Transcribing…")
                think.push_stage("Cleaning up…")
                shoot(app, think, os.path.join(args.out, f"{tag}_thinking.png"))
                count += 1
                think.set_paused(True)
                shoot(app, think,
                      os.path.join(args.out, f"{tag}_thinking_paused.png"))
                count += 1
                think.close()

                prov = settings_ui.ProviderDialog()
                prov.resize(420, 160)
                shoot(app, prov,
                      os.path.join(args.out, f"{tag}_provider_dialog.png"))
                count += 1
                prov.close()

                keys = settings_ui.ProviderKeysDialog(conf, pid)
                keys.resize(520, 360)
                if keys.listw.count():
                    keys.listw.setCurrentRow(0)
                shoot(app, keys,
                      os.path.join(args.out, f"{tag}_provider_keys.png"))
                count += 1
                keys.close()

                hist = settings_ui.HistoryDetailsDialog(dict(HISTORY_ROW))
                shoot(app, hist,
                      os.path.join(args.out, f"{tag}_history_details.png"))
                count += 1
                hist.close()

                creator = build_prompt_creator(None)
                shoot(app, creator,
                      os.path.join(args.out, f"{tag}_prompt_creator.png"))
                count += 1
                creator.close()

                app.processEvents()

        print(f"wrote {count} PNGs to {args.out}")


if __name__ == "__main__":
    main()

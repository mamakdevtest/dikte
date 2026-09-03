"""API and models page: the provider registry, speech-to-text and cleanup."""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QSpinBox,
    QSizePolicy, QVBoxLayout, QWidget,
)

import ggml
from i18n import t

from ..local_models import LocalModelBox
from ..widgets import InfoNote, SectionCard, SettingRow, btn
from . import page, scrolled


def _expanding(widget, min_width):
    """Minimum width + Expanding: grows for long TR labels, never truncates."""
    widget.setMinimumWidth(min_width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class _CardForm:
    """QFormLayout-compatible shim over a SectionCard.

    settings_ui.py and tests call setRowVisible/isRowVisible; the card holds
    SettingRow wrappers, so the shim maps the inner widget to its row and
    toggles both (inner for isHidden() checks, row to collapse the space).
    """

    def __init__(self, card):
        self._card = card
        self._map = {}

    def _register(self, widget, row):
        self._map[id(widget)] = (widget, row)

    def addRow(self, *args):
        if len(args) == 1:
            (widget,) = args
            if isinstance(widget, QLabel):
                wrap = QWidget()
                lay = QHBoxLayout(wrap)
                lay.setContentsMargins(20, 0, 20, 8)
                lay.addWidget(widget, 1)
                self._card.add(wrap)
                self._register(widget, wrap)
            else:
                self._card.add(widget)
                self._register(widget, None)
            return
        if len(args) == 2:
            label, field = args
            if isinstance(label, str):
                row = SettingRow(label, "", field)
                self._card.add(row)
                self._register(field, row)
                return
            # Two widgets side by side (button holder + status).
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(20, 4, 20, 4)
            lay.setSpacing(8)
            lay.addWidget(label, 0)
            lay.addWidget(field, 1)
            self._card.add(wrap)
            self._register(label, wrap)
            self._register(field, wrap)
            return
        raise TypeError("addRow takes 1 or 2 arguments")

    def setRowVisible(self, widget, visible):
        entry = self._map.get(id(widget))
        try:
            widget.setVisible(bool(visible))
        except Exception:
            pass
        if entry is not None:
            _, row = entry
            if row is not None and row is not widget:
                try:
                    row.setVisible(bool(visible))
                except Exception:
                    pass

    def isRowVisible(self, widget):
        entry = self._map.get(id(widget))
        if entry is not None:
            _, row = entry
            if row is not None and row is not widget:
                try:
                    if row.isHidden():
                        return False
                except Exception:
                    pass
        try:
            return not widget.isHidden()
        except Exception:
            return True


def _setting(card, form, label, help_text, control):
    row = SettingRow(label, help_text, control)
    card.add(row)
    form._register(control, row)
    return row


def _note(card, form, widget):
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(20, 0, 20, 8)
    lay.addWidget(widget, 1)
    card.add(wrap)
    form._register(widget, wrap)
    return wrap


def build(window):
    from settings_ui import (
        AGY_CLEANUP_MODELS, CLEANUP_CLAUDE_MODELS, CLEANUP_MODELS, CODEX_MODELS,
        REASONING_LEVELS, TRANSCRIBE_MODELS,
    )

    body, outer = page(
        t("API and models"),
        t("Choose where speech-to-text and transcript cleanup run. Keys are "
          "stored only on this computer."),
    )

    # The registry first: every provider and every key in one place.
    outer.addWidget(window._providers_group())

    # ---- speech to text --------------------------------------------------
    stt = SectionCard(t("Speech to text"))
    outer.addWidget(stt)
    stt_form = window.stt_form = _CardForm(stt)

    window.transcribe_provider = _expanding(QComboBox(), 280)
    for label, value in window._transcribe_choices():
        window.transcribe_provider.addItem(label, value)
    _setting(stt, stt_form, t("Provider"),
             t("Local runs here; hosted needs its key."),
             window.transcribe_provider)

    window.transcribe_model = QComboBox()
    window.transcribe_model.setEditable(True)
    window.refresh_transcribe_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_transcribe_models.clicked.connect(window._load_transcribe_models)
    window.transcribe_model_row = window._row(window.transcribe_model,
                                              window.refresh_transcribe_models)
    _setting(stt, stt_form, t("Model"),
             t("Voice model for the selected provider."),
             window.transcribe_model_row)

    window.transcribe_status = QLabel("")
    window.transcribe_status.setWordWrap(True)
    _note(stt, stt_form, window.transcribe_status)

    window.local_whisper = LocalModelBox(
        ggml.WHISPER, t("On this machine"),
        ggml.whisper_models, ggml.whisper_model_path)
    stt.add(window.local_whisper)
    stt_form._register(window.local_whisper, None)

    window.local_gpu = QCheckBox(t("Use the graphics card"))
    window.local_gpu.setToolTip(t("Needs a CUDA, ROCm or Vulkan build."))
    window.local_preload = QCheckBox(t("Load the model when Dikte starts"))
    window.local_preload.setToolTip(t("Pays the load once, keeps it in memory."))
    window.local_threads = QSpinBox()
    window.local_threads.setRange(0, 64)
    window.local_threads.setSpecialValueText(t("Automatic"))
    window.local_options = QWidget()
    options_lay = QVBoxLayout(window.local_options)
    options_lay.setContentsMargins(20, 4, 20, 8)
    options_lay.setSpacing(8)
    options_lay.addWidget(window.local_gpu)
    options_lay.addWidget(window.local_preload)
    threads_row = QWidget()
    threads_lay = QHBoxLayout(threads_row)
    threads_lay.setContentsMargins(0, 0, 0, 0)
    threads_lay.addWidget(QLabel(t("Threads")))
    threads_lay.addStretch(1)
    threads_lay.addWidget(window.local_threads)
    options_lay.addWidget(threads_row)
    options_lay.addWidget(InfoNote(t(
        "Without a GPU build this runs on the processor whatever is ticked."),
        variant="info"))
    stt.add(window.local_options)
    stt_form._register(window.local_options, None)

    window.transcribe_provider.currentIndexChanged.connect(window._provider_changed)

    # ---- transcript cleanup ----------------------------------------------
    orr = SectionCard(t("Transcript cleanup"))
    outer.addWidget(orr)
    orr_form = window.cleanup_form = _CardForm(orr)

    window.cleanup_enabled = QCheckBox()
    _setting(orr, orr_form, t("Clean the transcript with a model"),
             t("Off pastes the raw transcript."),
             window.cleanup_enabled)

    window.cleanup_provider = _expanding(QComboBox(), 280)
    for label, value in window._cleanup_choices():
        window.cleanup_provider.addItem(label, value)
    window.cleanup_provider.setToolTip(t("Where the cleanup model runs."))
    window.cleanup_provider.currentIndexChanged.connect(window._cleanup_provider_changed)
    _setting(orr, orr_form, t("Runs on"),
             t("Which model cleans up."),
             window.cleanup_provider)
    _note(orr, orr_form, InfoNote(t(
        "Local is free on this machine; Claude Code, Codex and Antigravity "
        "reuse the subscription you already have."), variant="info"))

    window.cleanup_model = QComboBox()
    window.cleanup_model.setEditable(True)
    window.cleanup_model.addItems(CLEANUP_MODELS)
    window.refresh_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_models.clicked.connect(window._load_models)
    window.cleanup_model_row = window._row(window.cleanup_model, window.refresh_models)
    _setting(orr, orr_form, t("Model"),
             t("Model id for this provider."),
             window.cleanup_model_row)

    window.cleanup_claude_model = QComboBox()
    window.cleanup_claude_model.setEditable(True)
    window.cleanup_claude_model.addItems(CLEANUP_CLAUDE_MODELS)
    window.refresh_claude_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_claude_models.clicked.connect(window._load_claude_models)
    window.cleanup_claude_model_row = window._row(window.cleanup_claude_model,
                                                  window.refresh_claude_models)
    _setting(orr, orr_form, t("Model"),
             t("Model id for this provider."),
             window.cleanup_claude_model_row)

    window.cleanup_codex_model = QComboBox()
    window.cleanup_codex_model.setEditable(True)
    window.cleanup_codex_model.addItems([t("Codex's own default")] + CODEX_MODELS)
    window.refresh_codex_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_codex_models.clicked.connect(window._load_codex_models)
    window.cleanup_codex_model_row = window._row(window.cleanup_codex_model,
                                                 window.refresh_codex_models)
    _setting(orr, orr_form, t("Model"),
             t("Model id for this provider."),
             window.cleanup_codex_model_row)

    window.cleanup_agy_model = QComboBox()
    window.cleanup_agy_model.setEditable(True)
    window.cleanup_agy_model.addItems(AGY_CLEANUP_MODELS)
    window.refresh_agy_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_agy_models.clicked.connect(window._load_agy_models)
    window.cleanup_agy_model_row = window._row(window.cleanup_agy_model,
                                               window.refresh_agy_models)
    _setting(orr, orr_form, t("Model"),
             t("Model id for this provider."),
             window.cleanup_agy_model_row)

    window.cleanup_reasoning = _expanding(QComboBox(), 240)
    for label, value in REASONING_LEVELS:
        window.cleanup_reasoning.addItem(t(label), value)
    window.cleanup_reasoning.setToolTip(t("How long a thinking model may reason."))
    _setting(orr, orr_form, t("Thinking"),
             t("More thinking mostly costs time here."),
             window.cleanup_reasoning)

    window.cleanup_test = btn(t("Test"), "secondary", "sm")
    window.cleanup_test.setToolTip(t("Sends one test sentence to the model."))
    window.cleanup_test.clicked.connect(window._test_cleanup_model)
    window.cleanup_test_status = QLabel("")
    window.cleanup_test_status.setWordWrap(True)
    orr_form.addRow(window._row(window.cleanup_test), window.cleanup_test_status)

    window.models_label = QLabel("")
    window.models_label.setWordWrap(True)
    _note(orr, orr_form, window.models_label)

    window.local_llm = LocalModelBox(
        ggml.LLAMA, t("On this machine"),
        ggml.llm_quants, ggml.llm_model_path, repos=ggml.llm_repos)
    orr.add(window.local_llm)
    orr_form._register(window.local_llm, None)

    window.local_llm_gpu = QCheckBox(t("Use the graphics card"))
    window.local_llm_preload = QCheckBox(t("Load the model when Dikte starts"))
    window.local_llm_preload.setToolTip(t("Slower to load; off loads on first cleanup."))
    window.local_llm_reasoning = QComboBox()
    for label, value in REASONING_LEVELS:
        window.local_llm_reasoning.addItem(t(label), value)
    window.local_llm_reasoning.setToolTip(t("Off is what cleanup wants."))
    window.local_llm_options = QWidget()
    llm_lay = QVBoxLayout(window.local_llm_options)
    llm_lay.setContentsMargins(20, 4, 20, 8)
    llm_lay.setSpacing(8)
    llm_lay.addWidget(window.local_llm_gpu)
    llm_lay.addWidget(window.local_llm_preload)
    llm_think = QWidget()
    llm_think_lay = QHBoxLayout(llm_think)
    llm_think_lay.setContentsMargins(0, 0, 0, 0)
    llm_think_lay.addWidget(QLabel(t("Thinking")))
    llm_think_lay.addStretch(1)
    llm_think_lay.addWidget(window.local_llm_reasoning)
    llm_lay.addWidget(llm_think)
    orr.add(window.local_llm_options)
    orr_form._register(window.local_llm_options, None)

    outer.addStretch(1)
    return scrolled(body)

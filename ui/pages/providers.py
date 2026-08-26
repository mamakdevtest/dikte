"""API and models page: the provider registry, speech-to-text and cleanup."""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

import ggml
from i18n import t

from ..local_models import LocalModelBox
from ..widgets import btn
from . import page, scrolled


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
    stt = QGroupBox(t("Speech to text"))
    stt_form = QFormLayout(stt)
    stt_form.setContentsMargins(20, 16, 20, 12)

    window.transcribe_provider = QComboBox()
    for label, value in window._transcribe_choices():
        window.transcribe_provider.addItem(label, value)
    window.transcribe_provider.setFixedWidth(280)
    stt_form.addRow(t("Provider"), window.transcribe_provider)

    window.stt_form = stt_form
    window.transcribe_model = QComboBox()
    window.transcribe_model.setEditable(True)
    window.refresh_transcribe_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_transcribe_models.clicked.connect(window._load_transcribe_models)
    window.transcribe_model_row = window._row(window.transcribe_model,
                                              window.refresh_transcribe_models)
    stt_form.addRow(t("Model"), window.transcribe_model_row)

    window.transcribe_status = QLabel("")
    window.transcribe_status.setWordWrap(True)
    stt_form.addRow(window.transcribe_status)

    window.local_whisper = LocalModelBox(
        ggml.WHISPER, t("On this machine"),
        ggml.whisper_models, ggml.whisper_model_path)
    stt_form.addRow(window.local_whisper)

    window.local_gpu = QCheckBox(t("Use the graphics card"))
    window.local_gpu.setToolTip(
        t("whisper.cpp reaches the card through CUDA, ROCm or Vulkan when the "
          "build it is running was made with one. A build without any of them "
          "runs on the processor whatever this says."))
    window.local_preload = QCheckBox(t("Load the model when Dikte starts"))
    window.local_preload.setToolTip(
        t("A large model takes a second or two to load. Loading it up front "
          "spends that once instead of on the first dictation, at the cost of "
          "the memory it sits in."))
    window.local_threads = QSpinBox()
    window.local_threads.setRange(0, 64)
    window.local_threads.setSpecialValueText(t("Automatic"))
    window.local_options = QWidget()
    options_form = QFormLayout(window.local_options)
    options_form.setContentsMargins(0, 0, 0, 0)
    options_form.addRow("", window.local_gpu)
    options_form.addRow("", window.local_preload)
    options_form.addRow(t("Threads"), window.local_threads)
    stt_form.addRow(window.local_options)

    window.transcribe_provider.currentIndexChanged.connect(window._provider_changed)
    outer.addWidget(stt)

    # ---- transcript cleanup ----------------------------------------------
    orr = QGroupBox(t("Transcript cleanup"))
    orr_form = window.cleanup_form = QFormLayout(orr)
    orr_form.setContentsMargins(20, 16, 20, 12)

    window.cleanup_enabled = QCheckBox(t("Clean the transcript with a model"))
    orr_form.addRow("", window.cleanup_enabled)

    window.cleanup_provider = QComboBox()
    for label, value in window._cleanup_choices():
        window.cleanup_provider.addItem(label, value)
    window.cleanup_provider.setFixedWidth(280)
    window.cleanup_provider.setToolTip(t(
        "llama.cpp runs here, on a model downloaded below; nothing to pay, "
        "nothing to install beyond it. Claude Code, Codex and Antigravity "
        "clean up on the subscription you already have, without a second "
        "key, and take a few seconds longer because each one opens a "
        "session to do it."))
    window.cleanup_provider.currentIndexChanged.connect(window._cleanup_provider_changed)
    orr_form.addRow(t("Runs on"), window.cleanup_provider)

    window.cleanup_model = QComboBox()
    window.cleanup_model.setEditable(True)
    window.cleanup_model.addItems(CLEANUP_MODELS)
    window.refresh_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_models.clicked.connect(window._load_models)
    window.cleanup_model_row = window._row(window.cleanup_model, window.refresh_models)
    orr_form.addRow(t("Model"), window.cleanup_model_row)

    window.cleanup_claude_model = QComboBox()
    window.cleanup_claude_model.setEditable(True)
    window.cleanup_claude_model.addItems(CLEANUP_CLAUDE_MODELS)
    window.refresh_claude_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_claude_models.clicked.connect(window._load_claude_models)
    window.cleanup_claude_model_row = window._row(window.cleanup_claude_model,
                                                  window.refresh_claude_models)
    orr_form.addRow(t("Model"), window.cleanup_claude_model_row)

    window.cleanup_codex_model = QComboBox()
    window.cleanup_codex_model.setEditable(True)
    window.cleanup_codex_model.addItems([t("Codex's own default")] + CODEX_MODELS)
    window.refresh_codex_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_codex_models.clicked.connect(window._load_codex_models)
    window.cleanup_codex_model_row = window._row(window.cleanup_codex_model,
                                                 window.refresh_codex_models)
    orr_form.addRow(t("Model"), window.cleanup_codex_model_row)

    window.cleanup_agy_model = QComboBox()
    window.cleanup_agy_model.setEditable(True)
    window.cleanup_agy_model.addItems(AGY_CLEANUP_MODELS)
    window.refresh_agy_models = btn(t("Fetch model list"), "secondary", "sm")
    window.refresh_agy_models.clicked.connect(window._load_agy_models)
    window.cleanup_agy_model_row = window._row(window.cleanup_agy_model,
                                               window.refresh_agy_models)
    orr_form.addRow(t("Model"), window.cleanup_agy_model_row)

    window.cleanup_reasoning = QComboBox()
    for label, value in REASONING_LEVELS:
        window.cleanup_reasoning.addItem(t(label), value)
    window.cleanup_reasoning.setFixedWidth(240)
    window.cleanup_reasoning.setToolTip(
        t("How long a thinking model may reason before it answers. Cleanup is "
          "a light job, so more thinking mostly costs time and tokens. Models "
          "that cannot think ignore this."))
    orr_form.addRow(t("Thinking"), window.cleanup_reasoning)

    window.cleanup_test = btn(t("Test"), "secondary", "sm")
    window.cleanup_test.setToolTip(t(
        "Sends one test sentence to the cleanup model and shows its reply. "
        "Proves the key, the address and the model id together."))
    window.cleanup_test.clicked.connect(window._test_cleanup_model)
    window.cleanup_test_status = QLabel("")
    window.cleanup_test_status.setWordWrap(True)
    orr_form.addRow(window._row(window.cleanup_test), window.cleanup_test_status)

    window.models_label = QLabel("")
    window.models_label.setWordWrap(True)
    orr_form.addRow(window.models_label)

    window.local_llm = LocalModelBox(
        ggml.LLAMA, t("On this machine"),
        ggml.llm_quants, ggml.llm_model_path, repos=ggml.llm_repos)
    orr_form.addRow(window.local_llm)

    window.local_llm_gpu = QCheckBox(t("Use the graphics card"))
    window.local_llm_preload = QCheckBox(t("Load the model when Dikte starts"))
    window.local_llm_preload.setToolTip(
        t("An LLM is slower to load than a whisper model and sits in more "
          "memory. Off means it is loaded on the first cleanup instead."))
    window.local_llm_reasoning = QComboBox()
    for label, value in REASONING_LEVELS:
        window.local_llm_reasoning.addItem(t(label), value)
    window.local_llm_reasoning.setToolTip(
        t("A model trained to think will think unless it is told not to, and "
          "spending 300 tokens of reasoning on a comma is 300 tokens of "
          "waiting. Off is what cleanup wants."))
    window.local_llm_options = QWidget()
    llm_form = QFormLayout(window.local_llm_options)
    llm_form.setContentsMargins(0, 0, 0, 0)
    llm_form.addRow("", window.local_llm_gpu)
    llm_form.addRow("", window.local_llm_preload)
    llm_form.addRow(t("Thinking"), window.local_llm_reasoning)
    orr_form.addRow(window.local_llm_options)

    outer.addWidget(orr)
    outer.addStretch(1)
    return scrolled(body)

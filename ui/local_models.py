"""The local model download box (whisper.cpp and llama.cpp), restyled.

Moved from ``settings_ui.py`` largely verbatim: the public surface the tests
and the settings window rely on is unchanged — ``selected()``, ``repository()``,
``load()``, ``status``, ``_pending``, ``_fit_popup`` and ``_report``. The only
change is the buttons, which now carry the design system's variant styling.
"""

import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QWidget,
)

import ggml
from i18n import t

from .widgets import btn as _btn


class LocalModelBox(QGroupBox):
    """The program, the model, and the two downloads that put them there.

    One class for whisper.cpp and llama.cpp, because the job is the same one
    twice: say whether the program is here, offer the models somebody publishes,
    fetch the chosen one, and stay usable while a gigabyte arrives.
    """

    _listed = pyqtSignal(list, str)
    _quants = pyqtSignal(list, str)
    _progress = pyqtSignal("qint64", "qint64")
    _finished = pyqtSignal(str, str)
    _installed = pyqtSignal(str, str)
    _program_ready = pyqtSignal(str, bool)

    changed = pyqtSignal()

    def __init__(self, program, title, models, model_path, repos=None, parent=None):
        super().__init__(title, parent)
        self.program = program
        self._models = models          # () -> [hub.Item], or (repo) -> [hub.Item]
        self._model_path = model_path  # (name) -> Path
        self._repos = repos            # None, or () -> [repo id]
        self._downloading = False
        self._pending = False
        self._stop = False
        self._wanted = ""              # the model to select once a list arrives

        form = QFormLayout(self)
        form.setContentsMargins(20, 16, 20, 12)

        self.program_label = QLabel("")
        self.program_label.setWordWrap(True)
        self.install_button = _btn(t("Download"), "secondary", "sm")
        self.install_button.clicked.connect(self._install_program)
        form.addRow(t("Program"), self._side_by_side(self.program_label,
                                                     self.install_button))

        if self._repos is not None:
            self.repo = QComboBox()
            self.repo.setEditable(True)
            self.repo.setToolTip(t("A Hugging Face repository of GGUF files. The "
                                   "list is fetched; any other one can be typed in."))
            self.repo.currentTextChanged.connect(self._repo_changed)
            form.addRow(t("Publisher"), self.repo)

        self.model = QComboBox()
        self.download_button = _btn(t("Download"), "secondary", "sm")
        self.download_button.clicked.connect(self._download)
        self.delete_button = _btn(t("Delete"), "ghost", "sm")
        self.delete_button.clicked.connect(self._delete)
        form.addRow(t("Model"), self._side_by_side(self.model,
                                                   self.download_button,
                                                   self.delete_button))
        self.model.currentIndexChanged.connect(self._model_changed)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.status)

        self._listed.connect(self._on_listed)
        self._quants.connect(self._on_listed)
        self._progress.connect(self._on_progress)
        self._finished.connect(self._on_finished)
        self._installed.connect(self._on_installed)
        self._program_ready.connect(self._on_program_ready)

    @staticmethod
    def _fit_popup(combo):
        """Let the list that drops down be as wide as its longest row."""
        view = combo.view()
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        metrics = combo.fontMetrics()
        widest = max((metrics.horizontalAdvance(combo.itemText(row))
                      for row in range(combo.count())), default=0)
        view.setMinimumWidth(widest + view.verticalScrollBar().sizeHint().width() + 24)

    @staticmethod
    def _side_by_side(*widgets):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for index, widget in enumerate(widgets):
            layout.addWidget(widget, 1 if index == 0 else 0)
        holder = QWidget()
        holder.setLayout(layout)
        return holder

    # ---- what is here ----------------------------------------------------

    def selected(self):
        return self.model.currentData() or ""

    def repository(self):
        return self.repo.currentText().strip() if self._repos is not None else ""

    def load(self, model, repo=""):
        """Show what is stored. What else is on offer is asked for on the way up."""
        self._wanted = model
        self._pending = True
        # Immediate placeholder so Settings first open <300ms; heavy ggml
        # probes (shutil.which + glob + file checks) run off the GUI thread
        # and report back via _program_ready. The deferred path via showEvent
        # will fetch model lists; program status is now async too.
        self.program_label.setText(t("Checking…"))
        self.install_button.setVisible(False)

        def _probe():
            try:
                path = ggml.program_path(self.program)
                if not path:
                    self._program_ready.emit(t("Not installed."), True)
                    return
                is_system = ggml.system_program(self.program)
                is_installed = ggml.installed_program(self.program)
                visible = not is_installed and not is_system
                if is_system:
                    text = t("Installed on the system: {path}", path=path)
                else:
                    version = ggml.installed_version(self.program) or "?"
                    text = t("Downloaded, version {version}.", version=version)
                self._program_ready.emit(text, visible)
            except Exception:
                self._program_ready.emit(t("Not installed."), True)

        threading.Thread(target=_probe, daemon=True).start()
        if self._repos is not None:
            self.repo.blockSignals(True)
            self.repo.clear()
            self.repo.addItems(list(ggml.SUGGESTED_LLM))
            self.repo.setCurrentText(repo or ggml.SUGGESTED_LLM[0])
            self.repo.blockSignals(False)
            self._fit_popup(self.repo)
        self._fill_models([])

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending:
            self._pending = False
            if self._repos is not None:
                self._fill_repos(self.repository())
            self._fetch_models(self.repository())

    def _show_program(self):
        # Kept synchronous for backwards compat (_on_installed, direct calls).
        # Settings deferral uses async path in load() -> _program_ready via
        # background thread; showEvent handles model list fetching. This sync
        # version remains lightweight and is used when already on GUI thread.
        path = ggml.program_path(self.program)
        if not path:
            self.program_label.setText(t("Not installed."))
            self.install_button.setVisible(True)
            return
        self.install_button.setVisible(not ggml.installed_program(self.program)
                                       and not ggml.system_program(self.program))
        if ggml.system_program(self.program):
            self.program_label.setText(t("Installed on the system: {path}", path=path))
        else:
            self.program_label.setText(
                t("Downloaded, version {version}.",
                  version=ggml.installed_version(self.program) or "?"))

    def _on_program_ready(self, text, visible):
        self.program_label.setText(text)
        self.install_button.setVisible(visible)
        self.changed.emit()

    # ---- the lists -------------------------------------------------------

    def _fill_repos(self, current):
        def work():
            self._listed.emit([("repos", ggml.llm_repos())], "")

        threading.Thread(target=work, daemon=True).start()

    def _repo_changed(self):
        if not self._downloading:
            self._fetch_models(self.repository())

    def _fetch_models(self, repo=""):
        self.status.setText(t("Fetching the model list…"))

        def work():
            try:
                found = self._models(repo) if self._repos is not None else self._models()
                self._quants.emit([("models", found)], "")
            except ggml.LocalError as exc:
                self._quants.emit([], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_listed(self, payload, error):
        if error:
            self.status.setText(error)
            self._refresh_buttons()
            return
        kind, found = payload[0]
        if kind == "repos":
            current = self.repo.currentText()
            self.repo.blockSignals(True)
            self.repo.clear()
            self.repo.addItems(found)
            self.repo.setCurrentText(current)
            self.repo.blockSignals(False)
            self._fit_popup(self.repo)
            return
        self._fill_models(found)

    def _fill_models(self, items):
        """One row per model, saying what it weighs and whether it is here."""
        wanted = self._wanted or self.selected()
        here = [name for name in (self._model_path(i.name).name for i in items)]
        self.model.blockSignals(True)
        self.model.clear()
        for item, name in zip(items, here):
            mark = (t("downloaded") if ggml.have_model(self._model_path(item.name))
                    else ggml.human_size(item.size))
            self.model.addItem(f"{name}  ({mark})", name)
            self.model.setItemData(self.model.count() - 1, item, Qt.ItemDataRole.UserRole + 1)
        for name in self._on_disk():
            if self.model.findData(name) < 0:
                self.model.addItem(f"{name}  ({t('downloaded')})", name)
        if wanted and self.model.findData(wanted) < 0:
            self.model.addItem(f"{wanted}  ({t('not downloaded')})", wanted)
        index = self.model.findData(wanted)
        self.model.setCurrentIndex(max(index, 0))
        self.model.blockSignals(False)
        self._fit_popup(self.model)
        self._wanted = ""
        self._model_changed()

    def _on_disk(self):
        return (ggml.installed_whisper_models() if self.program is ggml.WHISPER
                else ggml.installed_llm_models())

    # ---- fetching --------------------------------------------------------

    def _install_program(self):
        self.install_button.setEnabled(False)
        self.program_label.setText(t("Downloading…"))

        def work():
            try:
                ggml.install_program(self.program, on_progress=self._report)
                self._installed.emit("", "")
            except ggml.LocalError as exc:
                self._installed.emit("", str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_installed(self, _, error):
        self.install_button.setEnabled(True)
        self._show_program()
        if error:
            self.program_label.setText(error)
        self.changed.emit()

    def _current_item(self):
        return self.model.currentData(Qt.ItemDataRole.UserRole + 1)

    def _download(self):
        if self._downloading:
            self._stop = True
            return
        item = self._current_item()
        if item is None:
            return
        self._downloading, self._stop = True, False
        self._refresh_buttons()

        def work():
            try:
                landed = ggml.download(item, self._model_path(item.name),
                                       on_progress=self._report,
                                       should_stop=lambda: self._stop)
                self._finished.emit(item.name if landed else "", "")
            except ggml.LocalError as exc:
                self._finished.emit("", str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _report(self, done, total):
        self._progress.emit(done, total)

    def _on_progress(self, done, total):
        share = f" ({done * 100 // total}%)" if total else ""
        text = t("Downloading: {done} of {total}{share}",
                 done=ggml.human_size(done), total=ggml.human_size(total or done),
                 share=share)
        if self._downloading:
            self.status.setText(text)
        else:
            self.program_label.setText(text)

    def _on_finished(self, name, error):
        self._downloading = False
        if error:
            self.status.setText(error)
        elif not name:
            self.status.setText(t("Download stopped."))
        self._fill_models_from_current()
        self.changed.emit()

    def _fill_models_from_current(self):
        """Redraw the rows without asking anybody anything again."""
        items = [self.model.itemData(i, Qt.ItemDataRole.UserRole + 1)
                 for i in range(self.model.count())]
        self._wanted = self.selected()
        self._fill_models([i for i in items if i is not None])

    def _delete(self):
        name = self.selected()
        if not name or not ggml.have_model(self._model_path(name)):
            return
        if QMessageBox.question(self, t("Delete model"),
                                t("Delete {name} from this machine?", name=name)) \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            ggml.delete_model(self._model_path(name))
        except ggml.LocalError as exc:
            self.status.setText(str(exc))
        self._fill_models_from_current()
        self.changed.emit()

    def _model_changed(self):
        self._refresh_buttons()
        self.changed.emit()

    def _refresh_buttons(self):
        name = self.selected()
        here = bool(name) and ggml.have_model(self._model_path(name))
        self.delete_button.setEnabled(here and not self._downloading)
        self.download_button.setText(t("Stop") if self._downloading else t("Download"))
        self.download_button.setEnabled(self._downloading or (bool(name) and not here))
        if self._downloading:
            return
        if not name:
            self.status.setText(t("Nothing downloaded yet."))
        elif here:
            self.status.setText(t("Ready: {name}.", name=name))
        else:
            self.status.setText(t("{name} has not been downloaded yet.", name=name))

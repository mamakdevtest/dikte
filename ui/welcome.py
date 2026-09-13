"""The first-run wizard: can it hear you, can it think, and did it work.

Not a tour. Each of the three steps either changes something or says plainly why it cannot.
The microphone is checked with the recorder the dictation path itself uses, the engine step
is the download box the settings page already has (a fresh install's highest-friction
moment, so it is reused rather than reimplemented), and the last step does not simulate a
dictation — it waits for the real one and reports what it saw.

A wizard that cannot say "this machine has no microphone" is worse than no wizard, because
it is the one screen a new user trusts.
"""

import sys
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QStackedWidget,
                            QVBoxLayout, QWidget)

import audio
import config as cfg
import ggml
import hotkey
from i18n import t
from ui.local_models import LocalModelBox
from ui.widgets import InfoNote, Meta, SectionCard, StatusChip, Subtitle, Title, btn

# How long the microphone check listens, how long the last step waits for a real dictation
# before it says what to look at instead, and how often it looks.
LISTEN_MS = 2500
WAIT_MS = 90_000
POLL_MS = 1500
# Below this peak we did not hear a person: silence, a muted input, the wrong device.
HEARD = 0.02

STEPS = ((0, "Can it hear you?"),
         (1, "Can it think without a key?"),
         (2, "Now the real thing"))


def _window_icon():
    """The window icon: the theme's, or the one we ship. Not worth a dependency."""
    icon = QIcon.fromTheme("dikte")
    if not icon.isNull():
        return icon
    import pathlib
    for name in ("dikte.png", "dikte.ico"):
        candidate = pathlib.Path(__file__).resolve().parent.parent / "icons" / name
        if candidate.exists():
            return QIcon(str(candidate))
    return icon


class WelcomeWizard(QDialog):
    """Microphone, engine, and one real dictation watched from the outside.

    The wizard never changes the engine on its own: the engine step has a button for that,
    because silently repointing the transcriber at whatever model happens to be on disk is
    how a first run becomes a mystery later.
    """

    _sources_loaded = pyqtSignal(list, str)

    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.conf = conf
        self.setWindowTitle(t("Set up Dikte"))
        self.setWindowIcon(_window_icon())
        self.resize(780, 600)
        self._recorder = None
        self._peak = 0.0
        self._elapsed = 0
        self._history_at_start = self._history_count()
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(POLL_MS)
        self._watch_timer.timeout.connect(self._look_for_it)
        self._sources_loaded.connect(self._on_sources)
        self._build()

    # --- the frame --------------------------------------------------------

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(12)
        self.step_label = Meta("")
        outer.addWidget(self.step_label)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._mic_step())
        self.stack.addWidget(self._engine_step())
        self.stack.addWidget(self._try_step())
        outer.addWidget(self.stack, 1)
        outer.addLayout(self._footer())
        self._goto(0)

    def _footer(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        self.back = btn(t("Back"), variant="ghost")
        self.back.clicked.connect(lambda: self._goto(self.stack.currentIndex() - 1))
        row.addWidget(self.back)
        row.addStretch(1)
        self.skip = btn(t("Not now"), variant="ghost")
        self.skip.clicked.connect(self._not_now)
        row.addWidget(self.skip)
        self.next = btn(t("Next"), variant="primary")
        self.next.clicked.connect(self._advance)
        row.addWidget(self.next)
        return row

    def _goto(self, index):
        index = max(0, min(index, self.stack.count() - 1))
        self.stack.setCurrentIndex(index)
        number, title = STEPS[index]
        self.step_label.setText(t("Step {number} of {total} — {title}").format(
            number=number + 1, total=len(STEPS), title=t(title)))
        self.back.setEnabled(index > 0)
        self.next.setText(t("Finish") if index == self.stack.count() - 1 else t("Next"))
        if index == 2:
            # Starting the watch on arrival, not on construction: the clock should measure
            # the user's patience with this page, not the time they spent on the other two.
            self._history_at_start = self._history_count()
            self._elapsed = 0
            self._watch_timer.start()
        else:
            self._watch_timer.stop()

    def _advance(self):
        if self.stack.currentIndex() < self.stack.count() - 1:
            self._goto(self.stack.currentIndex() + 1)
            return
        self._finish()

    def _finish(self):
        self._watch_timer.stop()
        self._say_done()
        self.accept()

    def _say_done(self):
        self.conf.data["setup_done"] = True
        try:
            self.conf.save()
        except Exception as exc:
            # The wizard is over either way; what the user loses is the next run's reminder,
            # and pretending the setting was written would be the worse outcome.
            print(f"dikte: setup finished but that could not be saved ({exc})", file=sys.stderr)

    def _not_now(self):
        self._watch_timer.stop()
        self.reject()

    def closeEvent(self, event):
        self._watch_timer.stop()
        super().closeEvent(event)

    # --- step one: the microphone -----------------------------------------

    def _mic_step(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(12)
        box.addWidget(Title(t("Can it hear you?")))
        box.addWidget(Subtitle(t("Pick the microphone you speak into, then say something out "
                                 "loud. Nothing is transcribed by this check.")))
        card = SectionCard(t("Microphone"),
                           t("Dikte records from one input at a time; this is the one it "
                             "will use."))
        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumWidth(280)
        card.add(self.mic_combo)
        self.mic_button = btn(t("Listen for a moment"), variant="secondary")
        self.mic_button.clicked.connect(self._listen)
        card.add(self.mic_button)
        box.addWidget(card)
        self.mic_note = InfoNote(t("Looking for microphones…"), "info")
        box.addWidget(self.mic_note)
        box.addStretch(1)
        self._load_sources()
        return page

    def _load_sources(self):
        """Enumerate off the GUI thread: listing devices runs a sound-server query."""
        def work():
            sources, default, problem = [], "", ""
            try:
                sources = list(audio.cached_list_sources() or [])
            except Exception as exc:
                # Logged here as well as carried into the note below: the note is what the
                # user sees, this is what a bug report can quote.
                print(f"dikte: could not list the microphones ({exc})", file=sys.stderr)
                problem = str(exc)
            try:
                default = audio.default_input() or ""
            except Exception as exc:
                # Not fatal on its own: a list with no marked default still lets the user
                # choose, so the failure is recorded in the note rather than ending the step.
                print(f"dikte: could not ask which input is the default ({exc})",
                      file=sys.stderr)
                problem = problem or str(exc)
            self._sources_loaded.emit(sources, f"{default}\x00{problem}")

        threading.Thread(target=work, daemon=True).start()

    def _on_sources(self, sources, packed):
        default, problem = (packed.split("\x00", 1) + [""])[:2]
        self.mic_combo.clear()
        for source in sources:
            name = source.get("description") or source.get("name") or source.get("target", "")
            self.mic_combo.addItem(name, source.get("target") or source.get("name") or "")
        if default:
            for i in range(self.mic_combo.count()):
                if self.mic_combo.itemData(i) == default:
                    self.mic_combo.setCurrentIndex(i)
                    break
        if not sources:
            self.mic_button.setEnabled(False)
            self.mic_note.setText(t("No microphone was found on this machine. Dikte can still "
                                    "be set up — dictation will need one before it can type "
                                    "anything you say."))
            self.mic_note.setProperty("note", "warn")
        else:
            self.mic_note.setText(t("{count} input(s) found. Say something and press the "
                                    "button.").format(count=len(sources)))
            self.mic_note.setProperty("note", "info")
        if problem:
            print(f"dikte: microphone listing reported a problem ({problem})", file=sys.stderr)

    def _listen(self):
        if self._recorder is not None:
            return
        self._peak = 0.0
        self.mic_button.setEnabled(False)
        self.mic_note.setText(t("Listening… say a sentence out loud."))
        self.mic_note.setProperty("note", "info")
        recorder = audio.Recorder(self)
        recorder.level.connect(self._on_level)
        recorder.failed.connect(self._on_mic_failed)
        recorder.stopped.connect(self._on_mic_stopped)
        self._recorder = recorder
        recorder.start(self.mic_combo.currentData() or "", max_seconds=8)
        QTimer.singleShot(LISTEN_MS, self._stop_listening)

    def _stop_listening(self):
        if self._recorder is not None:
            self._recorder.stop()

    def _on_level(self, level):
        self._peak = max(self._peak, float(level))

    def _on_mic_failed(self, message):
        self._recorder = None
        self.mic_button.setEnabled(True)
        self.mic_note.setText(t("Nothing came through: {message}").format(message=message))
        self.mic_note.setProperty("note", "err")

    def _on_mic_stopped(self, path, _duration, _rms):
        self._recorder = None
        self.mic_button.setEnabled(True)
        if self._peak >= HEARD:
            self.mic_note.setText(t("Heard you — peak level {percent}%. The microphone "
                                    "works.").format(percent=round(self._peak * 100)))
            self.mic_note.setProperty("note", "ok")
        else:
            self.mic_note.setText(t("Nothing came through. Check that the microphone is not "
                                    "muted, that the right input is selected above, and that "
                                    "the system's input volume is up."))
            self.mic_note.setProperty("note", "warn")
        self._forget(path)

    def _forget(self, path):
        """Delete the check's own recording: it is not something the user said on purpose."""
        try:
            import os
            if path and os.path.exists(path):
                os.unlink(path)
        except OSError as exc:
            print(f"dikte: the microphone check left its recording behind ({exc})",
                  file=sys.stderr)

    # --- step two: the engine ---------------------------------------------

    def _engine_step(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(12)
        box.addWidget(Title(t("Can it think without a key?")))
        box.addWidget(Subtitle(t("Dikte transcribes either on this machine or through a "
                                 "service you have a key for. On this machine needs no "
                                 "account, and the model is the biggest download.")))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(t("Transcribing today:")))
        self.engine_chip = StatusChip("", "gray", dot="idle")
        row.addWidget(self.engine_chip)
        row.addStretch(1)
        box.addLayout(row)
        card = SectionCard(t("The model on this machine"),
                           t("Pick one and let it download; the sizes are real, and the "
                             "smallest is enough to start with."))
        self.model_box = LocalModelBox(ggml.WHISPER, t("On this machine"),
                                       ggml.whisper_models, ggml.whisper_model_path)
        card.add(self.model_box)
        self.use_button = btn(t("Transcribe on this machine"), variant="primary")
        self.use_button.clicked.connect(self._use_local_engine)
        card.add(self.use_button)
        box.addWidget(card)
        self.engine_note = InfoNote("", "info")
        box.addWidget(self.engine_note)
        box.addStretch(1)
        self._refresh_engine()
        return page

    def _refresh_engine(self):
        """Say what is set up now, in the product's own words rather than a boolean."""
        try:
            ready = bool(self.conf.transcribe_ready())
        except Exception as exc:
            # The answer decides a label, and an unreadable setting is a truthful "not set
            # up" here: the button below is how the user tells us otherwise.
            print(f"dikte: could not work out whether transcription is ready ({exc})",
                  file=sys.stderr)
            ready = False
        provider = self.conf.get("transcribe_provider", "local") or "local"
        self.engine_chip.setText(t("ready") if ready else t("nothing set up yet"))
        self.engine_chip.setVariant("sage" if ready else "tan")
        self.engine_note.setText(
            t("Right now Dikte transcribes through “{provider}”. Choosing the model below "
              "switches it to this machine and keeps working without a key.").format(
                  provider=provider))

    def _use_local_engine(self):
        model = ""
        try:
            model = self.model_box.selected() or ""
        except Exception as exc:
            print(f"dikte: the model list could not say what is selected ({exc})",
                  file=sys.stderr)
        if not model:
            self.engine_note.setText(t("Pick a model in the list first — the download button "
                                       "sits next to it."))
            self.engine_note.setProperty("note", "warn")
            return
        self.conf.data["local_model"] = model
        self.conf.data["transcribe_provider"] = "local"
        try:
            self.conf.save()
        except Exception as exc:
            self.engine_note.setText(t("That could not be saved: {error}").format(error=exc))
            self.engine_note.setProperty("note", "err")
            return
        # Refreshed first: it rewrites the note above, and a confirmation that is overwritten
        # in the same breath is how a save looks like it did not happen.
        self._refresh_engine()
        self.engine_note.setText(t("Saved: Dikte now transcribes on this machine with "
                                   "{model}.").format(model=model))
        self.engine_note.setProperty("note", "ok")

    # --- step three: the real thing ---------------------------------------

    def _try_step(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(12)
        box.addWidget(Title(t("Now the real thing")))
        combo = self.conf.get("shortcut", "") or hotkey.SHORTCUTS["toggle"][-1]
        box.addWidget(Subtitle(t("Put the cursor in any window, press {combo}, say a "
                                 "sentence, and press it again. This page is watching for "
                                 "the result.").format(combo=combo)))
        self.try_note = InfoNote(t("Waiting for your first dictation…"), "info")
        box.addWidget(self.try_note)
        self.try_detail = QLabel("")
        self.try_detail.setWordWrap(True)
        box.addWidget(self.try_detail)
        box.addStretch(1)
        self._describe_shortcut(combo)
        return page

    def _describe_shortcut(self, combo):
        """Whether the shortcut is actually registered — the first suspect when nothing comes."""
        try:
            status = hotkey.shortcut_status(hotkey.DESKTOP_ID)
        except Exception as exc:
            # Saying nothing about the shortcut is better than saying something wrong about
            # it; the note below then only lists what to check by hand.
            print(f"dikte: could not ask whether the shortcut is registered ({exc})",
                  file=sys.stderr)
            status = None
        if status:
            self.try_detail.setText(t("Shortcut {combo} is registered with the desktop.").format(
                combo=combo))
        elif status is not None:
            self.try_detail.setText(t("Shortcut {combo} is not registered yet — Settings → "
                                      "Shortcuts can install it, and `dikte doctor` says what "
                                      "is missing.").format(combo=combo))

    def _history_count(self):
        try:
            return len(cfg.read_history(limit=500) or [])
        except Exception as exc:
            print(f"dikte: could not read the history to watch for a dictation ({exc})",
                  file=sys.stderr)
            return None

    def _look_for_it(self):
        self._elapsed += POLL_MS
        count = self._history_count()
        if (count is not None and self._history_at_start is not None
                and count > self._history_at_start):
            self._watch_timer.stop()
            self.try_note.setText(t("There it is — that is a dictation, transcribed and typed "
                                    "where your cursor was."))
            self.try_note.setProperty("note", "ok")
            self.try_detail.setText(t("You can close this and use the shortcut anywhere. "
                                      "Dikte keeps the last recordings under History."))
            return
        if self._elapsed >= WAIT_MS:
            self._watch_timer.stop()
            self.try_note.setText(t("Nothing has arrived yet. Pressing {combo} should show "
                                    "the overlay over the text field; if it does not, one of "
                                    "these is the reason.").format(
                                        combo=self.conf.get("shortcut", "")
                                        or hotkey.SHORTCUTS["toggle"][-1]))
            self.try_note.setProperty("note", "warn")
            self.try_detail.setText(t("1. The shortcut is not registered (Settings → "
                                      "Shortcuts). 2. No engine is set up (step 2 above). "
                                      "3. The microphone is muted — `dikte doctor` names "
                                      "which of the three it is."))

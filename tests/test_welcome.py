"""The first-run wizard: three steps, each of which has to tell the truth.

The wizard is the one screen a new user trusts, so the tests are about what it *says*: a
machine with no microphone must be told so rather than shown a button that does nothing, a
silent input must not be called working, and an engine must not be claimed to be set up when
it is not. The recorder and the device listing are stubbed — a test that needs a microphone
is a test that fails on the machine that has none.
"""

import pathlib
import time
import unittest
from unittest import mock

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import audio
import config as cfg
from i18n import t
from tests.support import DikteTest
from ui.welcome import LISTEN_MS, WAIT_MS, WelcomeWizard


class FakeRecorder(QObject):
    """The recorder's contract, without a sound server behind it."""

    level = pyqtSignal(float)
    stopped = pyqtSignal(str, float, object)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.started = None
        self.stopped_called = False

    def start(self, target="", max_seconds=300):
        self.started = (target, max_seconds)

    def stop(self):
        self.stopped_called = True


class WizardTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.conf = self.config()
        self.mic = {"name": "mic0", "description": "Built-in microphone", "target": "mic0"}
        # The listing runs on a thread and asks the sound server; CI has no sound server.
        self.patch_attr(audio, "cached_list_sources", lambda: [dict(self.mic)])
        self.patch_attr(audio, "default_input", lambda: "mic0")
        self.recorders = []

        def make(parent=None):
            recorder = FakeRecorder(parent)
            self.recorders.append(recorder)
            return recorder

        self.patch_attr(audio, "Recorder", make)

    def wizard(self, **values):
        for key, value in values.items():
            self.conf.data[key] = value
        return WelcomeWizard(self.conf)

    def settle(self, condition, message):
        """Spin the event loop while the device listing's thread finishes."""
        for _ in range(300):
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail(message)

    def note(self, widget):
        return widget.text()


class TheStepsSayWhereYouAre(WizardTest):
    def test_it_opens_on_the_first_step_and_names_it(self):
        wizard = self.wizard()
        self.assertEqual(0, wizard.stack.currentIndex())
        self.assertIn(t("Step {number} of {total} — {title}").format(
            number=1, total=3, title=t("Can it hear you?")), wizard.step_label.text())
        self.assertFalse(wizard.back.isEnabled(), "there is nowhere to go back to")
        self.assertEqual(t("Next"), wizard.next.text())

    def test_the_last_step_offers_finish_and_not_next(self):
        wizard = self.wizard()
        wizard._goto(2)
        self.assertEqual(t("Finish"), wizard.next.text())
        self.assertTrue(wizard.back.isEnabled())

    def test_finishing_records_that_setup_is_done(self):
        wizard = self.wizard()
        wizard._goto(2)
        wizard.next.click()
        self.assertTrue(self.conf.get("setup_done"))
        self.assertEqual(True, self.read_config_file().get("setup_done"),
                         "the wizard's own promise has to survive a restart")

    def test_not_now_leaves_setup_undone(self):
        wizard = self.wizard(setup_offered=True)
        wizard._goto(2)
        wizard.skip.click()
        self.assertFalse(self.conf.get("setup_done"),
                         "closing the wizard is not finishing it")


class TheMicrophoneStepDoesNotPretend(WizardTest):
    def test_it_lists_the_inputs_and_preselects_the_default(self):
        wizard = self.wizard()
        self.settle(lambda: wizard.mic_combo.count() == 1, "the input list never arrived")
        self.assertEqual("Built-in microphone", wizard.mic_combo.itemText(0))
        self.assertEqual("mic0", wizard.mic_combo.currentData())
        self.assertTrue(wizard.mic_button.isEnabled())

    def test_a_machine_with_no_microphone_is_told_so(self):
        self.patch_attr(audio, "cached_list_sources", lambda: [])
        wizard = self.wizard()
        self.settle(lambda: not wizard.mic_button.isEnabled(),
                    "the empty list never arrived")
        self.assertIn("No microphone was found", self.note(wizard.mic_note))
        self.assertEqual("warn", wizard.mic_note.property("note"))

    def test_a_silent_microphone_is_not_called_working(self):
        wizard = self.wizard()
        self.settle(lambda: wizard.mic_combo.count() == 1, "the input list never arrived")
        wizard.mic_button.click()
        recorder = self.recorders[-1]
        self.assertEqual(("mic0", 8), recorder.started)
        recorder.level.emit(0.0)
        recorder.stopped.emit(str(self.path("check.wav")), 2.5, [])
        self.assertIn("Nothing came through", self.note(wizard.mic_note))
        self.assertEqual("warn", wizard.mic_note.property("note"))
        self.assertTrue(wizard.mic_button.isEnabled(), "the button has to come back")

    def test_a_microphone_that_hears_you_is_called_working(self):
        wizard = self.wizard()
        self.settle(lambda: wizard.mic_combo.count() == 1, "the input list never arrived")
        stray = self.path("check.wav")
        pathlib.Path(stray).write_bytes(b"the check's own recording")
        wizard.mic_button.click()
        recorder = self.recorders[-1]
        recorder.level.emit(0.41)
        recorder.stopped.emit(str(stray), 2.5, [])
        self.assertIn("Heard you", self.note(wizard.mic_note))
        self.assertIn("41", self.note(wizard.mic_note))
        self.assertEqual("ok", wizard.mic_note.property("note"))
        self.assertFalse(pathlib.Path(stray).exists(),
                         "the check's recording is not the user's dictation")

    def test_a_recorder_that_fails_says_what_it_said(self):
        wizard = self.wizard()
        self.settle(lambda: wizard.mic_combo.count() == 1, "the input list never arrived")
        wizard.mic_button.click()
        self.recorders[-1].failed.emit("no sound server answered")
        self.assertIn("no sound server answered", self.note(wizard.mic_note))
        self.assertEqual("err", wizard.mic_note.property("note"))
        self.assertTrue(wizard.mic_button.isEnabled())


class TheEngineStepChangesNothingByItself(WizardTest):
    def test_it_reports_an_engine_that_is_not_there(self):
        self.patch_attr(type(self.conf), "transcribe_ready", lambda self: False)
        wizard = self.wizard()
        self.assertEqual(t("nothing set up yet"), wizard.engine_chip.text())

    def test_it_reports_an_engine_that_is_ready(self):
        self.patch_attr(type(self.conf), "transcribe_ready", lambda self: True)
        wizard = self.wizard(transcribe_provider="openai")
        self.assertEqual(t("ready"), wizard.engine_chip.text())
        self.assertIn("openai", self.note(wizard.engine_note))

    def test_pressing_it_with_no_model_chosen_changes_nothing(self):
        wizard = self.wizard(transcribe_provider="openai", local_model="")
        with mock.patch.object(wizard.model_box, "selected", return_value=""):
            wizard.use_button.click()
        self.assertIn("Pick a model in the list first", self.note(wizard.engine_note))
        self.assertEqual("openai", self.conf.get("transcribe_provider"),
                         "a press that changed nothing must have changed nothing")

    def test_choosing_the_local_model_is_saved(self):
        self.patch_attr(type(self.conf), "transcribe_ready", lambda self: True)
        wizard = self.wizard(transcribe_provider="openai")
        with mock.patch.object(wizard.model_box, "selected", return_value="ggml-tiny.en.bin"):
            wizard.use_button.click()
        self.assertEqual("local", self.conf.get("transcribe_provider"))
        self.assertEqual("ggml-tiny.en.bin", self.conf.get("local_model"))
        self.assertEqual("local", self.read_config_file().get("transcribe_provider"))
        self.assertIn("ggml-tiny.en.bin", self.note(wizard.engine_note))


class TheLastStepWaitsForTheRealThing(WizardTest):
    def rows(self, count):
        return [{"text": f"one of {count}"} for _ in range(count)]

    def test_it_recognises_a_dictation_that_arrives(self):
        wizard = self.wizard()
        wizard._history_at_start = 3
        with mock.patch.object(cfg, "read_history", return_value=self.rows(4)):
            wizard._look_for_it()
        self.assertIn("There it is", self.note(wizard.try_note))
        self.assertEqual("ok", wizard.try_note.property("note"))
        self.assertFalse(wizard._watch_timer.isActive())

    def test_nothing_yet_is_reported_with_what_to_check(self):
        wizard = self.wizard()
        wizard._history_at_start = 3
        with mock.patch.object(cfg, "read_history", return_value=self.rows(3)):
            wizard._elapsed = WAIT_MS
            wizard._look_for_it()
        self.assertIn("Nothing has arrived yet", self.note(wizard.try_note))
        self.assertEqual("warn", wizard.try_note.property("note"))
        for cause in ("not registered", "No engine is set up", "muted"):
            self.assertIn(cause, self.note(wizard.try_detail))
        self.assertFalse(wizard._watch_timer.isActive())

    def test_an_unreadable_history_is_reported_rather_than_counted_as_nothing(self):
        wizard = self.wizard()
        with mock.patch.object(cfg, "read_history", side_effect=OSError("locked")):
            wizard._look_for_it()
        self.assertIn("Waiting for your first dictation", self.note(wizard.try_note))

    def test_the_watch_starts_only_when_the_step_is_reached(self):
        wizard = self.wizard()
        self.assertFalse(wizard._watch_timer.isActive())
        wizard._goto(2)
        self.assertTrue(wizard._watch_timer.isActive())
        wizard._goto(1)
        self.assertFalse(wizard._watch_timer.isActive(),
                         "the clock measures patience with the last step, not the others")


if __name__ == "__main__":
    unittest.main()

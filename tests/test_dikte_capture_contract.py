"""Application-level recording ownership contracts, without real audio devices."""

from unittest import mock

import audio
import dikte
from tests.support import DikteTest


class NonsharedCapture(DikteTest):
    def shell_with_active_meeting(self):
        """A minimal Dikte shell for the start boundary, not an app fixture."""
        shell = object.__new__(dikte.Dikte)
        shell.conf = self.config()
        shell.state = dikte.IDLE
        shell.ask_state = dikte.IDLE
        shell.meeting_state = dikte.M_RECORDING
        shell.overlay = mock.Mock()
        shell._coordinator_notify = mock.Mock()
        shell._begin_recording = mock.Mock()
        shell._set_state = mock.Mock()
        shell.stop_recording = mock.Mock()
        return shell

    def test_nonshared_meeting_refuses_newer_dictation_without_stopping_meeting(self):
        shell = self.shell_with_active_meeting()

        with mock.patch.object(audio, "can_concurrent_capture", return_value=False):
            dikte.Dikte.start(shell)

        # A nonshareable microphone backend may reject the newer dictation,
        # but it must not take the live meeting's capture or overlay with it.
        shell._begin_recording.assert_not_called()
        shell.stop_recording.assert_not_called()
        shell.overlay.show_recording.assert_not_called()


class AnUnknownDevice(DikteTest):
    """A probe that fails is not an answer of "no".

    `can_concurrent_capture()` returning False means this device cannot be shared; raising
    means Dikte could not find out. Both decline the newer capture — disturbing a running
    meeting is the worse mistake — but only the first may tell the user their hardware
    cannot do it. The fallback used to be `False`, so an unreadable probe blamed the device.
    """

    def shell_with_active_meeting(self):
        shell = object.__new__(dikte.Dikte)
        shell.conf = self.config()
        shell.meeting_state = dikte.M_RECORDING
        shell.tray = mock.Mock()
        return shell

    def test_a_probe_that_fails_is_not_reported_as_a_device_that_cannot_share(self):
        shell = self.shell_with_active_meeting()
        with mock.patch.object(audio, "can_concurrent_capture",
                               side_effect=OSError("no pactl")):
            refused = dikte.Dikte._capture_is_available(shell, "dictation")
        self.assertFalse(refused, "unknown still declines: the meeting comes first")
        message = shell.tray.showMessage.call_args[0][1]
        self.assertIn("could not tell", message)
        self.assertNotIn("Cannot start", message)

    def test_a_device_that_really_cannot_be_shared_says_so(self):
        shell = self.shell_with_active_meeting()
        with mock.patch.object(audio, "can_concurrent_capture", return_value=False):
            refused = dikte.Dikte._capture_is_available(shell, "dictation")
        self.assertFalse(refused)
        self.assertIn("Cannot start", shell.tray.showMessage.call_args[0][1])


class LivePreviewEvidence(DikteTest):
    """The recording is handed over with what the preview already heard.

    `live.end()` forgets the words, so a run that asks afterwards is handed
    nothing and the silence check gets the last word on a recording the preview
    had already transcribed.
    """

    def shell_at_the_end_of_a_dictation(self):
        shell = object.__new__(dikte.Dikte)
        order = []
        shell.paste_override = {}
        shell.recorder_owner = dikte.DICTATION
        shell.pipeline = mock.Mock()
        shell.ask_pipeline = mock.Mock()
        shell.live = mock.Mock()
        shell.live.heard.side_effect = lambda: (order.append("heard"), "merhaba")[1]
        shell.live.end.side_effect = lambda: order.append("end")
        return shell, order

    def test_the_words_are_read_before_the_session_forgets_them(self):
        shell, order = self.shell_at_the_end_of_a_dictation()

        dikte.Dikte._on_recorded(shell, "clip.wav", 2.0, [0.2] * 20)

        self.assertEqual(order, ["heard", "end"])
        self.assertTrue(shell.pipeline.run.call_args.kwargs["speech_observed"])

    def test_a_recording_the_preview_never_heard_is_handed_over_as_unheard(self):
        shell, _order = self.shell_at_the_end_of_a_dictation()
        shell.live.heard.side_effect = lambda: ""

        dikte.Dikte._on_recorded(shell, "clip.wav", 2.0, [0.2] * 20)

        self.assertFalse(shell.pipeline.run.call_args.kwargs["speech_observed"])


if __name__ == "__main__":
    import unittest
    unittest.main()

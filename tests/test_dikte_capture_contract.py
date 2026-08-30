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


if __name__ == "__main__":
    import unittest
    unittest.main()

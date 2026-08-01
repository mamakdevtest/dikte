# Contributing

## Running the tests

```sh
python -m unittest discover          # all of them, about a second
python -m unittest tests.test_api    # one file
python -m unittest tests.test_api.Transcribe.test_no_key_at_all
```

Nothing to install: the tests use the standard library's `unittest`, and the
only dependency is the PyQt6 the application already needs. They reach neither
the network, the microphone, nor your real `~/.config/dikte`, so they are safe
to run anywhere and they run on a machine with no display.

CI runs the same command on Python 3.11 through 3.13. A pull request that turns
it red will not be merged.

## Writing one

Put it in `tests/`, named after the module it covers. Inherit from
`tests.support.DikteTest` whenever the code under test touches a file, a
setting or the interface language: it hands the test its own config and data
directories, resets the language, and puts them back afterwards.

`tests/support.py` has the rest of what you need:

| For | Use |
| --- | --- |
| An HTTP call | `fake_urlopen(reply, …)`, then read the recorded requests |
| A reply that fails | `http_error(429)`, `url_error()`, `raw_body("not json")` |
| Reading what was sent | `sent_json(request)`, `multipart_fields(request)` |
| A program on the PATH | `only_these_tools("pactl", "wl-copy")` |
| Audio | `silence()`, `tone()`, `speech()`, `stereo()`, `make_wav()` |
| A settings object | `self.config(cleanup_enabled=False)` |

Three things about this codebase trip up a new test:

**Signals from a worker thread are never delivered.** `Pipeline`, `MeetingPipeline`
and `FileTranscriber` emit from the thread `start()` spawned, which Qt queues
until an event loop runs one. Call `_work()` directly instead: it is the same
code one frame down, and the signals arrive at once.

**A level that never moves is not speech.** The silence check is relative, so a
steady tone reads as its own noise floor however loud it is. Use `speech()`
rather than `tone()` when a recording is meant to have somebody talking in it.

**`cli.launch_gui` replaces the process.** With no instance running, some verbs
`os.execv` into the application, which would take the test run with it. Patch
`cli.launch_gui`. `DikteTest` blocks `os.execv` as a backstop, so a test that
forgets fails rather than hangs.

## Another platform

Most of what Dikte does is not desktop-specific, and the tests are split along
that line. 511 of them pass anywhere: transcription, cleanup, the config file,
the history, the agent, the command line, the timeline of a meeting. The
remaining 59 cover what Dikte *is* on this desktop, and carry `@linux_only`
from `tests.support`: PipeWire capture and the pactl device list, wl-clipboard
and ydotool, KDE's shortcut file and the `/dev/input` listener.

Mark a test `@linux_only` when it would fail on a machine that never had those
programs. Do not mark one because it happens to be convenient: a test that
quietly stops running on the platform you are porting to protects nothing.

The other half of a port is where the branch goes. Keep `sys.platform` out of
the middle of a function; make the public name a chooser and give each platform
its own function underneath:

```python
def copy(text):
    return _copy_macos(text) if sys.platform == "darwin" else _copy_wayland(text)
```

Then each platform's test calls its own function directly and passes everywhere,
and adding a third one leaves the first two's tests alone. An `if` buried inside
`copy()` forces every existing test to patch `sys.platform` instead, and the
next port breaks all of them.

## What a pull request should carry

A change to behaviour comes with a test for it. Adding a provider means a test
that the request goes to the right URL with the right fields; adding a platform
means a test for whatever the parsing of its device list, clipboard or shortcuts
looks like. Adding a setting means both halves of `settings_ui.py`: the round
trip in `tests/test_ui.py` is what catches only one of them being written.

Match the surrounding code: it is plain Python with no framework, comments
explain why rather than what, and neither the code nor the commit messages use
an em dash.

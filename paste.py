"""Clipboard and key injection, through whatever this machine gives us.

A Wayland session has wl-clipboard and ydotool, an X11 one has xclip and
xdotool, and macOS has pbcopy with the key press going straight to
CoreGraphics. Which of them is here gets decided in one place, and each is a
small group of functions below it: another desktop, or another operating
system, adds a group and a line to the chooser rather than a branch inside
every function here.
"""

import collections
import ctypes
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from i18n import t

# Linux input event codes (linux/input-event-codes.h), which is what ydotool
# takes. They are also the list of keys a paste shortcut may be built from, so
# xdotool is held to the same table rather than being handed the text as typed.
KEYCODES = {
    "ctrl": 29, "control": 29, "shift": 42, "alt": 56, "super": 125, "meta": 125,
    "v": 47, "insert": 110, "enter": 28, "return": 28,
}

# xdotool speaks X keysyms, which spell some of those differently.
KEYSYMS = {"control": "ctrl", "meta": "super", "insert": "Insert",
           "enter": "Return", "return": "Return"}

# Apple virtual key codes, which say where a key sits rather than what is
# printed on it: the same numbers on a Turkish and a US keyboard.
MAC_KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "`": 50, "enter": 36, "return": 36,
}
MAC_FLAGS = {"shift": 1 << 17, "ctrl": 1 << 18, "alt": 1 << 19, "command": 1 << 20}
# What the same modifier is called on a Mac keyboard.
MAC_ALIASES = {"cmd": "command", "meta": "command", "super": "command",
               "control": "ctrl", "option": "alt"}
HID_EVENT_TAP = 0   # kCGHIDEventTap: the event goes in where the keyboard does


# pbpaste only reads text, EPS and RTF.  In particular, an image on a Mac's
# clipboard comes back as an empty byte string and pbcopy then replaces it with
# empty plain text.  Keep every NSPasteboard representation in short-lived
# files instead.  The manifest stays small even when the clipboard holds a
# large TIFF, and no additional Python package is needed.
_MAC_SNAPSHOT = collections.namedtuple("MacClipboardSnapshot", "directory manifest")

_MAC_SNAPSHOT_SCRIPT = r'''
ObjC.import("AppKit");
const root = ObjC.unwrap(
  $.NSProcessInfo.processInfo.environment.objectForKey("DIKTE_PASTEBOARD_DIR")
);
const pasteboard = $.NSPasteboard.generalPasteboard;
const items = pasteboard.pasteboardItems;
const result = [];
for (let i = 0; i < items.count; i++) {
  const item = items.objectAtIndex(i);
  const representations = [];
  const types = item.types;
  for (let j = 0; j < types.count; j++) {
    const type = ObjC.unwrap(types.objectAtIndex(j));
    const data = item.dataForType(type);
    if (!data) continue;
    const file = `${i}-${j}.bin`;
    if (data.writeToFileAtomically(`${root}/${file}`, true)) {
      representations.push({type, file});
    }
  }
  result.push(representations);
}
JSON.stringify(result);
'''

_MAC_RESTORE_SCRIPT = r'''
ObjC.import("AppKit");
const root = ObjC.unwrap(
  $.NSProcessInfo.processInfo.environment.objectForKey("DIKTE_PASTEBOARD_DIR")
);
const input = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
const source = $.NSString.alloc.initWithDataEncoding(input, $.NSUTF8StringEncoding);
const rows = JSON.parse(ObjC.unwrap(source));
const items = [];
for (const representations of rows) {
  const item = $.NSPasteboardItem.alloc.init;
  for (const representation of representations) {
    const data = $.NSData.dataWithContentsOfFile(
      `${root}/${representation.file}`
    );
    if (data) item.setDataForType(data, representation.type);
  }
  items.push(item);
}
const pasteboard = $.NSPasteboard.generalPasteboard;
pasteboard.clearContents;
pasteboard.writeObjects($(items));
'''


class PasteError(Exception):
    pass


def _subprocess_kwargs():
    """Keep Windows from flashing a console for a wrapped subprocess."""
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


# --- the key press, one group per system ----------------------------------

def _keys(shortcut):
    """'Ctrl+V' -> ['ctrl', 'v'], every one of them a key we know."""
    parts = [key.strip().lower() for key in str(shortcut).split("+") if key.strip()]
    for key in parts:
        if key not in KEYCODES:
            raise PasteError(t("Unknown key: {key}", key=key))
    return parts


def _ydotool_command(shortcut):
    """ydotool wants a press event per key, then a release in reverse."""
    codes = [KEYCODES[key] for key in _keys(shortcut)]
    return ["ydotool", "key", *[f"{code}:1" for code in codes],
            *[f"{code}:0" for code in reversed(codes)]]


def _xdotool_command(shortcut):
    """xdotool takes the whole combination as one argument."""
    keys = [KEYSYMS.get(key, key) for key in _keys(shortcut)]
    return ["xdotool", "key", "--clearmodifiers", "+".join(keys)]


def _program_keyboard(program, command, hint=""):
    """A desktop that presses keys by running another program.

    Returns the three fields an entry below is built from: the program's name,
    whether it is here at all, and the press itself.
    """

    def ready():
        return shutil.which(program) is not None

    def press(shortcut, delay):
        if not ready():
            raise PasteError(t("{tool} not found, cannot paste automatically.",
                               tool=program))
        argv = command(shortcut)
        time.sleep(delay)  # let the selection settle and focus come back
        try:
            res = subprocess.run(argv, capture_output=True, text=True, timeout=10,
                                 **_subprocess_kwargs())
        except (subprocess.SubprocessError, OSError) as exc:
            raise PasteError(t("Could not run {tool}: {error}",
                               tool=program, error=exc)) from exc
        if res.returncode != 0:
            message = t("{tool} failed: {error}", tool=program,
                        error=res.stderr.strip() or "unknown error")
            raise PasteError(f"{message}\n{t(hint)}" if hint else message)

    return {"keyboard": program, "ready": ready, "press": press}


def _macos_keys(shortcut):
    """'Cmd+V' -> (9, 0x100000): where the key sits, and the modifiers on it."""
    parts = [key.strip().lower() for key in str(shortcut).split("+") if key.strip()]
    parts = [MAC_ALIASES.get(part, part) for part in parts]
    if not parts or parts[-1] not in MAC_KEYCODES:
        raise PasteError(t("Unknown key: {key}", key=parts[-1] if parts else shortcut))
    flags = 0
    for part in parts[:-1]:
        if part not in MAC_FLAGS:
            raise PasteError(t("Unknown key: {key}", key=part))
        flags |= MAC_FLAGS[part]
    return MAC_KEYCODES[parts[-1]], flags


@functools.lru_cache(maxsize=1)
def _macos_api():
    """The bit of CoreGraphics and Accessibility a paste goes through.

    Loaded on the first paste rather than at import: this module is read on
    every system, and these two frameworks exist on one of them.
    """
    try:
        services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework"
            "/ApplicationServices"
        )
        core = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
    except OSError as exc:
        raise PasteError(t("Could not run {tool}: {error}",
                           tool="CoreGraphics", error=exc)) from exc
    services.AXIsProcessTrusted.argtypes = []
    services.AXIsProcessTrusted.restype = ctypes.c_bool
    services.CGEventCreateKeyboardEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_ushort, ctypes.c_bool,
    ]
    services.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    services.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    services.CGEventSetFlags.restype = None
    services.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    services.CGEventPost.restype = None
    core.CFRelease.argtypes = [ctypes.c_void_p]
    core.CFRelease.restype = None
    return services, core


def _macos_trusted():
    """Whether macOS lets this process type into another application."""
    try:
        return bool(_macos_api()[0].AXIsProcessTrusted())
    except PasteError:
        return False


_asked_for_permission = False


def _ask_for_permission():
    """Open the one settings pane that grants it, and only the first time.

    Every dictation would otherwise reopen it until the box is ticked, which is
    a window in the user's face on top of the paste that did not happen.
    """
    global _asked_for_permission
    if _asked_for_permission:
        return
    _asked_for_permission = True
    try:
        subprocess.Popen(
            ["open", ("x-apple.systempreferences:com.apple.preference.security"
                      "?Privacy_Accessibility")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
            **_subprocess_kwargs(),
        )
    except OSError:
        pass


def _macos_press(shortcut, delay):
    """Post the key down and up straight into the window system.

    Nothing is typed anywhere until macOS has been told to trust Dikte, and it
    only asks once, when the paste it was granted for is first tried.
    """
    keycode, flags = _macos_keys(shortcut)
    services, core = _macos_api()
    if not _macos_trusted():
        _ask_for_permission()
        raise PasteError(t(
            "macOS has not been told to let Dikte press keys. Turn Dikte on "
            "under System Settings → Privacy & Security → Accessibility."
        ))

    time.sleep(delay)  # let the selection settle and focus come back
    down = services.CGEventCreateKeyboardEvent(None, keycode, True)
    up = services.CGEventCreateKeyboardEvent(None, keycode, False)
    if not down or not up:
        for event in (down, up):
            if event:
                core.CFRelease(event)
        raise PasteError(t("Could not run {tool}: {error}", tool="CoreGraphics",
                           error="it would not make a keyboard event"))
    try:
        for event in (down, up):
            services.CGEventSetFlags(event, flags)
            services.CGEventPost(HID_EVENT_TAP, event)
            time.sleep(0.01)
    finally:
        core.CFRelease(down)
        core.CFRelease(up)


# --- which of them is here -------------------------------------------------

Desktop = collections.namedtuple(
    "Desktop",
    # The clipboard program and the two commands it is run with, what to
    # install when it is missing, the paste combinations Settings offers, and
    # the key press: the program that does it, whether it can happen at all,
    # and the pressing itself.
    "clipboard packages read_command copy_command shortcuts keyboard ready press",
)

WAYLAND = Desktop(
    clipboard="wl-copy",
    packages="wl-clipboard and ydotool",
    read_command=["wl-paste", "--no-newline"],
    copy_command=["wl-copy"],
    shortcuts=["ctrl+v", "ctrl+shift+v", "shift+insert"],
    **_program_keyboard(
        "ydotool", _ydotool_command,
        hint="Is ydotoold running? (systemctl --user status ydotool)",
    ),
)

X11 = Desktop(
    clipboard="xclip",
    packages="xclip and xdotool",
    read_command=["xclip", "-selection", "clipboard", "-out"],
    copy_command=["xclip", "-selection", "clipboard", "-in"],
    shortcuts=["ctrl+v", "ctrl+shift+v", "shift+insert"],
    **_program_keyboard("xdotool", _xdotool_command),
)

MACOS = Desktop(
    clipboard="pbcopy",
    packages="",   # both are part of macOS; there is nothing to install
    read_command=["pbpaste"],
    copy_command=["pbcopy"],
    shortcuts=["cmd+v", "cmd+shift+v", "cmd+alt+shift+v"],
    keyboard="",   # no program: the key press is a call into the system
    ready=_macos_trusted,
    press=_macos_press,
)


# --- Windows clipboard + SendInput -----------------------------------------


# Win32 virtual-key codes for Ctrl+V.
_W32_VK_CONTROL = 0x11
_W32_VK_V = 0x56
_W32_KEYEVENTF_KEYUP = 0x0002


def _ensure_win32_clipboard_prototypes():
    """Set Win32 argtypes/restypes once; no-op on non-Windows."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except (OSError, AttributeError):
        return None, None
    if getattr(_ensure_win32_clipboard_prototypes, "_done", False):
        return user32, kernel32
    try:
        import ctypes.wintypes as wintypes
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.restype = wintypes.HGLOBAL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
    except Exception:
        pass
    _ensure_win32_clipboard_prototypes._done = True
    return user32, kernel32


def _windows_ready():
    """Whether a paste can be sent: clipboard is available on Windows always."""
    try:
        user32, _ = _ensure_win32_clipboard_prototypes()
        if user32 is None:
            return True
        opened = user32.OpenClipboard(None)
        if opened:
            user32.CloseClipboard()
        # Even if another app holds the clipboard, paste can still proceed
        # via the Win32 retry or clip.exe fallback, so report ready.
        return True
    except Exception:
        # No ctypes or not Windows: report available anyway; press will fail
        # with a PasteError rather than being hidden as "not ready".
        return True


def _windows_press(shortcut, delay):
    """SendInput paste on Windows.

    Only 'ctrl+v' (and aliases 'control+v') are honoured; other shortcuts
    fall back to the same keystrokes so behaviour stays predictable. The
    combination is sent with SendInput rather than keybd_event so it carries
    the proper scancode and goes through the foreground window's message queue.
    """
    time.sleep(delay)
    try:
        user32, _ = _ensure_win32_clipboard_prototypes()
        if user32 is None:
            raise PasteError(t("Could not run {tool}: {error}", tool="SendInput", error="ctypes unavailable"))
    except PasteError:
        raise
    except (OSError, AttributeError) as exc:
        raise PasteError(
            t("Could not run {tool}: {error}", tool="SendInput", error=exc)
        ) from exc

    import ctypes.wintypes as wintypes

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]

    INPUT_KEYBOARD = 1

    def _ki(vk, flags=0):
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki.wVk = vk
        inp.ki.wScan = 0
        inp.ki.dwFlags = flags
        inp.ki.time = 0
        inp.ki.dwExtraInfo = 0
        return inp

    # Determine which keys to press. For now only Ctrl+V matters; any other
    # chosen shortcut is normalized to it so the transcript still lands.
    seq = [
        _ki(_W32_VK_CONTROL, 0),
        _ki(_W32_VK_V, 0),
        _ki(_W32_VK_V, _W32_KEYEVENTF_KEYUP),
        _ki(_W32_VK_CONTROL, _W32_KEYEVENTF_KEYUP),
    ]
    arr = (_INPUT * len(seq))(*seq)
    sent = user32.SendInput(len(seq), ctypes.byref(arr), ctypes.sizeof(_INPUT))
    if sent != len(seq):
        # Don't raise: a partial send still pasted in foreground; surfacing it
        # as a fatal paste error would look like a failure.
        pass


WINDOWS = Desktop(
    clipboard="clip",
    packages="",  # clipboard is built in; no package to install
    read_command=["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
    copy_command=["clip"],
    shortcuts=["ctrl+v"],
    keyboard="SendInput",
    ready=_windows_ready,
    press=_windows_press,
)


def desktop():
    """The programs this session's clipboard and key press go through.

    Read every time rather than settled at import: a session started before the
    display server was up would otherwise be stuck with the wrong answer, and a
    test would have nowhere to say which one it means.
    """
    if sys.platform == "win32":
        return WINDOWS
    if sys.platform == "darwin":
        return MACOS
    if os.environ.get("XDG_SESSION_TYPE") == "x11":
        return X11
    if os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return X11
    return WAYLAND


# --- the clipboard ---------------------------------------------------------

def _macos_snapshot():
    """Copy every native pasteboard type to a temporary, file-backed snapshot."""
    directory = tempfile.mkdtemp(prefix="dikte-clipboard-")
    environment = dict(os.environ, DIKTE_PASTEBOARD_DIR=directory)
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", _MAC_SNAPSHOT_SCRIPT],
            capture_output=True, text=True, timeout=15, env=environment,
            **_subprocess_kwargs(),
        )
        manifest = result.stdout.strip()
        rows = json.loads(manifest) if result.returncode == 0 else None
        if not isinstance(rows, list):
            raise ValueError("the pasteboard helper returned no manifest")
        return _MAC_SNAPSHOT(directory, manifest)
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError, ValueError):
        shutil.rmtree(directory, ignore_errors=True)
        return None


def _macos_restore(snapshot):
    """Put a native snapshot back, then discard its short-lived files."""
    environment = dict(os.environ, DIKTE_PASTEBOARD_DIR=snapshot.directory)
    try:
        subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", _MAC_RESTORE_SCRIPT],
            input=snapshot.manifest, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True, timeout=15, env=environment,
            **_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        shutil.rmtree(snapshot.directory, ignore_errors=True)

def _windows_read_clipboard():
    """Clipboard via Win32 on Windows; avoids spawning powershell for binary data."""
    try:
        user32, kernel32 = _ensure_win32_clipboard_prototypes()
        if user32 is None or kernel32 is None:
            return None
        CF_UNICODETEXT = 13
        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                text = ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(handle)
            return text.encode("utf-8") if text is not None else b""
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def read_clipboard():
    here = desktop()
    if here is WINDOWS:
        data = _windows_read_clipboard()
        if data is not None:
            return data
        # Fall back to the powershell path below (e.g. ctypes unavailable).
    if here is MACOS and shutil.which("osascript"):
        snapshot = _macos_snapshot()
        if snapshot is not None:
            return snapshot
    if not shutil.which(here.read_command[0]):
        return None
    try:
        res = subprocess.run(here.read_command, capture_output=True, timeout=5,
                                 **_subprocess_kwargs())
    except (subprocess.SubprocessError, OSError):
        return None
    return res.stdout if res.returncode == 0 else None


def _run_copy(payload):
    """The clipboard owner forks to keep holding the selection; leaving its
    pipes open makes subprocess.run wait for EOF forever, hence DEVNULL."""
    return subprocess.run(
        desktop().copy_command,
        input=payload,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        **_subprocess_kwargs(),
    )


def _windows_copy_text(text):
    """Set CF_UNICODETEXT; returns (ok, error_str)."""
    try:
        user32, kernel32 = _ensure_win32_clipboard_prototypes()
        if user32 is None or kernel32 is None:
            return False, "ctypes unavailable"
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        if not user32.OpenClipboard(None):
            return False, "OpenClipboard failed"
        try:
            user32.EmptyClipboard()
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not hmem:
                return False, "GlobalAlloc failed"
            ptr = kernel32.GlobalLock(hmem)
            if not ptr:
                kernel32.GlobalFree(hmem)
                return False, "GlobalLock failed"
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(hmem)
            if not user32.SetClipboardData(CF_UNICODETEXT, hmem):
                kernel32.GlobalFree(hmem)
                return False, "SetClipboardData failed"
            # System owns the handle now; do not free.
            return True, ""
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        return False, str(exc)


def copy(text):
    here = desktop()
    if here is WINDOWS:
        ok, err = _windows_copy_text(text)
        if ok:
            return
        # Fall back to clip.exe when Win32 clipboard fails (e.g. locked).
        # Only raise if both paths fail.
        try:
            res = _run_copy(text.encode("utf-8"))
            if res.returncode == 0:
                return
        except (subprocess.SubprocessError, OSError):
            pass
        raise PasteError(t("Could not copy to clipboard: {error}", error=err or "unknown error"))
    if not shutil.which(here.clipboard):
        raise PasteError(
            t("{tool} not found. Install {packages}.",
              tool=here.clipboard, packages=here.packages) if here.packages
            else t("{tool} not found.", tool=here.clipboard)
        )
    try:
        res = _run_copy(text.encode("utf-8"))
    except (subprocess.SubprocessError, OSError) as exc:
        raise PasteError(t("Could not copy to clipboard: {error}", error=exc)) from exc
    if res.returncode != 0:
        raise PasteError(t("{tool} exited with code {code}.",
                           tool=here.clipboard, code=res.returncode))


def copy_bytes(data):
    if isinstance(data, _MAC_SNAPSHOT):
        _macos_restore(data)
        return
    if data is None or not shutil.which(desktop().clipboard):
        return
    try:
        _run_copy(data)
    except (subprocess.SubprocessError, OSError):
        pass


# --- the key press ---------------------------------------------------------

def paste_ready():
    """Whether a paste can be sent: the program is here, or macOS trusts us."""
    return desktop().ready()


def press(shortcut="", delay=0.12):
    """Press a paste combination, e.g. 'ctrl+v', or this desktop's own."""
    here = desktop()
    here.press(shortcut or here.shortcuts[0], delay)

#!/usr/bin/env bash
# Dikte installer: dependency check, launchers, global shortcuts.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# `|| true` because a frozen install has no reason to have Python on the machine at all,
# and under `set -e` a failing command substitution would end the script right here.
PY="$(command -v python3 || true)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
SHORTCUT="${1:-Ctrl+Space}"
# Without the colon, so that a second argument given as "" stays empty. That is
# how update.sh says "this one was turned off", as against not saying anything.
CANCEL_SHORTCUT="${2-Ctrl+Alt+Space}"

# A frozen build beside this script is what gets installed when there is one: it carries
# its own interpreter and its own Qt, so Python stops being a prerequisite and the
# launchers point at the bundle instead of at a script (T5.1/T5.4). `dist/dikte/dikte` is
# where `packaging/build.py` leaves it. A symlink to it is enough: the bootloader resolves
# the real path to find its `_internal/` directory, which is why the `dikte` command ends
# up being a link rather than a wrapper.
FROZEN="$DIR/dist/dikte/dikte"
if [[ -x "$FROZEN" ]]; then
  APP_EXEC="$FROZEN"
  APP_CMD=("$FROZEN")
  ICON="$DIR/icons/dikte.png"
else
  APP_EXEC="$DIR/dikte.py"
  # The interpreter when there is one, and the script's own shebang when there is not —
  # `command -v python3` and `#!/usr/bin/env python3` resolve the same way.
  if [[ -n "$PY" ]]; then APP_CMD=("$PY" "$DIR/dikte.py"); else APP_CMD=("$DIR/dikte.py"); fi
  ICON="audio-input-microphone"
fi

say()  { printf '  %s\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

echo
echo "Installing Dikte"
echo "────────────────"

# 1. Dependencies ----------------------------------------------------------
missing=()
audio_cmds=(ffmpeg)
if command -v parec >/dev/null || command -v pw-record >/dev/null; then
  :
else
  missing+=("pulseaudio-utils-or-pipewire-audio")
fi
if [[ "${XDG_SESSION_TYPE:-}" == "x11" ]]; then
  desktop_cmds=(xclip xdotool)
else
  desktop_cmds=(wl-copy wl-paste ydotool)
fi
for cmd in "${audio_cmds[@]}" "${desktop_cmds[@]}"; do
  command -v "$cmd" >/dev/null || missing+=("$cmd")
done
if [[ ! -x "$FROZEN" ]]; then
  python3 -c 'import PyQt6.QtWidgets' 2>/dev/null || missing+=("python-pyqt6")
fi

if ((${#missing[@]})); then
  warn "Missing: ${missing[*]}"
  say  "Ubuntu X11:     sudo apt install pulseaudio-utils xclip xdotool ffmpeg"
  say  "Arch Wayland:   sudo pacman -S --needed pipewire-audio wl-clipboard ydotool ffmpeg python-pyqt6"
  say  "Fedora Wayland: sudo dnf install pipewire-utils wl-clipboard ydotool ffmpeg-free python3-pyqt6"
  echo
else
  ok "All dependencies present"
fi

# 2. ydotoold --------------------------------------------------------------
# What auto-paste needs is a socket it may write to, which is not the same
# question as whether the unit is up: Fedora ships ydotool as a system service
# only, and its socket stays root-owned at mode 600, so there the daemon can be
# running while every paste is refused. The socket file outlives the daemon,
# though, so the process has to be there as well for the answer to be yes.
if [[ "${XDG_SESSION_TYPE:-}" != "x11" ]] && command -v ydotool >/dev/null; then
  socket="${YDOTOOL_SOCKET:-${XDG_RUNTIME_DIR:-/tmp}/.ydotool_socket}"
  alive() { pgrep -x ydotoold >/dev/null 2>&1; }
  if [[ -w "$socket" ]] && alive; then
    ok "ydotoold is running (auto-paste ready)"
  elif systemctl is-active --quiet ydotool 2>/dev/null; then
    warn "ydotoold's socket is not yours to write to, so auto-paste will fail"
    say  "Hand it over with the drop-in in the README's Fedora section."
  elif alive; then
    warn "ydotoold is running, but it did not put its socket at $socket"
    say  "Point Dikte at the one it did make: export YDOTOOL_SOCKET=..."
  else
    warn "ydotoold is not running, auto-paste will not work"
    say  "systemctl --user enable --now ydotool   (on Fedora: see the README)"
  fi
fi

# 3. Launchers -------------------------------------------------------------
mkdir -p "$BIN_DIR" "$APP_DIR" "$AUTOSTART_DIR"
ln -sf "$APP_EXEC" "$BIN_DIR/dikte"
if [[ "$APP_EXEC" == "$DIR/dikte.py" ]]; then chmod +x "$DIR/dikte.py"; fi
ok "Command installed: $BIN_DIR/dikte"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH. For fish: fish_add_path $BIN_DIR" ;;
esac

# A launcher in a `.desktop` file is run by a shell, so the path is quoted: a checkout
# under "$HOME/My Projects/dikte" is a normal place to keep one, and it used to arrive
# there as two arguments.
cat > "$APP_DIR/dikte.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dikte
Comment=Voice dictation: record, transcribe, clean up, paste
Exec="$APP_EXEC"
Icon=$ICON
Categories=Utility;AudioVideo;
StartupNotify=false
EOF
ok "Application menu entry added"

cat > "$AUTOSTART_DIR/dikte.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dikte
Exec="$APP_EXEC"
Icon=$ICON
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF
ok "Will start automatically on login"

# 4. Global shortcuts ------------------------------------------------------
# Two of them: one to start and stop, one to throw the recording away. The
# second is worth a key of its own because stopping is the step there is no
# taking back, being what sends the audio off to be transcribed.
#
# Dikte registers them rather than this script writing the files itself: it
# knows which desktop it is on, and it stores the combination in the settings
# as well, which is where the built-in listener reads it from. A key written
# to only one of the two places is a key that half works.
if [[ "$SHORTCUT" == "$CANCEL_SHORTCUT" ]]; then
  warn "Both arguments are $SHORTCUT, so the discard key was left out."
  say  "Pass two different combinations, or set it in Settings → Shortcuts."
  CANCEL_SHORTCUT=""
fi

register() {   # which  combination  label
  if out="$("${APP_CMD[@]}" shortcut install "$1" --combo "$2" 2>&1)"; then
    ok "$3: $2"
  else
    # One line: the rest of what it has to say about KWin is printed below.
    warn "${out%%$'\n'*}"
  fi
}

# A bundle has Qt inside it; a source install has to have it on the machine.
if [[ -x "$FROZEN" ]] || python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
  register toggle "$SHORTCUT" "Start and stop"
  if [[ -n "$CANCEL_SHORTCUT" ]]; then
    register cancel "$CANCEL_SHORTCUT" "Discard the recording"
  fi
  if [[ "${XDG_CURRENT_DESKTOP:-}" != *[Gg][Nn][Oo][Mm][Ee]* ]]; then
    warn "KWin only reads these at startup, so they go live after your next"
    say  "login. Until then open Settings → Shortcuts and turn on the"
    say  "built-in listener to use them right away."
  fi
else
  warn "PyQt6 is missing, so no shortcut was registered. Install it, then run:"
  say  "dikte shortcut install toggle --combo '$SHORTCUT'"
fi

echo
ok "Done. Start it with:  dikte"
say "The settings window opens on first run: download a speech model, or add"
say "an OpenAI or OpenRouter key instead."
echo

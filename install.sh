#!/usr/bin/env bash
# Dikte installer: dependency check, launchers, KDE shortcut.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
SHORTCUT="${1:-Ctrl+Space}"

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
python3 -c 'import PyQt6.QtWidgets' 2>/dev/null || missing+=("python-pyqt6")

if ((${#missing[@]})); then
  warn "Missing: ${missing[*]}"
  say  "Ubuntu X11:    sudo apt install pulseaudio-utils xclip xdotool ffmpeg"
  say  "Arch Wayland:  sudo pacman -S --needed pipewire-audio wl-clipboard ydotool ffmpeg python-pyqt6"
  echo
else
  ok "All dependencies present"
fi

# 2. ydotoold --------------------------------------------------------------
if [[ "${XDG_SESSION_TYPE:-}" != "x11" ]] && command -v ydotool >/dev/null; then
  if systemctl --user is-active --quiet ydotool 2>/dev/null \
     || systemctl --user is-active --quiet ydotoold 2>/dev/null; then
    ok "ydotoold is running (auto-paste ready)"
  else
    warn "ydotoold is not running, auto-paste will not work"
    say  "systemctl --user enable --now ydotool"
  fi
fi

# 3. Launchers -------------------------------------------------------------
mkdir -p "$BIN_DIR" "$APP_DIR" "$AUTOSTART_DIR"
ln -sf "$DIR/dikte.py" "$BIN_DIR/dikte"
chmod +x "$DIR/dikte.py"
ok "Command installed: $BIN_DIR/dikte"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH. For fish: fish_add_path $BIN_DIR" ;;
esac

cat > "$APP_DIR/dikte.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dikte
Comment=Voice dictation: record, transcribe, clean up, paste
Exec=$PY $DIR/dikte.py
Icon=audio-input-microphone
Categories=Utility;AudioVideo;
StartupNotify=false
EOF
ok "Application menu entry added"

cat > "$AUTOSTART_DIR/dikte.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dikte
Exec=$PY $DIR/dikte.py
Icon=audio-input-microphone
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF
ok "Will start automatically on login"

# 4. KDE global shortcut ---------------------------------------------------
cat > "$APP_DIR/dikte-toggle.desktop" <<EOF
[Desktop Entry]
Exec=$PY $DIR/dikte.py toggle
Name=Dikte: start/stop recording
NoDisplay=true
StartupNotify=false
Type=Application
X-KDE-GlobalAccel-CommandShortcut=true
EOF

if [[ "${XDG_CURRENT_DESKTOP:-}" == *GNOME* || "${XDG_CURRENT_DESKTOP:-}" == *gnome* ]]; then
  ok "GNOME detected"
  say "Open Dikte Settings > Shortcut to install the global shortcut."
elif command -v kwriteconfig6 >/dev/null; then
  kwriteconfig6 --notify --file kglobalshortcutsrc \
    --group services --group dikte-toggle.desktop \
    --key _launch "$SHORTCUT"
  ok "KDE shortcut registered: $SHORTCUT"
  warn "KWin only reads this at startup, so the shortcut goes live after your"
  say  "next login. Until then open Settings → Shortcut and turn on the"
  say  "built-in listener to use it right away."
else
  warn "No supported shortcut manager found. Add the shortcut in desktop settings."
fi

echo
ok "Done. Start it with:  dikte"
say "The settings window opens on first run; add an OpenAI, Groq or OpenRouter key."
echo

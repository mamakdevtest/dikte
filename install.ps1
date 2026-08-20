# install.ps1 - Install Dikte on Windows.
#
# What it does:
#   1. Creates a Start Menu shortcut and a Startup shortcut (autostart).
#   2. Adds the project dir to the user's PATH so `python dikte.py --help` works
#      as `dikte` via a generated dikte.cmd shim in %LOCALAPPDATA%\Programs\Dikte.
#   3. Registers the global shortcuts via `python dikte.py shortcut install`.
#
# Prerequisites: Python 3.11+ on PATH, ffmpeg on PATH.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Shortcut "Ctrl+Space" -CancelShortcut "Ctrl+Esc"

param(
    [string]$Shortcut = "Ctrl+Space",
    [string]$CancelShortcut = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Ok($msg) { Write-Host "ok $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "warn $msg" -ForegroundColor Yellow }
function Say($msg) { Write-Host $msg }

$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DIR) { $DIR = (Get-Location).Path }

# Pick python
$PY = $null
foreach ($cand in @("python","python3","py")) {
    try {
        $v = & $cand -c "import sys; print(sys.version)" 2>$null
        if ($LASTEXITCODE -eq 0) { $PY = $cand; break }
    } catch {}
}
if (-not $PY) { Warn "Python not found on PATH. Install Python 3.11+ and re-run."; exit 1 }

# 1. App dir + shim -------------------------------------------------------
$BIN_DIR = Join-Path $env:LOCALAPPDATA "Programs\Dikte"
New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null
$shim = Join-Path $BIN_DIR "dikte.cmd"
$shimContent = "@echo off`r`n`"$PY`" `"$DIR\dikte.py`" %*`r`n"
Set-Content -Path $shim -Value $shimContent -Encoding Ascii
Ok "Command installed: $shim"

# Add to user PATH if missing
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
if ($userPath -split ";" | Where-Object { $_ -eq $BIN_DIR }) {
    # already there
} else {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BIN_DIR", "User")
    $env:Path = "$env:Path;$BIN_DIR"
    Ok "Added $BIN_DIR to your user PATH (restart your terminal to pick it up)."
}

# 2. Start Menu entry -----------------------------------------------------
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
if (Test-Path $startMenuDir) {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path $startMenuDir "Dikte.lnk"))
    $lnk.TargetPath = $PY
    $lnk.Arguments = "`"$DIR\dikte.py`" --gui"
    $lnk.WorkingDirectory = $DIR
    $lnk.Description = "Voice dictation: record, transcribe, clean up, paste"
    try { $lnk.IconLocation = "$DIR\icons\dikte.ico,0" } catch {}
    $lnk.Save()
    Ok "Start Menu entry added."
}

# 3. Startup (autostart) --------------------------------------------------
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
if (Test-Path $startupDir) {
    $ws2 = New-Object -ComObject WScript.Shell
    $lnk2 = $ws2.CreateShortcut((Join-Path $startupDir "Dikte.lnk"))
    $lnk2.TargetPath = $PY
    $lnk2.Arguments = "`"$DIR\dikte.py`" --gui"
    $lnk2.WorkingDirectory = $DIR
    $lnk2.Description = "Dikte (autostart)"
    try { $lnk2.IconLocation = "$DIR\icons\dikte.ico,0" } catch {}
    $lnk2.Save()
    Ok "Will start automatically on login."
} else {
    Warn "Startup folder not found; skipping autostart."
}

# 4. Global shortcuts -----------------------------------------------------
if ($Shortcut -and $CancelShortcut -and $Shortcut -eq $CancelShortcut) {
    Warn "Both arguments are $Shortcut, so the discard key was left out."
    Say  "Pass two different combinations, or set it in Settings -> Shortcuts."
    $CancelShortcut = ""
}

function Register-Shortcut($which, $combo, $label) {
    if (-not $combo) { return }
    try {
        $out = & $PY "$DIR\dikte.py" shortcut install $which --combo $combo 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { Ok "${label}: $combo" }
        else { Warn (($out -split "`n")[0].Trim()) }
    } catch {
        Warn "Could not register ${label}: $_"
    }
}

# Check PyQt6 available before trying (same guard as install.sh)
try { & $PY -c "import PyQt6.QtWidgets" 2>$null; $hasQt = ($LASTEXITCODE -eq 0) } catch { $hasQt = $false }

if ($hasQt) {
    Register-Shortcut "toggle" $Shortcut "Start/stop recording"
    if ($CancelShortcut) { Register-Shortcut "cancel" $CancelShortcut "Discard the recording" }
    # Optional extra shortcuts when passed as env or left for Settings
}

# 5. ffmpeg check ---------------------------------------------------------
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Warn "ffmpeg not found on PATH. Install it with: winget install Gyan.FFmpeg"
    Say  "Then restart Dikte so it can find the microphone."
}

Ok "Done. Start it with:  dikte  (or from the Start Menu)"

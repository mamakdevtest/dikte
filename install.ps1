# install.ps1 - Install Dikte on Windows.
#
# What it does:
#   1. Registers Dikte in Windows Apps & Features (Programs and Features),
#      with an UninstallString that runs a copy of uninstall.ps1 kept in the
#      install dir (so uninstall keeps working if this checkout moves), and a
#      Start Menu shortcut plus a Startup (autostart) shortcut.
#   2. Adds the project dir to the user's PATH so `python dikte.py --help` works
#      as `dikte` via a generated dikte.cmd shim in %LOCALAPPDATA%\Programs\Dikte.
#   3. Registers the global shortcuts via `python dikte.py shortcut install`.
#   4. Launches the GUI windowlessly (pythonw) so no console window appears.
#
# Safe to run again to repair or update an existing install: every step
# overwrites or no-ops, nothing double-applies.
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
$DIR = (Resolve-Path $DIR).Path

# Display metadata. Kept minimal and reliable: no remote version lookup, so the
# recorded version is local-only and never blocks a reinstall.
$APP_GUID  = "Dikte"
$DISPLAY_NAME = "Dikte"
$PUBLISHER = "Mamak Studio"
$VERSION   = "1.0.0"
$ICON_PATH = Join-Path $DIR "icons\dikte.ico"

# Pick python: a console one for the `dikte` shim and CLI, and a windowless one
# (pythonw / pyw) for the GUI so start-up does not flash a console.
$PY       = $null   # interpreter command for console/the `dikte` shim + CLI
$PY_VER   = @()     # version selectors to pass when calling $PY (e.g. @("-3"))
$GUI_PY   = $null   # interpreter command that launches the GUI windowlessly
$GUI_VER  = @()     # version selectors for $GUI_PY
$PY_BIN   = $null   # full python.exe path (resolved to find pythonw / pyw)

# Resolve an interpreter. `py` needs `-3` as a separate argument, so the launcher
# and version selector are kept apart: the command stays a single token so the
# call operator can find it, and the version flag is passed as its own argument.
function Resolve-Python([string]$cand) {
    if (_try $cand) {
        $script:PY    = $cand
        $script:PY_VER = @()
        return $true
    }
    if ($cand -eq "py" -and (_try "py" "-3")) {
        $script:PY    = "py"
        $script:PY_VER = @("-3")
        return $true
    }
    return $false
}

function _try([string]$exe, [string[]]$args) {
    try {
        $all = @($args) + @("-c", "import sys; print(sys.version)")
        $v = & $exe @all 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

# 1. Locate interpreters ---------------------------------------------------
# Prefer a full pair. The official python.org installer drops python.exe and
# pythonw.exe together inside the install dir, but only python.exe is on PATH
# by default, so resolve python first, then ask it where pythonw lives.
foreach ($cand in @("python","python3","py")) {
    if (Resolve-Python $cand) {
        # Where is the python EXE? Only for python/py.exe launchers that give a path.
        if ($cand -eq "python" -or $cand -eq "python3") {
            $exe = (Get-Command $cand -ErrorAction SilentlyContinue).Source
            if ($exe) { $PY_BIN = $exe }
        } elseif ($cand -eq "py") {
            # Ask the py launcher which actual python.exe it would run.
            try {
                $pyPath = & $cand @($PY_VER) -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $pyPath) { $PY_BIN = ($pyPath | Select-Object -Last 1).Trim() }
            } catch {}
        }
        break
    }
}
if (-not $PY) { Warn "Python not found on PATH. Install Python 3.11+ and re-run."; exit 1 }

# A pythonw.exe beside python.exe is the normal windowless interpreter.
$GUI_PY = $null
if ($PY_BIN) {
    $w = Join-Path (Split-Path -Parent $PY_BIN) "pythonw.exe"
    if (Test-Path $w) { $GUI_PY = $w; $GUI_VER = @() }
}
# Fall back to `pyw -3` (the windowless half of the launcher).
if (-not $GUI_PY) {
    if (_try "pyw") { $script:GUI_PY = "pyw"; $script:GUI_VER = @() }
    elseif (_try "pyw" "-3") { $script:GUI_PY = "pyw"; $script:GUI_VER = @("-3") }
}
# Last resort: the regular interpreter. The GUI will still work; it just shows
# a console while it runs.
if (-not $GUI_PY) { $GUI_PY = $PY; $GUI_VER = @($PY_VER); Warn "pythonw not found; the GUI may show a console window." }

# 2. App dir + shim -------------------------------------------------------
$BIN_DIR = Join-Path $env:LOCALAPPDATA "Programs\Dikte"
New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null
$shim = Join-Path $BIN_DIR "dikte.cmd"
$shimContent = "@echo off`r`n$PY $(($PY_VER -join ' ')) `"$DIR\dikte.py`" %*`r`n"
Set-Content -Path $shim -Value $shimContent -Encoding Ascii
Ok "Command installed: $shim"

# Keep a copy of the uninstaller next to the install: the Apps & Features
# entry points at the copy, so uninstall keeps working if this checkout moves
# or disappears.
Copy-Item -Path (Join-Path $DIR "uninstall.ps1") -Destination $BIN_DIR -Force
Ok "Uninstaller copied to: $(Join-Path $BIN_DIR 'uninstall.ps1')"

# Add to user PATH if missing (install/uninstall stay symmetric).
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
if ($userPath -split ";" | Where-Object { $_ -eq $BIN_DIR }) {
    # already there
} else {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BIN_DIR", "User")
    $env:Path = "$env:Path;$BIN_DIR"
    Ok "Added $BIN_DIR to your user PATH (restart your terminal to pick it up)."
}

# One helper for shortcuts that launch the GUI windowlessly.
$ws = New-Object -ComObject WScript.Shell
function New-GuiShortcut([string]$path, [string]$desc) {
    $lnk = $ws.CreateShortcut($path)
    # $GUI_PY is a bare executable ("pythonw", "pyw", "python"...). WScript.Shell
    # cannot take a prepended call operator, and the version selector (e.g. -3)
    # must be a CLI argument for pyw, so both parts are passed explicitly.
    $lnk.TargetPath = $GUI_PY
    $lnk.Arguments = @($GUI_VER) + @("`"$DIR\dikte.py`" --gui") -join ' '
    $lnk.WorkingDirectory = $DIR
    $lnk.Description = $desc
    if (Test-Path $ICON_PATH) { try { $lnk.IconLocation = "$ICON_PATH,0" } catch {} }
    $lnk.Save()
}

# 3. Start Menu entry -----------------------------------------------------
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
if (Test-Path $startMenuDir) {
    New-GuiShortcut (Join-Path $startMenuDir "Dikte.lnk") \
        "Voice dictation: record, transcribe, clean up, paste" | Out-Null
    Ok "Start Menu entry added."
}

# 4. Startup (autostart) --------------------------------------------------
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
if (Test-Path $startupDir) {
    New-GuiShortcut (Join-Path $startupDir "Dikte.lnk") "Dikte (autostart)" | Out-Null
    Ok "Will start automatically on login."
} else {
    Warn "Startup folder not found; skipping autostart."
}

# 5. Global shortcuts -----------------------------------------------------
if ($Shortcut -and $CancelShortcut -and $Shortcut -eq $CancelShortcut) {
    Warn "Both arguments are $Shortcut, so the discard key was left out."
    Say  "Pass two different combinations, or set it in Settings -> Shortcuts."
    $CancelShortcut = ""
}

function Register-Shortcut($which, $combo, $label) {
    if (-not $combo) { return }
    try {
        $out = & $PY @($PY_VER) "$DIR\dikte.py" shortcut install $which --combo $combo 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { Ok "${label}: $combo" }
        else { Warn (($out -split "`n")[0].Trim()) }
    } catch {
        Warn "Could not register ${label}: $_"
    }
}

# Check PyQt6 available before trying (same guard as install.sh)
try { & $PY @($PY_VER) -c "import PyQt6.QtWidgets" 2>$null; $hasQt = ($LASTEXITCODE -eq 0) } catch { $hasQt = $false }

if ($hasQt) {
    Register-Shortcut "toggle" $Shortcut "Start/stop recording"
    if ($CancelShortcut) { Register-Shortcut "cancel" $CancelShortcut "Discard the recording" }
}

# 6. Apps & Features / uninstall registration -----------------------------
$unreg = Join-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" $APP_GUID
$uninst = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$BIN_DIR\uninstall.ps1`""
New-Item -Path $unreg -Force | Out-Null
Set-ItemProperty $unreg "DisplayName"    $DISPLAY_NAME
Set-ItemProperty $unreg "DisplayVersion" $VERSION
Set-ItemProperty $unreg "Publisher"      $PUBLISHER
Set-ItemProperty $unreg "InstallLocation" $DIR
Set-ItemProperty $unreg "DisplayIcon"    "$ICON_PATH,0"
Set-ItemProperty $unreg "UninstallString" $uninst
Set-ItemProperty $unreg "EstimatedSize"  0x1000
Set-ItemProperty $unreg "NoModify"       1
Set-ItemProperty $unreg "NoRepair"       1
Ok "Registered in Settings > Apps (with an uninstall entry)."

# 7. ffmpeg check ---------------------------------------------------------
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Warn "ffmpeg not found on PATH. Install it with: winget install Gyan.FFmpeg"
    Say  "Then restart Dikte so it can find the microphone."
}

Ok "Done. Start it with:  dikte  (or from the Start Menu)"
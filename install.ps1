# install.ps1 - Install Dikte on Windows.
#
# What it does:
#   1. Registers Dikte in Windows Apps & Features (Programs and Features),
#      with an UninstallString that runs a copy of uninstall.ps1 kept in the
#      install dir (so uninstall keeps working if this checkout moves), and a
#      Start Menu shortcut plus a Startup (autostart) shortcut.
#   2. Adds the project dir to the user's PATH so `python dikte.py --help` works
#      as `dikte` via a generated dikte.cmd shim in %LOCALAPPDATA%\Programs\Dikte.
#   3. Ensures PyQt6 is installed (pip install PyQt6) when missing.
#   4. Registers the global shortcuts via `python dikte.py shortcut install`.
#   5. Launches the GUI windowlessly (pythonw) so no console window appears.
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
function Info($msg) { Write-Host "info $msg" -ForegroundColor Cyan }

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

function _try_version([string]$exe, [string[]]$args) {
    try {
        $all = @($args) + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        $out = & $exe @all 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        $ver = ($out | Select-Object -Last 1).Trim()
        # Reject 0-byte Store shim that prints nothing or errors
        if (-not $ver -or $ver -notmatch '^\d+\.\d+') { return $null }
        $parts = $ver.Split('.')
        $maj = [int]$parts[0]; $min = [int]$parts[1]
        if ($maj -lt 3 -or ($maj -eq 3 -and $min -lt 11)) { return $null }
        return $ver
    } catch { return $null }
}

# 1. Locate interpreters ---------------------------------------------------
# Strategy: first try PATH (python, python3, py), then scan common install
# locations and registry so that a Store shim or a missing PATH entry does not
# hide a perfectly good Python under %LOCALAPPDATA%\Programs\Python.
$found = $false
foreach ($cand in @("python","python3","py")) {
    if (Resolve-Python $cand) {
        $ver = _try_version $cand @($PY_VER)
        if ($ver) {
            $found = $true
            break
        } else {
            # Shim found but unusable (e.g. Store stub without Python) -- keep searching
            $script:PY = $null; $script:PY_VER = @()
        }
    }
}
if (-not $found) {
    # Scan filesystem locations that the official installer uses.
    $candidates = @()
    $candidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path "$env:ProgramFiles\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path "${env:ProgramFiles(x86)}\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path "C:\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    # Registry (per-user and per-machine) for python.org and Store builds
    foreach ($root in @("HKCU:\Software\Python","HKLM:\Software\Python")) {
        try {
            if (Test-Path $root) {
                Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
                    try {
                        $ip = (Get-ItemProperty "$($_.PSPath)\InstallPath" -ErrorAction SilentlyContinue)."ExecutablePath"
                        if (-not $ip) { $ip = Join-Path (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).InstallPath "python.exe" }
                        if ($ip -and (Test-Path $ip)) { $candidates += $ip }
                    } catch {}
                }
            }
            # Wow6432Node
            $wow = $root -replace "Software\\Python","Software\Wow6432Node\Python"
            if (Test-Path $wow) {
                Get-ChildItem $wow -ErrorAction SilentlyContinue | ForEach-Object {
                    try {
                        $ip = (Get-ItemProperty "$($_.PSPath)\InstallPath" -ErrorAction SilentlyContinue)."ExecutablePath"
                        if ($ip -and (Test-Path $ip)) { $candidates += $ip }
                    } catch {}
                }
            }
        } catch {}
    }
    # Pick newest version first
    $candidates = $candidates | Sort-Object -Unique | Where-Object { $_ -and (Test-Path $_) }
    $best = $null; $bestVer = $null
    foreach ($path in $candidates) {
        try {
            $v = & $path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
            if ($LASTEXITCODE -ne 0) { continue }
            $verStr = ($v | Select-Object -Last 1).Trim()
            if ($verStr -match '^(\d+)\.(\d+)\.(\d+)') {
                $maj=[int]$Matches[1]; $min=[int]$Matches[2]
                if ($maj -lt 3 -or ($maj -eq 3 -and $min -lt 11)) { continue }
                if (-not $bestVer -or ([version]$verStr -gt [version]$bestVer)) {
                    $bestVer = $verStr; $best = $path
                }
            }
        } catch {}
    }
    if ($best) {
        $script:PY = $best; $script:PY_VER = @(); $found = $true
        Info "Found Python $bestVer at $best"
    }
}
if (-not $found -or -not $PY) { Warn "Python not found on PATH. Install Python 3.11+ from https://www.python.org/downloads/ and re-run."; Warn "Tried: python, python3, py, and common install locations."; exit 1 }

# Verify version >= 3.11
$verCheck = _try_version $PY @($PY_VER)
if (-not $verCheck) {
    Warn "Python at $PY reports version '$verCheck' but 3.11+ is required."; exit 1
}
Info "Using Python $verCheck ($PY)"

# Resolve PY_BIN: the real python.exe path (needed to find pythonw.exe beside it).
try {
    $probe = & $PY @($PY_VER) -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { $PY_BIN = ($probe | Select-Object -Last 1).Trim() }
} catch {}
if (-not $PY_BIN -and $PY -ne "py" -and $PY -ne "pyw") {
    try { $PY_BIN = (Get-Command $PY -ErrorAction SilentlyContinue).Source } catch {}
}
# If PY is a full path, use it directly
if (-not $PY_BIN -and (Test-Path $PY -ErrorAction SilentlyContinue)) { $PY_BIN = (Resolve-Path $PY -ErrorAction SilentlyContinue).Path }

# A pythonw.exe beside python.exe is the normal windowless interpreter.
$GUI_PY = $null
if ($PY_BIN -and (Test-Path $PY_BIN)) {
    $w = Join-Path (Split-Path -Parent $PY_BIN) "pythonw.exe"
    if (Test-Path $w) { $GUI_PY = $w; $GUI_VER = @() }
    else {
        # Some Store installs use pythonw in same dir but under WindowsApps alias
        $w2 = $PY_BIN -replace 'python\.exe$','pythonw.exe'
        if (Test-Path $w2) { $GUI_PY = $w2; $GUI_VER = @() }
    }
}
# Fall back to `pyw -3` (the windowless half of the launcher).
if (-not $GUI_PY) {
    if (_try "pyw") { $script:GUI_PY = "pyw"; $script:GUI_VER = @() }
    elseif (_try "pyw" "-3") { $script:GUI_PY = "pyw"; $script:GUI_VER = @("-3") }
}
# Last resort: the regular interpreter. The GUI will still work; it just shows
# a console while it runs.
if (-not $GUI_PY) { $GUI_PY = $PY; $GUI_VER = @($PY_VER); Warn "pythonw not found; the GUI may show a console window." }
if ($GUI_PY -ne "pyw" -and $GUI_PY -ne "pythonw" -and (Test-Path $GUI_PY)) {
    Info "Windowless interpreter: $GUI_PY"
} else {
    Info "Windowless interpreter: $GUI_PY $($GUI_VER -join ' ')"
}

# 2. App dir + shim -------------------------------------------------------
$BIN_DIR = Join-Path $env:LOCALAPPDATA "Programs\Dikte"
New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null
$shim = Join-Path $BIN_DIR "dikte.cmd"
# Quote the interpreter if it contains spaces (e.g. C:\Program Files\Python...)
$pyForShim = $PY
if ($PY -match '\s' -and $PY -notmatch '^".*"$') { $pyForShim = "`"$PY`"" }
$verPart = ($PY_VER -join ' ').Trim()
if ($verPart) { $shimLine = "@echo off`r`n$pyForShim $verPart `"$DIR\dikte.py`" %*`r`n" }
else { $shimLine = "@echo off`r`n$pyForShim `"$DIR\dikte.py`" %*`r`n" }
Set-Content -Path $shim -Value $shimLine -Encoding Ascii
Ok "Command installed: $shim"

# Also ensure shim directory is quoted correctly for debugging
try {
    $probeShim = Get-Content $shim -Raw
    Info "Shim: $($probeShim.Trim())"
} catch {}

# Keep a copy of the uninstaller next to the install: the Apps & Features
# entry points at the copy, so uninstall keeps working if this checkout moves
# or disappears.
try {
    Copy-Item -Path (Join-Path $DIR "uninstall.ps1") -Destination $BIN_DIR -Force
    Ok "Uninstaller copied to: $(Join-Path $BIN_DIR 'uninstall.ps1')"
} catch {
    Warn "Could not copy uninstaller: $_"
}

# Add to user PATH if missing (install/uninstall stay symmetric).
try {
    $userPath = [Environment]::GetEnvironmentVariable("Path","User")
    if (-not $userPath) { $userPath = "" }
    $pathParts = $userPath -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
    if ($pathParts -contains $BIN_DIR) {
        # already there
    } else {
        $newPath = if ($userPath.Trim() -eq "") { $BIN_DIR } else { "$userPath;$BIN_DIR" }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        $env:Path = "$env:Path;$BIN_DIR"
        Ok "Added $BIN_DIR to your user PATH (restart your terminal to pick it up)."
    }
} catch {
    Warn "Could not update PATH: $_"
}

# One helper for shortcuts that launch the GUI windowlessly.
$ws = $null
try { $ws = New-Object -ComObject WScript.Shell -ErrorAction Stop } catch {
    Warn "WScript.Shell unavailable (com automation blocked by policy); Start Menu and Startup shortcuts will be skipped. You can still run: dikte"
    $ws = $null
}
function New-GuiShortcut([string]$path, [string]$desc) {
    if (-not $ws) { throw "WScript.Shell not available" }
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
    if ($ws) {
        try {
            New-GuiShortcut (Join-Path $startMenuDir "Dikte.lnk") "Voice dictation: record, transcribe, clean up, paste" | Out-Null
            Ok "Start Menu entry added."
        } catch {
            Warn "Could not create Start Menu shortcut: $_"
        }
    } else {
        Warn "Skipped Start Menu shortcut (WScript.Shell blocked)."
    }
}

# 4. Startup (autostart) --------------------------------------------------
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
if (Test-Path $startupDir) {
    if ($ws) {
        try {
            New-GuiShortcut (Join-Path $startupDir "Dikte.lnk") "Dikte (autostart)" | Out-Null
            Ok "Will start automatically on login."
        } catch {
            Warn "Could not create Startup shortcut: $_"
        }
    } else {
        Warn "Skipped Startup shortcut (WScript.Shell blocked)."
    }
} else {
    Warn "Startup folder not found; skipping autostart."
}

# 5. Ensure PyQt6 is installed -------------------------------------------
$hasQt = $false
try { & $PY @($PY_VER) -c "import PyQt6.QtWidgets" 2>$null; $hasQt = ($LASTEXITCODE -eq 0) } catch { $hasQt = $false }
if (-not $hasQt) {
    Info "PyQt6 not found; installing..."
    $pipArgs = @("-m","pip","install","--quiet","PyQt6")
    $installed = $false
    try {
        & $PY @($PY_VER) @pipArgs 2>&1 | Out-String | ForEach-Object { if ($_.Trim()) { Say $_.Trim() } }
        if ($LASTEXITCODE -eq 0) { $installed = $true }
    } catch {}
    if (-not $installed) {
        # Corporate pip often needs --user
        Info "Retrying with --user..."
        $pipArgsUser = @("-m","pip","install","--quiet","--user","PyQt6")
        try {
            & $PY @($PY_VER) @pipArgsUser 2>&1 | Out-String | ForEach-Object { if ($_.Trim()) { Say $_.Trim() } }
            if ($LASTEXITCODE -eq 0) { $installed = $true }
        } catch {}
    }
    if ($installed) {
        try { & $PY @($PY_VER) -c "import PyQt6.QtWidgets" 2>$null; $hasQt = ($LASTEXITCODE -eq 0) } catch { $hasQt = $false }
        if ($hasQt) { Ok "PyQt6 installed." } else { Warn "PyQt6 pip succeeded but import still fails; check VC++ Redistributable: https://aka.ms/vc14" }
    } else {
        Warn "Could not install PyQt6 automatically. Install manually:"
        Say  "  $PY -m pip install PyQt6"
        Say  "If pip is blocked by proxy, ask IT for offline wheel or try:"
        Say  "  $PY -m pip install --user PyQt6"
        Say  "Corporate proxy example: $PY -m pip install --proxy http://proxy.company:8080 PyQt6"
    }
} else {
    Info "PyQt6 already installed."
}

# 6. Global shortcuts -----------------------------------------------------
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

if ($hasQt) {
    Register-Shortcut "toggle" $Shortcut "Start/stop recording"
    if ($CancelShortcut) { Register-Shortcut "cancel" $CancelShortcut "Discard the recording" }
} else {
    Warn "Skipped shortcut registration (PyQt6 missing)."
}

# 7. Apps & Features / uninstall registration -----------------------------
try {
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
} catch {
    Warn "Could not register uninstall entry (registry blocked by policy): $_"
}

# 8. ffmpeg check ---------------------------------------------------------
$ffmpegFound = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -ne $null
if (-not $ffmpegFound) {
    Warn "ffmpeg not found on PATH. Trying winget..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            Info "Installing ffmpeg via winget (Gyan.FFmpeg)..."
            & winget install --silent --accept-package-agreements --accept-source-agreements Gyan.FFmpeg 2>&1 | Out-String | ForEach-Object { if ($_.Trim()) { Say $_.Trim() } }
            $ffmpegFound = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -ne $null
            if ($ffmpegFound) { Ok "ffmpeg installed." } else { Warn "winget finished but ffmpeg still not on PATH; restart terminal or install manually: winget install Gyan.FFmpeg" }
        } catch {
            Warn "winget install failed (may be blocked by policy): $_"
            Say  "Install manually: winget install Gyan.FFmpeg"
        }
    } else {
        Warn "ffmpeg not found on PATH. Install it with: winget install Gyan.FFmpeg"
        Say  "Or download from https://ffmpeg.org and add its bin folder to PATH."
        Say  "Then restart Dikte so it can find the microphone."
    }
} else {
    Info "ffmpeg found."
}

# 9. Launch GUI -----------------------------------------------------------
if ($hasQt) {
    try {
        $guiArgs = @($GUI_VER) + @("`"$DIR\dikte.py`"", "--gui")
        # Use Start-Process so the installer can exit while Dikte stays running.
        # WindowStyle Hidden hides the console when falling back to python.exe.
        $style = if ($GUI_PY -like "*pythonw.exe" -or $GUI_PY -eq "pyw") { "Hidden" } else { "Hidden" }
        # Build argument string correctly: join with spaces, already quoted.
        $argStr = ($guiArgs -join ' ')
        Info "Launching Dikte..."
        Start-Process -FilePath $GUI_PY -ArgumentList $argStr -WorkingDirectory $DIR -WindowStyle Hidden -ErrorAction Stop | Out-Null
        Ok "Dikte started. Look for its tray icon near the clock."
        Say  "If you don't see it, run: dikte doctor"
    } catch {
        Warn "Could not launch GUI automatically: $_"
        Say  "Start it manually: dikte"
        Say  "Or: $GUI_PY $($GUI_VER -join ' ') `"$DIR\dikte.py`" --gui"
    }
} else {
    Warn "GUI not launched (PyQt6 missing). Fix PyQt6 then run: dikte"
}

Ok "Done. Start it with:  dikte  (or from the Start Menu)"
Say  "Troubleshoot: dikte doctor"

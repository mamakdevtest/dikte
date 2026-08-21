# uninstall.ps1 - Remove Dikte's Windows install artefacts (not the source dir).
#
# Takes back what install.ps1 put down, and nothing else unless asked. Your
# settings and dictations survive a plain run; --purge is the word that deletes
# them, mirroring uninstall.sh.
#
# Idempotent: running it again, or running it when parts are only half there,
# reports each missing piece and does not fail destructively.

param(
    [switch]$Purge
)

$ErrorActionPreference = "SilentlyContinue"
Set-StrictMode -Version Latest

function Say($m)  { Write-Host $m }
function Ok($m)   { Write-Host "ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host "warn $m" -ForegroundColor Yellow }
function Gone($m) { Write-Host "· $m" }

$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DIR) { $DIR = (Get-Location).Path }

$APP_GUID  = "Dikte"
$BIN_DIR   = Join-Path $env:LOCALAPPDATA "Programs\Dikte"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Dikte.lnk"
$autostart = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\Dikte.lnk"
$configDir = Join-Path $env:APPDATA "Dikte"
$dataDir   = Join-Path $env:LOCALAPPDATA "Dikte"

# 1. The running instance --------------------------------------------------
# It holds tray icon, hotkeys and a socket; ask it to quit rather than pull the
# launchers out from under it. Non-fatal if it is not running.
$python = $null
foreach ($cand in @("python","python3","py")) {
    $probe = $cand
    if ($cand -eq "py") { $probe = "py -3" }
    try { $null = & $probe -c "pass" 2>$null; if ($LASTEXITCODE -eq 0) { $python = $probe; break } } catch {}
}

if ($python) {
    if (Get-Process | Where-Object { $_.ProcessName -match "^python(w)?$" } | Select-Object -First 1) {
        $null = & $python "$DIR\dikte.py" quit 2>$null
        Ok "Asked the running instance to quit."
    } else {
        Gone "Dikte is not running."
    }
} else {
    Warn "Python not found, so the running instance (if any) was left alone."
}

# 2. The shim and PATH -----------------------------------------------------
$shimFile = Join-Path $BIN_DIR "dikte.cmd"
if (Test-Path $shimFile) {
    Remove-Item -Force $shimFile
    Ok "Removed command shim: $shimFile"
} else {
    Gone "Command shim was not there: $shimFile"
}

# Reverse the PATH addition; leave the rest of the user PATH untouched.
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
if ($userPath) {
    $parts = @($userPath -split ';' | Where-Object { $_ -and $_ -ne $BIN_DIR })
    $newPath = $parts -join ';'
    if ($newPath -eq $userPath) {
        Gone "$BIN_DIR was not on your PATH."
    } else {
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Ok "Restored your user PATH (removed $BIN_DIR)."
    }
}

# 3. Shortcuts -------------------------------------------------------------
foreach ($lnk in @($startMenu, $autostart)) {
    if (Test-Path $lnk) {
        Remove-Item -Force $lnk
        Ok "Removed shortcut: $lnk"
    } else {
        Gone "Shortcut was not there: $lnk"
    }
}

# 4. App directory (only if we emptied it) ---------------------------------
# Keep it if the user put other things in there, and never follow a junction.
if (Test-Path $BIN_DIR) {
    $left = @(Get-ChildItem -Force $BIN_DIR -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "dikte.cmd" })
    if ($left.Count -eq 0) {
        Remove-Item -Force -Recurse $BIN_DIR
        Ok "Removed empty install dir: $BIN_DIR"
    } else {
        Warn "Left $BIN_DIR in place (it still contains other files)."
    }
} else {
    Gone "Install dir was not there: $BIN_DIR"
}

# 5. Apps & Features registration -------------------------------------------
$unreg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$APP_GUID"
if (Test-Path $unreg) {
    Remove-Item -Force -Recurse $unreg
    Ok "Removed the Settings > Apps entry."
} else {
    Gone "No Settings > Apps entry to remove."
}

# 6. Settings and dictations ------------------------------------------------
if ($Purge) {
    if (Test-Path $configDir) { Remove-Item -Force -Recurse $configDir; Ok "Deleted settings: $configDir" }
    else { Gone "Settings were not there: $configDir" }
    if (Test-Path $dataDir)   { Remove-Item -Force -Recurse $dataDir;   Ok "Deleted data: $dataDir" }
    else { Gone "Data was not there: $dataDir" }
} else {
    Say "Settings kept:   $configDir"
    Say "Data kept:       $dataDir"
    Say "Delete them too with:  powershell -ExecutionPolicy Bypass -File uninstall.ps1 -Purge"
}

Ok "Done. Source files were left untouched: $DIR"
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

# The source checkout, for talking to a running Dikte. install.ps1 records it
# as InstallLocation; read it now because step 5 removes the registry key, and
# do not rely on $DIR, which is the install dir when this runs as the copy
# Windows' uninstall UI invokes.
$srcDir = ""
$unregKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$APP_GUID"
try { $srcDir = (Get-ItemProperty $unregKey).InstallLocation } catch {}

# 1. The running instance --------------------------------------------------
# It holds tray icon, hotkeys and a socket; ask it to quit rather than pull the
# launchers out from under it. Non-fatal if it is not running.
function Probe-Python([string]$cand, [string[]]$sel) {
    try {
        $out = & $cand @sel -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $ver = ($out | Select-Object -Last 1).Trim()
        if (-not $ver -or $ver -notmatch '^\d+\.\d+') { return $false }
        $p = $ver.Split('.'); if ([int]$p[0] -lt 3 -or ([int]$p[0] -eq 3 -and [int]$p[1] -lt 11)) { return $false }
        return $true
    } catch { return $false }
}

$python = $null
$pyArgs = @()
foreach ($cand in @("python","python3")) {
    if (Probe-Python $cand @()) { $python = $cand; break }
}
# The py launcher wants an explicit version selector, which must reach it as a
# separate argument: "& 'py -3'" looks for one program literally named "py -3".
if (-not $python -and (Probe-Python "py" @("-3"))) { $python = "py"; $pyArgs = @("-3") }
# Fallback: direct file scan like install.ps1
if (-not $python) {
    $cands = @()
    $cands += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    foreach ($p in $cands) { if (Probe-Python $p @()) { $python = $p; $pyArgs=@(); break } }
}

if ($python) {
    if (Get-Process | Where-Object { $_.ProcessName -match "^python(w)?$" } | Select-Object -First 1) {
        if ($srcDir -and (Test-Path (Join-Path $srcDir "dikte.py"))) {
            $null = & $python @pyArgs (Join-Path $srcDir "dikte.py") quit 2>$null
            Ok "Asked the running instance to quit."
        } else {
            Warn "Install location unknown, so the running instance (if any) was left alone."
        }
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

# Reverse the PATH addition; leave the rest of the user PATH untouched,
# empty segments included.
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
if ($userPath) {
    $parts = $userPath -split ';'
    if ($parts -contains $BIN_DIR) {
        $newPath = (($parts | Where-Object { $_ -ne $BIN_DIR }) -join ';')
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Ok "Restored your user PATH (removed $BIN_DIR)."
    } else {
        Gone "$BIN_DIR was not on your PATH."
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
# The uninstaller's own copy goes first: pwsh keeps the script in memory, so
# deleting the file we are running usually works; if not, say so and keep it.
$selfCopy = Join-Path $BIN_DIR "uninstall.ps1"
$selfGone = $true
if (Test-Path $selfCopy) {
    try {
        Remove-Item -Force $selfCopy
        Ok "Removed uninstaller copy: $selfCopy"
    } catch {
        $selfGone = $false
        Warn "Could not remove the running uninstaller copy: $selfCopy"
    }
}
if (Test-Path $BIN_DIR) {
    $left = @(Get-ChildItem -Force $BIN_DIR -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "dikte.cmd" -and $_.Name -ne "uninstall.ps1" })
    if ($left.Count -eq 0 -and $selfGone) {
        Remove-Item -Force -Recurse $BIN_DIR
        Ok "Removed empty install dir: $BIN_DIR"
    } else {
        Warn "Left $BIN_DIR in place (it still contains other files)."
    }
} else {
    Gone "Install dir was not there: $BIN_DIR"
}

# 5. Apps & Features registration -------------------------------------------
if (Test-Path $unregKey) {
    Remove-Item -Force -Recurse $unregKey
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

$sourceLeft = if ($srcDir) { $srcDir } else { $DIR }
Ok "Done. Source files were left untouched: $sourceLeft"
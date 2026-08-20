# uninstall.ps1 - Remove Dikte's Windows install artefacts (not the source dir).
param()
$ErrorActionPreference = "SilentlyContinue"
Set-StrictMode -Version Latest
function Say($m){ Write-Host $m }
$BIN_DIR = Join-Path $env:LOCALAPPDATA "Programs\Dikte"
Remove-Item -Force (Join-Path $BIN_DIR "dikte.cmd") 2>$null
# Keep the dir if user put other things there.
if ((Get-ChildItem $BIN_DIR -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Remove-Item -Force -Recurse $BIN_DIR 2>$null
}
$start = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Dikte.lnk"
Remove-Item -Force $start 2>$null
$auto  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\Dikte.lnk"
Remove-Item -Force $auto 2>$null
Say "ok Removed Dikte shortcuts and shim (source files kept)."

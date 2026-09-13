# PyInstaller spec for Dikte — one definition of what the frozen bundle contains.
#
# Licence: GPL-3.0-only (Q1, docs/ai/DECISIONS.md). A frozen build is GPL-3.0 object
# code, so whoever hands one out provides the Corresponding Source for it (§6). Freezing
# is not in tension with that: PyQt6's terms and Dikte's now say the same thing.
#
# One executable, not two. `dikte.py` is both the command line (verbs: record, doctor,
# transcribe, meeting…) and the window (no verb, or --gui), so one binary answers both.
# Windows wants a console-less twin for the startup entry — that is T5.4, and it belongs
# there rather than here, because only Windows has the problem.
#
# What has to travel with the code: the application reads three asset trees from disk at
# runtime and none of them is a Python module.
#   docs/fonts/*.ttf          the six faces ui/theme.py hands to QFontDatabase
#   assets/fonts/icons/*.svg  the 56 icons ui/icons.py renders
#   icons/dikte.{ico,png}     the window and tray icon in dikte.py
# The first living under `docs/` while the second lives under `assets/` is a packaging
# smell that predates this phase (ui/icons.py already searches four candidate paths for
# it). Both are bundled where they are: moving them is a refactor with nothing to do with
# packaging, and a refactor inside a packaging change is how a bundle breaks.

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "docs", "fonts"), "docs/fonts"),
    (os.path.join(ROOT, "assets", "fonts"), "assets/fonts"),
    (os.path.join(ROOT, "assets", "fonts", "icons"), "assets/fonts/icons"),
    (os.path.join(ROOT, "icons"), "icons"),
]

# Qt ships far more than a settings window with SVG icons needs, and PyInstaller's Qt
# hook is generous. These stay out. The list is deliberately conservative: a wrong
# exclude fails at runtime, on a machine nobody is testing on, which is the opposite of
# what a bundle is for.
excludes = [
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebChannel",
    "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuickWidgets", "PyQt6.QtQuick3D",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtBluetooth",
    "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSensors", "PyQt6.QtSerialPort",
    "PyQt6.QtSql", "PyQt6.QtTest", "PyQt6.QtWebSockets", "PyQt6.QtDesigner",
    "PyQt6.QtHelp", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
    "PyQt6.Qt3DCore", "PyQt6.Qt3DRender", "PyQt6.QtSpatialAudio",
    "PyQt6.QtTextToSpeech", "PyQt6.QtRemoteObjects", "PyQt6.QtStateMachine",
    "PyQt6.QtGraphs", "PyQt6.QtScxml", "PyQt6.QtHttpServer", "PyQt6.QtNetworkAuth",
    # the repository's own trees, which are not the application
    "tests", "tools", "design", "graphify",
]

a = Analysis(
    [os.path.join(ROOT, "dikte.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="dikte",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "icons", "dikte.ico") if os.path.exists(
        os.path.join(ROOT, "icons", "dikte.ico")) else None,
)

# Windows gets a second, console-less executable, because Windows is the platform where a
# console is a *visible* thing that flashes on screen. The Startup entry and the Start
# Menu shortcut point at this one; a terminal keeps using `dikte`, which still has its
# console for the CLI. Other platforms have no equivalent problem, and a second executable
# carries its own copy of the module archive, so they do not pay for it.
twin = None
if sys.platform == "win32":
    twin = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="diktew",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=os.path.join(ROOT, "icons", "dikte.ico"),
    )

coll = COLLECT(
    *(c for c in (exe, twin) if c is not None),
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="dikte",
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821  (PyInstaller injects BUNDLE)
        coll,
        name="dikte.app",
        icon=os.path.join(ROOT, "icons", "dikte.ico"),
        bundle_identifier="app.dikte",
        info_plist={
            # Recording is the application's whole purpose; macOS refuses microphone
            # access without this string, and the refusal looks like a Dikte bug.
            "NSMicrophoneUsageDescription":
                "Dikte records your voice to transcribe it on this computer.",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
        },
    )

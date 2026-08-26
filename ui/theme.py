"""Design tokens and the QSS generator for Dikte's settings UI.

The exported prototype (`design/Dikte-Yeniden-Tasarım-Prototipi/assets/dikte.css`)
is the visual contract. Its ``:root`` and ``[data-theme=light]`` variables are
frozen here as plain dictionaries, one per theme, and ``stylesheet()`` turns one
into a single QSS string. There is exactly one QSS string per theme; switching
the theme re-applies it to the whole application.
"""

import os
import pathlib
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect

# The palette is the prototype's CSS variables, keyed by the same names the
# stylesheet uses, so the QSS below reads almost like the source CSS.
DARK = {
    "canvas": "#11191B",
    "sidebar": "#162225",
    "surface": "#1B292B",
    "surface2": "#233537",
    "field": "#142123",
    "border": "#314548",
    "borderStrong": "#4A6261",
    "fg": "#E7F0EC",
    "fg2": "#A8BCB5",
    "fg3": "#7C918A",
    "terra": "#E08A72",
    "terraDeep": "#C66F5D",
    "sage": "#8FAF9E",
    "sageDark": "#A8C7B5",
    "ok": "#75C59B",
    "warn": "#D8B870",
    "err": "#DF8582",
    "info": "#82B9CE",
    "inkBtn": "#0C1315",
    "onInk": "#F2F7F4",
}

LIGHT = {
    "canvas": "#F1F6F3",
    "sidebar": "#E5EEE9",
    "surface": "#FBFDFC",
    "surface2": "#EDF4F0",
    "field": "#FFFFFF",
    "border": "#CBD9D2",
    "borderStrong": "#AFC4B8",
    "fg": "#17211F",
    "fg2": "#536963",
    "fg3": "#71847E",
    "terra": "#C96D59",
    "terraDeep": "#A85544",
    "sage": "#B7CCBD",
    "sageDark": "#3F6B5A",
    "ok": "#2F7D5B",
    "warn": "#A87924",
    "err": "#B94B4B",
    "info": "#2B7390",
    "inkBtn": "#17211F",
    "onInk": "#F2F7F4",
}

TOKENS = {"dark": DARK, "light": LIGHT}

# Radii and the fixed geometry the prototype pins in px. Kept as integers so a
# future spacing helper can read them without parsing QSS.
RADII = {"r1": 4, "r2": 6, "r3": 8, "r4": 12}

# Shadows from dikte.css --sh-1/2/3 per theme (used via QGraphicsDropShadowEffect, not QSS)
SHADOWS = {
    "dark": {
        "sh1": "0 1px 2px rgba(20,20,18,.05)",
        "sh2": "0 1px 2px rgba(20,20,18,.06),0 6px 20px rgba(20,20,18,.09)",
        "sh3": "0 2px 6px rgba(20,20,18,.08),0 18px 48px rgba(20,20,18,.16)",
    },
    "light": {
        "sh1": "0 1px 2px rgba(19,42,35,.05)",
        "sh2": "0 1px 2px rgba(19,42,35,.06),0 6px 20px rgba(19,42,35,.09)",
        "sh3": "0 2px 6px rgba(19,42,35,.08),0 18px 48px rgba(19,42,35,.14)",
    },
}

_current = "dark"
_fonts_loaded = False


def _load_fonts():
    global _fonts_loaded
    if _fonts_loaded:
        return
    _fonts_loaded = True
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # docs/fonts contains Inter + JetBrains Mono ttf downloaded from Google Fonts
    candidates = [
        os.path.join(base, "docs", "fonts", "Inter-400.ttf"),
        os.path.join(base, "docs", "fonts", "Inter-500.ttf"),
        os.path.join(base, "docs", "fonts", "Inter-600.ttf"),
        os.path.join(base, "docs", "fonts", "Inter-700.ttf"),
        os.path.join(base, "docs", "fonts", "JetBrainsMono-400.ttf"),
        os.path.join(base, "docs", "fonts", "JetBrainsMono-500.ttf"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            QFontDatabase.addApplicationFont(p)
    # Fallback: also try assets if vendored differently
    extra = os.path.join(base, "assets", "fonts")
    if os.path.isdir(extra):
        for fname in os.listdir(extra):
            if fname.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(extra, fname))


_chevron_cache = {}


def _chevron_path(theme_name):
    """Ensure a 14px chevron PNG exists for the theme and return its forward-slash URL."""
    # Use DATA_DIR when possible, else temp dir; ensure the file is recreated if palette changes.
    if theme_name in _chevron_cache:
        path = _chevron_cache[theme_name]
        if os.path.isfile(path):
            return path.replace("\\", "/")
    try:
        from config import DATA_DIR as _DATA_DIR
        base_dir = pathlib.Path(_DATA_DIR)
        base_dir.mkdir(parents=True, exist_ok=True)
        path = str(base_dir / f"dikte-chevron-{theme_name}.png")
    except Exception:
        try:
            base_dir = pathlib.Path(tempfile.gettempdir()) / "dikte"
            base_dir.mkdir(parents=True, exist_ok=True)
            path = str(base_dir / f"dikte-chevron-{theme_name}.png")
        except Exception:
            return ""
    try:
        # Generate pixmap via icons; requires QApplication
        app = QApplication.instance()
        if app is None:
            return ""
        from . import icons as _icons
        c = TOKENS.get(theme_name, DARK)
        color = c.get("fg2", "#A8BCB5")
        # For disabled state we use fg3
        pm = _icons.pixmap("chevD", 14, color)
        if pm.isNull():
            return ""
        pm.save(path, "PNG")
        _chevron_cache[theme_name] = path
        return path.replace("\\", "/")
    except Exception:
        return ""


def _chevron_disabled_path(theme_name):
    key = f"{theme_name}-disabled"
    if key in _chevron_cache and os.path.isfile(_chevron_cache[key]):
        return _chevron_cache[key].replace("\\", "/")
    try:
        from config import DATA_DIR as _DATA_DIR
        base_dir = pathlib.Path(_DATA_DIR)
        base_dir.mkdir(parents=True, exist_ok=True)
        path = str(base_dir / f"dikte-chevron-{theme_name}-disabled.png")
    except Exception:
        base_dir = pathlib.Path(tempfile.gettempdir()) / "dikte"
        base_dir.mkdir(parents=True, exist_ok=True)
        path = str(base_dir / f"dikte-chevron-{theme_name}-disabled.png")
    try:
        app = QApplication.instance()
        if app is None:
            return ""
        from . import icons as _icons
        c = TOKENS.get(theme_name, DARK)
        color = c.get("fg3", "#7C918A")
        pm = _icons.pixmap("chevD", 14, color)
        if pm.isNull():
            return ""
        pm.save(path, "PNG")
        _chevron_cache[key] = path
        return path.replace("\\", "/")
    except Exception:
        return ""


def current():
    return _current


def palette(theme=None):
    """The colour tokens of a theme, defaulting to the one in use."""
    return TOKENS[theme or _current]


def _mix(hex_a, hex_b, share_a):
    """A hex colour that is `share_a` parts of a, the rest b (0.0..1.0)."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(
        round(a[i] * share_a + b[i] * (1 - share_a)) for i in range(3)
    )


def _rgba(hex_color, alpha):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def shadow_effect(level=1, theme=None):
    """Create a QGraphicsDropShadowEffect matching CSS --sh-1/2/3."""
    c = palette(theme)
    eff = QGraphicsDropShadowEffect()
    if level >= 3:
        eff.setBlurRadius(48)
        eff.setOffset(0, 18)
        # use borderStrong with low opacity to approximate
        col = QColor(c["borderStrong"])
        col.setAlpha(36)
        eff.setColor(col)
    elif level == 2:
        eff.setBlurRadius(20)
        eff.setOffset(0, 6)
        col = QColor(c["borderStrong"])
        col.setAlpha(22)
        eff.setColor(col)
    else:
        eff.setBlurRadius(6)
        eff.setOffset(0, 1)
        col = QColor(c["borderStrong"])
        col.setAlpha(18)
        eff.setColor(col)
    return eff


def stylesheet(theme=None):
    """The whole QSS for one theme, as a single string."""
    c = palette(theme)
    border_soft = _mix(c["border"], c["canvas"], 0.62)
    border_row = _mix(c["border"], c["canvas"], 0.52)
    border_panel = _mix(c["border"], c["surface"], 0.75)
    field_mix = _mix(c["field"], c["surface"], 0.92)
    # Chevron for QComboBox dropdown — generated per-theme to ensure contrast
    _theme_name = theme if theme in TOKENS else _current
    chev = _chevron_path(_theme_name)
    chev_disabled = _chevron_disabled_path(_theme_name)
    if chev:
        chev_rule = f'QComboBox::down-arrow {{ image: url({chev}); width: 14px; height: 14px; }}'
    else:
        chev_rule = 'QComboBox::down-arrow { width: 14px; height: 14px; }'
    if chev_disabled:
        chev_disabled_rule = f'QComboBox::down-arrow:disabled {{ image: url({chev_disabled}); }}'
    else:
        chev_disabled_rule = ''
    return f"""
* {{ font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
     font-size: 13px; }}
QWidget {{ color: {c["fg"]}; background: transparent; }}
QDialog {{ background: {c["canvas"]}; }}
QWidget#sidebar {{ background: {c["sidebar"]};
                    border-right: 1px solid {border_soft}; }}
QWidget#main {{ background: {c["canvas"]}; }}

/* ---- the page stack ---------------------------------------------------- */
QTabWidget::pane {{ border: none; background: {c["canvas"]}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; padding: 6px 12px; color: {c["fg2"]}; }}
QTabBar::tab:selected {{ color: {c["fg"]}; border-bottom: 2px solid {c["sageDark"]}; }}
QTabBar::tab:hover {{ color: {c["fg"]}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ---- sidebar ----------------------------------------------------------- */
QLabel#brandName {{ font-size: 14.5px; font-weight: 700; }}
QLabel#brandSub {{ font-size: 11px; color: {c["fg3"]}; }}
QLabel#navLabel {{ font-size: 13px; font-weight: 500; color: {c["fg2"]}; }}
QPushButton#navItem {{ text-align: left; padding: 0 9px; border-radius: 6px;
                       border: none; background: transparent;
                       min-height: 32px; }}
QPushButton#navItem:hover {{ background: {_mix(c["surface"], c["sidebar"], 0.55)}; }}
QPushButton#navItem[active="true"] {{
    background: {_mix(c["sage"], c["sidebar"], 0.30)};
    border: 1px solid {_mix(c["sageDark"], c["canvas"], 0.26)}; }}
QPushButton#navItem[active="true"] QLabel#navLabel {{ color: {c["fg"]}; }}

/* ---- cards (QGroupBox doubles as the card) ----------------------------- */
QGroupBox {{
    background: {c["surface"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    margin-top: 8px;
    padding: 14px 20px 8px 20px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 16px; padding: 0 4px; color: {c["fg"]}; font-size: 13px;
}}
QFrame#card {{ background: {c["surface"]}; border: 1px solid {c["border"]};
               border-radius: 8px; }}
QFrame#panel {{ background: {_mix(c["surface2"], c["surface"], 0.55)};
               border: 1px solid {border_panel};
               border-radius: 6px; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#cardDesc {{ font-size: 12.5px; color: {c["fg2"]}; }}

/* ---- labels ------------------------------------------------------------ */
QLabel#pageTitle {{ font-size: 24px; font-weight: 600; }}
QLabel#pageSub {{ font-size: 13px; color: {c["fg2"]}; }}
QLabel#rowLabel {{ font-size: 13.5px; font-weight: 500; }}
QLabel#rowHelp {{ font-size: 12px; color: {c["fg3"]}; }}
QLabel#meta {{ font-size: 11px; color: {c["fg3"]}; }}
QLabel[mono="true"] {{ font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
                       font-size: 11.5px; }}
QLabel#kbd {{ font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
              font-size: 11.5px; color: {c["fg"]};
              background: {c["surface2"]}; border: 1px solid {c["border"]};
              border-bottom: 2px solid {c["border"]}; border-radius: 4px;
              padding: 1px 6px; }}

/* ---- dots and chips ---------------------------------------------------- */
QLabel[dot="ok"]   {{ background: {c["ok"]}; border-radius: 4px; }}
QLabel[dot="sage"] {{ background: {c["sageDark"]}; border-radius: 4px; }}
QLabel[dot="warn"] {{ background: {c["warn"]}; border-radius: 4px; }}
QLabel[dot="err"]  {{ background: {c["err"]}; border-radius: 4px; }}
QLabel[dot="info"] {{ background: {c["info"]}; border-radius: 4px; }}
QLabel[dot="idle"] {{ background: {c["fg3"]}; border-radius: 4px; }}
QLabel[dot="rec"]  {{ background: {c["terra"]}; border-radius: 4px; }}

QFrame[chip="sage"] {{ background: {_mix(c["sage"], c["surface"], 0.30)};
                       color: {c["sageDark"]}; border: 1px solid {_mix(c["sageDark"], c["canvas"], 0.22)};
                       border-radius: 11px; }}
QFrame[chip="sage"] QLabel {{ font-size: 11.5px; color: {c["sageDark"]}; }}
QFrame[chip="gray"] {{ background: {c["surface2"]}; color: {c["fg2"]};
                       border: 1px solid {c["border"]}; border-radius: 11px; }}
QFrame[chip="gray"] QLabel {{ font-size: 11.5px; color: {c["fg2"]}; }}
QFrame[chip="tan"]  {{ background: {_mix(c["warn"], c["surface"], 0.14)};
                       color: "#8A6A14"; border: 1px solid {_mix(c["warn"], c["canvas"], 0.34)};
                       border-radius: 11px; }}
QFrame[chip="tan"] QLabel {{ font-size: 11.5px; color: "#8A6A14"; }}
QFrame[chip="red"]  {{ background: {_mix(c["err"], c["surface"], 0.10)};
                       color: {c["err"]}; border: 1px solid {_mix(c["err"], c["canvas"], 0.28)};
                       border-radius: 11px; }}
QFrame[chip="red"] QLabel {{ font-size: 11.5px; color: {c["err"]}; }}
QFrame[chip="ok"]   {{ background: {_mix(c["ok"], c["surface"], 0.12)};
                       color: {c["ok"]}; border: 1px solid {_mix(c["ok"], c["canvas"], 0.28)};
                       border-radius: 11px; }}
QFrame[chip="ok"] QLabel {{ font-size: 11.5px; color: {c["ok"]}; }}

/* ---- notes ------------------------------------------------------------- */
QLabel[note="info"] {{ background: {_mix(c["info"], c["surface"], 0.07)};
                       color: {c["fg2"]}; border: 1px solid {_mix(c["info"], c["canvas"], 0.24)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="warn"] {{ background: {_mix(c["warn"], c["surface"], 0.11)};
                       color: {c["fg2"]}; border: 1px solid {_mix(c["warn"], c["canvas"], 0.38)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="err"]  {{ background: {_mix(c["err"], c["surface"], 0.07)};
                       color: {c["fg2"]}; border: 1px solid {_mix(c["err"], c["canvas"], 0.26)};
                       border-radius: 6px; padding: 8px 12px; }}
QLabel[note="ok"]   {{ background: {_mix(c["ok"], c["surface"], 0.08)};
                       color: {c["fg2"]}; border: 1px solid {_mix(c["ok"], c["canvas"], 0.26)};
                       border-radius: 6px; padding: 8px 12px; }}

/* ---- fields ------------------------------------------------------------ */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {c["field"]}; border: 1px solid {c["border"]};
    border-radius: 6px; color: {c["fg"]}; selection-background-color: {c["sage"]};
    padding: 0 10px; min-height: 30px; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover {{
    border-color: {c["borderStrong"]}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border-color: {c["borderStrong"]}; background: {c["field"]}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {c["surface2"]}; color: {c["fg3"]}; }}
QPlainTextEdit, QTextEdit {{ padding: 8px 10px; }}
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }}
{chev_rule}
{chev_disabled_rule}
QComboBox QAbstractItemView {{ background: {c["surface"]}; color: {c["fg"]};
    border: 1px solid {c["border"]}; selection-background-color: {c["surface2"]};
    selection-color: {c["fg"]}; }}
QComboBox::down-arrow:disabled {{ opacity: 0.6; }}

/* ---- buttons ----------------------------------------------------------- */
QPushButton {{ min-height: 32px; padding: 0 13px; border-radius: 6px;
               font-size: 13px; font-weight: 500; border: 1px solid transparent; }}
QPushButton[size="sm"] {{ min-height: 26px; padding: 0 9px; font-size: 12px; }}
QPushButton[variant="primary"] {{ background: {c["terraDeep"]}; color: "#FFF8F5"; }}
QPushButton[variant="primary"]:hover {{ background: {c["terra"]}; }}
QPushButton[variant="ink"] {{ background: {c["inkBtn"]}; color: {c["onInk"]}; }}
QPushButton[variant="ink"]:hover {{ background: {_mix(c["inkBtn"], c["surface2"], 0.78)}; }}
QPushButton[variant="secondary"] {{ background: {c["field"]};
    border-color: {c["border"]}; color: {c["fg"]}; }}
QPushButton[variant="secondary"]:hover {{ background: {c["surface2"]};
    border-color: {c["borderStrong"]}; }}
QPushButton[variant="ghost"] {{ color: {c["fg2"]}; }}
QPushButton[variant="ghost"]:hover {{ background: {c["surface2"]}; color: {c["fg"]}; }}
QPushButton[variant="danger"] {{ color: {c["err"]}; }}
QPushButton[variant="danger"]:hover {{ background: {_mix(c["err"], c["surface"], 0.09)}; }}
QPushButton:disabled {{ color: {c["fg3"]}; background: {c["surface2"]}; }}

/* ---- checkboxes (toggles) --------------------------------------------- */
QCheckBox[kind="toggle"] {{ spacing: 0; }}
QCheckBox[kind="toggle"]::indicator {{ width: 34px; height: 18px;
    border-radius: 9px; border: 1px solid {c["borderStrong"]};
    background: {_mix(c["borderStrong"], c["surface2"], 0.62)}; }}
QCheckBox[kind="toggle"]::indicator:checked {{
    background: {c["sageDark"]}; border-color: {c["sageDark"]}; }}
QCheckBox[kind="toggle"]::indicator:disabled {{ opacity: 0.4; }}
QCheckBox {{ color: {c["fg"]}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c["borderStrong"]};
    border-radius: 4px; background: {c["field"]}; }}
QCheckBox::indicator:checked {{ background: {c["sageDark"]};
    border-color: {c["sageDark"]}; }}

/* ---- lists ------------------------------------------------------------- */
QListWidget {{ background: {c["surface"]}; border: 1px solid {c["border"]};
    border-radius: 8px; color: {c["fg"]}; padding: 4px; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {_mix(c["sage"], c["surface"], 0.20)};
    color: {c["fg"]}; border-left: 2px solid {c["sageDark"]}; }}
QListWidget::item:hover {{ background: {_mix(c["surface2"], c["canvas"], 0.62)}; }}

/* ---- menus (tray) ------------------------------------------------------ */
QMenu {{ background: {c["surface"]}; border: 1px solid {c["border"]};
        border-radius: 8px; padding: 5px; }}
QMenu::item {{ height: 31px; padding: 0 10px 0 10px; margin: 0;
              border-radius: 6px; color: {c["fg"]}; }}
QMenu::item:selected {{ background: {c["surface2"]}; color: {c["fg"]}; }}
QMenu::item:disabled {{ color: {c["fg3"]}; }}
QMenu::separator {{ height: 1px; background: {border_row}; margin: 5px 6px; }}
QMenu::item:disabled:selected {{ background: transparent; }}
QMenu::indicator {{ width: 0px; }}

/* ---- progress ---------------------------------------------------------- */
QProgressBar {{ border: none; background: {_mix(c["borderStrong"], c["surface2"], 0.45)};
    border-radius: 6px; height: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {c["sageDark"]}; border-radius: 6px; }}

/* ---- overlay picker ---------------------------------------------------- */
QWidget#cornerPicker {{ background: {c["surface2"]}; border: 1px solid {c["border"]};
                       border-radius: 6px; }}
QPushButton[cornerCell="true"] {{ background: transparent; border: 1px solid transparent;
                                 border-radius: 6px; min-width: 44px; min-height: 34px; }}
QPushButton[cornerCell="true"]:hover {{ background: {_mix(c["sage"], c["surface"], 0.16)}; }}
QPushButton[cornerCell="true"][active="true"] {{ background: {_mix(c["sage"], c["surface"], 0.32)};
                                                  border: 1px solid {c["sageDark"]}; }}
QFrame#miniScreen {{ background: {c["surface2"]}; border: 1px solid {c["borderStrong"]};
                    border-radius: 6px; }}
QLabel#miniOv {{ background: {c["field"]}; border: 1px solid {c["border"]};
                border-radius: 6px; font-family: "JetBrains Mono", monospace; font-size: 8px; color: {c["fg"]}; }}

/* ---- misc -------------------------------------------------------------- */
QSplitter::handle {{ background: transparent; }}
QFrame#rowSeparator {{ background: {border_row}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#cardFooter {{ border-top: 1px solid {border_soft}; }}
"""


def apply(theme=None):
    """Apply a theme's QSS to the whole application and record the choice."""
    global _current
    if theme in TOKENS:
        _current = theme
    _load_fonts()
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(stylesheet(_current))
    return _current


def toggle():
    return apply("light" if _current == "dark" else "dark")

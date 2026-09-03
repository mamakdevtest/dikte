"""Theme adapter over :mod:`ui.tokens` and :mod:`ui.qss`.

The exported prototype (`design/Dikte-Yeniden-Tasarım-Prototipi/assets/dikte.css`)
is the visual contract. Token values live in ``ui/tokens.py``; the QSS engine
lives in ``ui/qss.py``. This module keeps the historic API — ``stylesheet()``,
``apply()``, ``palette()``, ``normalize()``, ``current()``, ``toggle()`` and
the ``TOKENS``/``THEMES`` keys — delegating every answer to the new engine.
"""

import os
import pathlib
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect

from . import qss as _qss
from . import tokens as _tokens

# Re-exported token tables — same keys, same dict objects as ui.tokens.
DARK = _tokens.DARK
LIGHT = _tokens.LIGHT
BLUE = _tokens.BLUE
GREEN = _tokens.GREEN
VIOLET = _tokens.VIOLET
ORANGE = _tokens.ORANGE
PINK = _tokens.PINK
TEAL = _tokens.TEAL
THEMES = _tokens.THEMES
TOKENS = _tokens.TOKENS
RADII = _tokens.RADII
SHADOWS = _tokens.SHADOWS

_current = "blue"
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
    return _qss.mix(hex_a, hex_b, share_a)


def _mix_hex(hex_a, hex_b, share_a):
    return _qss.mix(hex_a, hex_b, share_a)


def _rgba(hex_color, alpha):
    return _qss.rgba(hex_color, alpha)


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
    name = theme if theme in TOKENS else _current
    c = palette(name)
    chev = _chevron_path(name)
    chev_disabled = _chevron_disabled_path(name)
    return _qss.stylesheet(c, theme_name=name,
                           chevron=chev, chevron_disabled=chev_disabled)


def apply(theme=None):
    """Apply a colour theme's QSS to the whole application and record it."""
    global _current
    if theme is not None:
        _current = normalize(theme)
    else:
        _current = normalize(_current)
    _load_fonts()
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(stylesheet(_current))
    return _current


def toggle():
    """Cycle the six colour themes only (no dark/light)."""
    names = list(THEMES)
    current = _current if _current in names else names[0]
    index = names.index(current)
    return apply(names[(index + 1) % len(names)])


def normalize(name):
    """Map legacy dark/light (and unknowns) onto a colour theme key."""
    return _tokens.normalize(name)

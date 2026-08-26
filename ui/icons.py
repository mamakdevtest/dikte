"""The icon set, ported verbatim from the prototype's ``dikte.js`` ICONS table.

Every glyph is a 24px viewBox stroke SVG (stroke-width 1.7, round caps/joins),
the same markup the web prototype injects at ``[data-ic]``. ``icon()`` renders
one to a QIcon in memory through PyQt6.QtSvg, so no image files are needed.
"""

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_SVG_OPEN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
             'fill="none" stroke="{color}" stroke-width="1.7" '
             'stroke-linecap="round" stroke-linejoin="round">')

# The inner markup of each icon, exactly as the prototype defines it.
ICONS = {
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5V21"/>',
    "micOff": '<path d="M15 9.5V6a3 3 0 0 0-5.6-1.5"/><path d="M9 9v2a3 3 0 0 0 4.6 2.5"/><path d="M5.5 11a6.5 6.5 0 0 0 10.9 4.8"/><path d="M12 17.5V21"/><path d="m4 4 16 16"/>',
    "sliders": '<path d="M4 7.5h9"/><path d="M17.5 7.5H20"/><circle cx="15.2" cy="7.5" r="2.2"/><path d="M4 16.5h2.5"/><path d="M11 16.5h9"/><circle cx="8.7" cy="16.5" r="2.2"/>',
    "plug": '<path d="M9 3v4.5"/><path d="M15 3v4.5"/><path d="M6.5 7.5h11V11a5.5 5.5 0 0 1-11 0z"/><path d="M12 16.5V21"/>',
    "eraser": '<path d="m8 20.5-4-4a2 2 0 0 1 0-2.8l8.7-8.7a2 2 0 0 1 2.8 0l4 4a2 2 0 0 1 0 2.8l-7.2 7.2a2.4 2.4 0 0 1-1.7.7z"/><path d="m8.5 9.5 6.5 6.5"/><path d="M20.5 20.5H11"/>',
    "terminal": '<path d="m4 17 6-5-6-5"/><path d="M12 19h8"/>',
    "users": '<circle cx="9" cy="7.5" r="3.5"/><path d="M2.5 20.5v-.8a6.2 6.2 0 0 1 6.2-6.2h.6a6.2 6.2 0 0 1 6.2 6.2v.8"/><path d="M15.8 4.4a3.5 3.5 0 0 1 0 6.3"/><path d="M19.5 13.7a6.2 6.2 0 0 1 2 4.6v2.2"/>',
    "fileText": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/>',
    "fileAudio": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 15.5v-2"/><path d="M12 17v-5"/><path d="M15 15.5v-2"/>',
    "keyboard": '<rect x="3" y="6.5" width="18" height="11" rx="2"/><path d="M7 10.5h.01"/><path d="M10.5 10.5h.01"/><path d="M14 10.5h.01"/><path d="M17.5 10.5h.01"/><path d="M7 14h10"/>',
    "history": '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.4"/><path d="M3.5 3.5v5h5"/><path d="M12 8v4.3l2.7 2.7"/>',
    "pip": '<rect x="3" y="5" width="18" height="14" rx="2"/><rect x="12" y="11.5" width="6.5" height="4.5" rx="1"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20.5 20.5-4.7-4.7"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "x": '<path d="m6 6 12 12"/><path d="m18 6-12 12"/>',
    "chevD": '<path d="m6 9 6 6 6-6"/>',
    "chevR": '<path d="m9 6 6 6-6 6"/>',
    "chevL": '<path d="m15 6-6 6 6 6"/>',
    "check": '<path d="m4.5 12.5 5 5L19.5 7"/>',
    "checkC": '<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.4 4.8-5"/>',
    "xC": '<circle cx="12" cy="12" r="8.5"/><path d="m9.2 9.2 5.6 5.6"/><path d="m14.8 9.2-5.6 5.6"/>',
    "alert": '<path d="M10.3 4.2 2.9 17a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 8h.01"/><path d="M12 11.5V16"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.2a2.5 2.5 0 0 1 4.9.7c0 1.6-2.5 2.1-2.5 3.6"/><path d="M12 17h.01"/>',
    "dots": '<circle cx="5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    "trash": '<path d="M4 7h16"/><path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2"/><path d="m6.5 7 .8 12.1a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9L17.5 7"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    "folder": '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6L11 7h7.5A2.5 2.5 0 0 1 21 9.5v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16.5z"/>',
    "refresh": '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1l2.6 2.5"/><path d="M20.5 3.5v5h-5"/>',
    "download": '<path d="M12 3.5V15"/><path d="m7 10 5 5 5-5"/><path d="M4.5 20.5h15"/>',
    "upload": '<path d="M12 15V3.5"/><path d="m7 8.5 5-5 5 5"/><path d="M4.5 20.5h15"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
    "play": '<path d="M8 5.5v13l10-6.5z" fill="currentColor" stroke="none"/>',
    "pause": '<rect x="6.5" y="5" width="3.6" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="13.9" y="5" width="3.6" height="14" rx="1" fill="currentColor" stroke="none"/>',
    "eye": '<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eyeOff": '<path d="M10.6 6c.5-.1.9-.2 1.4-.2 6 0 9.5 6.2 9.5 6.2a17 17 0 0 1-2.7 3.4"/><path d="M6.4 7.3A16.6 16.6 0 0 0 2.5 12S6 18.2 12 18.2c1.6 0 3-.4 4.2-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="m4 4 16 16"/>',
    "pencil": '<path d="m14.5 5.5 4 4"/><path d="M4 20l1.2-4.6L16.4 4.2a2 2 0 0 1 2.8 0l.6.6a2 2 0 0 1 0 2.8L8.6 18.8z"/>',
    "key": '<circle cx="8" cy="15.5" r="4.2"/><path d="m11 12.5 8.5-8.5"/><path d="M16 7.5 19 10.5"/><path d="M13.5 10 16 12.5"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.6 2.3 4 5.3 4 8.5s-1.4 6.2-4 8.5c-2.6-2.3-4-5.3-4-8.5s1.4-6.2 4-8.5z"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2.5V6"/><path d="M15 2.5V6"/><path d="M9 18v3.5"/><path d="M15 18v3.5"/><path d="M2.5 9H6"/><path d="M2.5 15H6"/><path d="M18 9h3.5"/><path d="M18 15h3.5"/>',
    "bell": '<path d="M6.3 9.5a5.7 5.7 0 0 1 11.4 0c0 4.6 1.8 5.8 1.8 5.8H4.5s1.8-1.2 1.8-5.8"/><path d="M10.4 19.5a1.7 1.7 0 0 0 3.2 0"/>',
    "wave": '<path d="M4 10v4"/><path d="M8 7v10"/><path d="M12 4v16"/><path d="M16 7v10"/><path d="M20 10v4"/>',
    "headphones": '<path d="M4 14.5v-2a8 8 0 0 1 16 0v2"/><path d="M4 14.5h2.2a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M20 14.5h-2.2a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1H19a1 1 0 0 0 1-1z"/>',
    "monitor": '<rect x="3" y="4.5" width="18" height="12.5" rx="2"/><path d="M8.5 21h7"/><path d="M12 17v4"/>',
    "power": '<path d="M12 3v9"/><path d="M18.2 6.6a8.5 8.5 0 1 1-12.4 0"/>',
    "restart": '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.4"/><path d="M3.5 3.5v5h5"/>',
    "filter": '<path d="M4 5.5h16l-6.2 7.2v4.9l-3.6 1.9v-6.8z"/>',
    "calendar": '<rect x="4" y="5.5" width="16" height="15" rx="2"/><path d="M8 3.5v4"/><path d="M16 3.5v4"/><path d="M4 10.5h16"/>',
    "tag": '<path d="m3.5 12.6V5.5a2 2 0 0 1 2-2h7.1a2 2 0 0 1 1.4.6l6.5 6.5a2 2 0 0 1 0 2.8l-7.1 7.1a2 2 0 0 1-2.8 0l-6.5-6.5a2 2 0 0 1-.6-1.4z"/><circle cx="8" cy="8" r="1.1" fill="currentColor" stroke="none"/>',
    "type": '<path d="M5 6.5V4.5h14v2"/><path d="M12 4.5V19.5"/><path d="M9 19.5h6"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2.5"/>',
    "arrowUR": '<path d="M7 17 17 7"/><path d="M8.5 7H17v8.5"/>',
    "minus": '<path d="M5.5 12h13"/>',
    "square": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "save": '<path d="M5.5 3.5h10.5l3.5 3.5v12a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4.5 19V5a1.5 1.5 0 0 1 1-1.5z"/><path d="M8 3.5V8h7V3.5"/><path d="M8 20.5v-6h8v6"/>',
    "sun": '<circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v2"/><path d="M12 19.5v2"/><path d="m4.6 4.6 1.4 1.4"/><path d="m18 18 1.4 1.4"/><path d="M2.5 12h2"/><path d="M19.5 12h2"/><path d="m4.6 19.4 1.4-1.4"/><path d="m18 6 1.4-1.4"/>',
    "moon": '<path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2z"/>',
}


def _default_color():
    try:
        from . import theme as _theme
        return _theme.palette().get("fg", "#E7F0EC")
    except Exception:
        return "#E7F0EC"


def svg(name, color=None):
    """The full SVG document for an icon, with the stroke coloured in."""
    if color is None:
        color = _default_color()
    return _SVG_OPEN.format(color=color) + ICONS.get(name, "") + "</svg>"


def pixmap(name, size=17, color=None):
    """Render an icon to a QPixmap of the given pixel size."""
    if color is None:
        color = _default_color()
    renderer = QSvgRenderer(QByteArray(svg(name, color).encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()
    pm = QPixmap(int(size), int(size))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def icon(name, size=17, color=None):
    """A QIcon for a named glyph. `color` is a hex string; None uses theme fg."""
    if color is None:
        color = _default_color()
    return QIcon(pixmap(name, size, color))

"""Page builders — one module per prototype screen.

Each module exposes ``build(window)`` which constructs that screen's widgets
inside the settings window (assigning the window attributes the tests and the
save/load path use) and returns the page widget. Shared scaffolding lives here.
"""

from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ..widgets import Subtitle, Title


def scrolled(widget):
    """A page wrapped in a borderless, resizable scroll area."""
    from PyQt6.QtCore import Qt
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


def page(title="", subtitle=""):
    """A padded page column, with an optional title + subtitle head."""
    body = QWidget()
    outer = QVBoxLayout(body)
    outer.setContentsMargins(36, 26, 36, 40)
    outer.setSpacing(16)
    if title:
        outer.addWidget(Title(title))
    if subtitle:
        outer.addWidget(Subtitle(subtitle))
    # Store outer for responsive margin updates
    body.setProperty("_outer", outer)
    return body, outer


def update_margins(body, compact: bool):
    """Adjust page padding for <1080 breakpoint (36,26 vs 24,22)."""
    if body is None:
        return
    layout = body.layout()
    if layout is None:
        return
    if compact:
        layout.setContentsMargins(24, 22, 24, 32)
    else:
        layout.setContentsMargins(36, 26, 36, 40)
    # also handle savebar if present via finding sibling
    try:
        body.updateGeometry()
    except Exception:
        pass


def apply_page_margins_for_width(window, width: int):
    """Helper for SettingsWindow.resizeEvent to update all pages."""
    compact = width < 1080
    try:
        from PyQt6.QtWidgets import QScrollArea
        tabs = getattr(window, "tabs", None) or getattr(window, "shell", None) and getattr(window.shell, "tabs", None)
        if tabs is None:
            return
        for i in range(tabs.count()):
            scroll = tabs.widget(i)
            body = None
            if isinstance(scroll, QScrollArea):
                body = scroll.widget()
            elif isinstance(scroll, QWidget) and scroll.layout() is not None:
                body = scroll
            if body is not None:
                update_margins(body, compact)
    except Exception:
        pass

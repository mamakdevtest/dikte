"""Native components over ``ui/widgets.py`` — same APIs, no duplication.

``ui/widgets.py`` owns every behaviour (including ``ToggleSwitch``'s animated
knob); this module wraps it with the two newer faces the catalogue needs —
``Button`` (capitalised twin of ``btn()``) and ``Dropdown`` (editable combo
with its focus ring from QSS) — and re-exports the rest under the exact same
names so existing callers keep working.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QPushButton

from . import icons as _icons
from . import theme as _theme
from .widgets import (
    CornerPicker,
    Dot,
    EmptyState,
    InfoNote,
    KbdChip,
    Meta,
    MiniScreen,
    ModelRow,
    MonoLabel,
    SectionCard,
    SegmentedControl,
    SettingRow,
    Spinner,
    StatusChip,
    Subtitle,
    Title,
    ToggleSwitch,
    btn,
    gate,
    icon_button,
    model_row,
    switch_row,
)

__all__ = [
    "Button", "Dropdown", "ModelRow", "model_row", "ToggleSwitch",
    "SectionCard", "SettingRow", "switch_row", "gate",
    "InfoNote", "StatusChip", "Dot", "Spinner", "EmptyState",
    "btn", "icon_button", "Meta", "MonoLabel", "KbdChip", "Title", "Subtitle",
    "SegmentedControl", "CornerPicker", "MiniScreen",
]

_VARIANTS = ("primary", "ink", "secondary", "ghost", "danger", "rec", "seg")


class Button(QPushButton):
    """A styled push-button; ``size="sm"`` selects the 26px-tall button.

    Same contract as ``widgets.btn()`` — ``variant`` picks the QSS brush,
    ``icon_name`` renders through ``ui/icons.py`` — as a class for callers
    that prefer construction over a factory.
    """

    def __init__(self, text="", variant="secondary", size=None,
                 icon_name=None, icon_color=None, parent=None):
        super().__init__(text, parent)
        self.setProperty("variant",
                         variant if variant in _VARIANTS else "secondary")
        if size == "sm":
            self.setProperty("size", "sm")
            self.setFixedHeight(26)
        else:
            self.setFixedHeight(32)
        if icon_name:
            try:
                self.setIcon(_icons.icon(
                    icon_name, 15, icon_color or _theme.palette()["fg2"]))
            except Exception:
                pass


class Dropdown(QComboBox):
    """Editable combo whose hover/focus/disabled/popup paint comes from QSS.

    The focus ring is ``QComboBox#dropdown:focus`` in ``ui/qss.py`` — no
    inline ``setStyleSheet`` here, only behaviour: editable, no-insert (a
    typed id survives a fetch), and the ``dropdown`` object name.
    """

    def __init__(self, items=(), parent=None, placeholder=""):
        super().__init__(parent)
        self.setObjectName("dropdown")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if placeholder:
            try:
                self.setPlaceholderText(placeholder)
            except Exception:
                try:
                    self.lineEdit().setPlaceholderText(placeholder)
                except Exception:
                    pass
        if items:
            self.addItems(list(items))

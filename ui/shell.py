"""AppShell: the two-column frame — sidebar and a hidden-bar page stack.

The page stack is a plain QTabWidget whose tab bar is hidden; the sidebar drives
``currentIndex`` and stays in sync both ways. ``SettingsWindow.tabs`` is this
same QTabWidget, so the test contract (9 tabs, ``api_tab_index``) holds exactly
as before.
"""

import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from . import icons as _icons
from . import theme
from .widgets import Dot, Meta, StatusChip


# The nine pages, in the order the tabs (and therefore the sidebar) carry them.
# (icon, english key) — the label is resolved through t() by the caller.
NAV = [
    ("sliders", "General"),
    ("plug", "API and models"),
    ("eraser", "Cleanup rules"),
    ("terminal", "Agent"),
    ("users", "Meeting"),
    ("fileText", "Minutes"),
    ("fileAudio", "Audio file"),
    ("keyboard", "Shortcuts"),
    ("history", "History"),
]


def _badge_pixmap(size=34):
    """The brand badge: the app's dikte.png in a rounded square with the terra
    dot in the corner."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pm = QPixmap()
    for cand in (os.path.join(base, "icons", "dikte.png"),
                 os.path.join(base, "design", "Dikte-Yeniden-Tasarım-Prototipi",
                              "dikte.png")):
        if os.path.isfile(cand):
            pm = QPixmap(cand)
            break
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = theme.palette()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(c["fg"]))
    painter.drawRoundedRect(0, 0, size, size, 10, 10)
    if not pm.isNull():
        scaled = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - size) // 2
        y = (scaled.height() - size) // 2
        painter.drawPixmap(-x, -y, scaled)
    painter.setBrush(QColor(c["terra"]))
    painter.drawEllipse(size - 9, size - 9, 8, 8)
    painter.end()
    return out


class AppShell(QWidget):
    theme_toggled = pyqtSignal()

    def __init__(self, whisper_label="Whisper", parent=None):
        super().__init__(parent)
        self._nav = []          # list of (button, icon_name)
        self._nav_titles = []
        self._compact = False
        self._theme_name = "dark"

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        sidebar = self._build_sidebar(whisper_label)
        self._sidebar = sidebar

        main = QWidget()
        main.setObjectName("main")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.tabs)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar, 0)
        layout.addWidget(main, 1)

    # ---- sidebar ---------------------------------------------------------

    def _build_sidebar(self, whisper_label):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(226)
        col = QVBoxLayout(sidebar)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # brand block
        brand = QWidget()
        self._brand_widget = brand
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(16, 18, 16, 14)
        bl.setSpacing(11)
        self._brand_layout = bl
        badge = QLabel()
        badge.setPixmap(_badge_pixmap())
        badge.setFixedSize(34, 34)
        bl.addWidget(badge)
        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(0)
        name = QLabel("Dikte")
        name.setObjectName("brandName")
        name_col.addWidget(name)
        sub = QLabel(_t("Local dictation"))
        sub.setObjectName("brandSub")
        name_col.addWidget(sub)
        bl.addLayout(name_col)
        self._brand_name = name
        self._brand_sub = sub
        bl.addStretch(1)
        col.addWidget(brand)

        # nav
        nav = QVBoxLayout()
        nav.setContentsMargins(10, 2, 10, 2)
        nav.setSpacing(1)
        self._nav = []
        col.addLayout(nav, 1)
        self._nav_layout = nav

        # foot: engine card + theme toggle
        foot = QWidget()
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(12, 10, 12, 12)
        fl.setSpacing(8)

        engine = self._engine_card(whisper_label)
        self._engine_card_widget = engine
        fl.addWidget(engine)
        self._foot_widget = foot

        self.theme_button = QPushButton()
        self.theme_button.setProperty("variant", "ghost")
        self.theme_button.setFixedHeight(30)
        self.theme_button.clicked.connect(self.theme_toggled.emit)
        fl.addWidget(self.theme_button)
        col.addWidget(foot)
        return sidebar

    @staticmethod
    def _engine_card(whisper_label):
        card = QWidget()
        card.setObjectName("card")
        col = QVBoxLayout(card)
        col.setContentsMargins(11, 9, 11, 9)
        col.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(7)
        wave = QLabel()
        wave.setPixmap(_icons.pixmap("wave", 15, theme.palette()["sageDark"]))
        top.addWidget(wave)
        model = QLabel(whisper_label)
        model.setStyleSheet("font-size: 12.5px; font-weight: 600;")
        top.addWidget(model)
        top.addStretch(1)
        chip = StatusChip(_t("Local"), "sage", dot="sage")
        top.addWidget(chip)
        col.addLayout(top)

        status = QHBoxLayout()
        status.setSpacing(6)
        status.addWidget(Dot("ok"))
        ready = QLabel(_t("Ready"))
        ready.setStyleSheet("color: %s; font-size: 11.5px;" % theme.palette()["fg2"])
        status.addWidget(ready)
        status.addStretch(1)
        ver = Meta("1.0")
        ver.setProperty("mono", True)
        status.addWidget(ver)
        col.addLayout(status)
        return card

    # ---- pages -----------------------------------------------------------

    def add_page(self, title, widget, icon_name):
        index = self.tabs.addTab(widget, title)
        button = QPushButton()
        button.setObjectName("navItem")
        button.setProperty("active", False)
        button.setIconSize(QSize(16, 16))
        button.setText("  " + title)
        button.setIcon(_icons.icon(icon_name, 16, theme.palette()["fg3"]))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _=False, i=index: self.set_page(i))
        self._nav_layout.addWidget(button)
        self._nav.append((button, icon_name))
        self._nav_titles.append(title)
        if getattr(self, "_compact", False):
            button.setText("")
            button.setStyleSheet("text-align: center; padding: 0;")
        return index

    def set_page(self, index):
        self.tabs.setCurrentIndex(index)
        self._sync_nav(index)

    def _on_tab_changed(self, index):
        self._sync_nav(index)

    def _sync_nav(self, index):
        c = theme.palette()
        for i, (button, icon_name) in enumerate(self._nav):
            active = i == index
            button.setProperty("active", active)
            color = c["sageDark"] if active else c["fg3"]
            button.setIcon(_icons.icon(icon_name, 16, color))
            button.style().unpolish(button)
            button.style().polish(button)

    # ---- theme -----------------------------------------------------------

    def _apply_theme_text(self):
        c = theme.palette(self._theme_name)
        icon_name = "moon" if self._theme_name == "dark" else "sun"
        self.theme_button.setIcon(_icons.icon(icon_name, 14, c["fg2"]))
        self.theme_button.setToolTip(
            _t("Switch to light theme") if self._theme_name == "dark" else _t("Switch to dark theme"))
        if getattr(self, "_compact", False):
            self.theme_button.setText("")
        else:
            self.theme_button.setText(
                "  " + (_t("Light theme") if self._theme_name == "dark" else _t("Dark theme")))

    def set_theme(self, name):
        self._theme_name = name if name in ("dark", "light") else "dark"
        self._apply_theme_text()

    def setCompact(self, compact: bool):
        compact = bool(compact)
        if getattr(self, "_compact", False) == compact:
            # still need to ensure theme text reflects mode if theme changed
            pass
        self._compact = compact
        if hasattr(self, "_sidebar") and self._sidebar is not None:
            self._sidebar.setFixedWidth(64 if compact else 226)
        if hasattr(self, "_brand_layout") and self._brand_layout is not None:
            if compact:
                self._brand_layout.setContentsMargins(0, 14, 0, 10)
                self._brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                self._brand_layout.setContentsMargins(16, 18, 16, 14)
                self._brand_layout.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if hasattr(self, "_brand_name"):
            self._brand_name.setVisible(not compact)
        if hasattr(self, "_brand_sub"):
            self._brand_sub.setVisible(not compact)
        if hasattr(self, "_engine_card_widget"):
            self._engine_card_widget.setVisible(not compact)
        for idx, (button, icon_name) in enumerate(self._nav):
            title = self._nav_titles[idx] if idx < len(self._nav_titles) else button.text().strip()
            if compact:
                button.setText("")
                button.setStyleSheet("text-align: center; padding: 0;")
            else:
                button.setText("  " + title)
                button.setStyleSheet("")
            button.style().unpolish(button)
            button.style().polish(button)
        self._apply_theme_text()
        if hasattr(self, "_brand_widget"):
            self._brand_widget.style().unpolish(self._brand_widget)
            self._brand_widget.style().polish(self._brand_widget)


# A tiny late-binding wrapper so shell.py imports stay free of a hard i18n
# dependency at module import time (i18n is imported by settings_ui already).
def _t(text):
    try:
        from i18n import t
        return t(text)
    except Exception:
        return text

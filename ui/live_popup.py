"""The wider live view: what is being heard, while it is being heard.

A small button on the recording pill opens this; the words that arrive from
the rolling preview collect here in a panel big enough to read at a glance,
for dictation and for the microphone side of a meeting alike.
"""

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QPlainTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from i18n import t

try:
    from ui import theme as _theme
except Exception:  # pragma: no cover - theme is always available in the app
    _theme = None

WIDTH = 460
HEIGHT = 260
RADIUS = 14
EXPAND_FACTOR = 1.8       # grown height target, in compact heights
MAX_AREA_FRACTION = 0.6   # but never taller than this share of the screen
NEAR_BOTTOM_SLACK = 8     # px from the bottom that still counts as "following"


def _palette():
    if _theme is not None:
        p = _theme.palette()
    else:
        p = {"field": "#142123", "border": "#314548", "fg": "#E7F0EC",
             "fg3": "#7C918A", "surface2": "#223234"}
    return p


class LivePopup(QWidget):
    """A frameless card that collects the live preview text."""

    overlayGeometryChanged = pyqtSignal()
    concealed = pyqtSignal()

    def __init__(self, corner="bottom-left", below=None):
        super().__init__(None)
        self.corner = corner
        self.below = below
        self._overlay_coordinator = None
        self._expanded = False
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(WIDTH, HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 34, 14, 12)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.text.setObjectName("live_popup_text")
        self.text.setPlaceholderText(t("Words will appear here as they are heard…"))
        # Structural QSS only (no frozen palette hex): tone comes from
        # QPalette via _refresh_palette() + QPainter via _palette().
        self.text.setStyleSheet(
            "QPlainTextEdit#live_popup_text { background: transparent; "
            "border: none; font-size: 13px; }"
        )
        layout.addWidget(self.text)

        self.arrow = QToolButton(self)
        self.arrow.setObjectName("live_popup_expand")
        self.arrow.setText("▼")
        self.arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.arrow.setStyleSheet(
            "QToolButton#live_popup_expand { background: transparent; border: none; "
            "font-size: 12px; padding: 2px 8px; border-radius: 6px; } "
            "QToolButton#live_popup_expand:hover { background: rgba(255, 255, 255, 28); }"
        )
        self.arrow.clicked.connect(self._toggle_expanded)
        self._refresh_palette()
        self._apply_expanded_labels()
        self._place_arrow()

    def _refresh_palette(self):
        """Apply the current theme tone via QPalette (no frozen hex in QSS)."""
        try:
            p = _palette()
            fg = QColor(p.get("fg", "#E7F0EC"))
            fg3 = QColor(p.get("fg3", "#7C918A"))
        except Exception:
            return
        try:
            pal = self.text.palette()
            pal.setColor(self.text.backgroundRole(), QColor(0, 0, 0, 0))
            pal.setColor(pal.ColorRole.Text, fg)
            try:
                pal.setColor(pal.ColorRole.PlaceholderText, fg3)
            except Exception:
                pass
            self.text.setPalette(pal)
        except Exception:
            pass
        try:
            apal = self.arrow.palette()
            apal.setColor(apal.ColorRole.ButtonText, fg)
            apal.setColor(apal.ColorRole.WindowText, fg)
            self.arrow.setPalette(apal)
        except Exception:
            pass

    def _apply_expanded_labels(self):
        tip = t("Collapse") if self._expanded else t("Expand")
        self.arrow.setToolTip(tip)
        self.arrow.setAccessibleName(tip)

    def set_overlay_coordinator(self, coordinator):
        """Bind this optional live-detail card to an activity stack."""
        self._overlay_coordinator = coordinator
        if coordinator is not None:
            self.below = None

    @property
    def overlay_coordinator(self):
        return self._overlay_coordinator

    def _place_arrow(self):
        self.arrow.resize(self.arrow.sizeHint())
        self.arrow.move(self.width() - self.arrow.width() - 8, 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_arrow()
        self.overlayGeometryChanged.emit()

    def _toggle_expanded(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded):
        """Grow the card toward twice its height, or shrink it back.

        The grown height is capped at a share of the screen's available
        height, and the card is re-anchored so it stays fully on screen.
        """
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if expanded:
            area = self._screen_area()
            cap = int(area.height() * MAX_AREA_FRACTION) if area is not None \
                else int(HEIGHT * EXPAND_FACTOR)
            self.resize(WIDTH, max(HEIGHT, min(int(HEIGHT * EXPAND_FACTOR), cap)))
        else:
            self.resize(WIDTH, HEIGHT)
        self.arrow.setText("▲" if expanded else "▼")
        self._apply_expanded_labels()
        self._reposition()

    def paintEvent(self, _event):
        p = _palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(p["border"]), 1))
        bg = QColor(p["field"])
        bg.setAlpha(242)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), RADIUS, RADIUS)
        painter.setPen(QColor(p["fg"]))
        font = QFont(self.font())
        font.setPointSizeF(9.5)
        font.setBold(True)
        painter.setFont(font)
        header = QRect(14, 8, self.width() - 58, 18)
        painter.drawText(header,
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         t("Live speech"))

    def set_text(self, text):
        """Replace the preview text, keeping the newest words on screen.

        When the reader has scrolled up to look at older words, the view
        stays where they put it; following resumes once they return to
        the bottom.
        """
        text = text or ""
        if self.text.toPlainText() == text:
            return
        bar = self.text.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - NEAR_BOTTOM_SLACK
        held = bar.value()
        self.text.setPlainText(text)
        if at_bottom:
            bar.setValue(bar.maximum())
        else:
            bar.setValue(min(held, bar.maximum()))

    def toggle(self):
        if self.isVisible():
            self.hide()
            self.concealed.emit()
        else:
            self.show()
            self._reposition()
            self.raise_()

    def _screen_area(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QCursor
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _reposition(self):
        coordinator = self._overlay_coordinator
        if coordinator is not None:
            coordinator.recompute_geometry()
            return
        area = self._screen_area()
        if area is None:
            return
        left = "left" in self.corner
        x = area.left() + 28 if left else area.right() - self.width() - 28
        anchor = self.below.y() if self.below is not None and self.below.isVisible() \
            else area.bottom() - self.height() - 28
        y = int(anchor - self.height() - 10)
        if y < area.top() + 4:
            y = int(anchor + (self.below.height() if self.below else 72) + 10)
        # The grown card must never poke past either edge of the screen.
        y = max(area.top() + 4, min(y, int(area.bottom() - self.height() - 4)))
        self.move(int(x), y)

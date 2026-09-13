"""The wider live view: what is being heard, while it is being heard.

A small button on the recording pill opens this; the words that arrive from
the rolling preview collect here in a panel big enough to read at a glance,
for dictation and for the microphone side of a meeting alike.
"""

from PyQt6.QtCore import QPointF, QRect, Qt, pyqtSignal
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
# The card is as tall as the words in it (U6): a fixed height left three lines of
# text sitting in four hundred pixels of empty card, which reads as a broken panel
# rather than a quiet one. These two bounds only keep it sane — never a sliver, and
# never taller than the compact cap until the reader asks for more. HEIGHT keeps
# its name because it is still the height of a full compact card, and the size an
# empty one is drawn at is MIN_HEIGHT.
MIN_HEIGHT = 96
HEIGHT = 260
RADIUS = 14
MAX_AREA_FRACTION = 0.6   # the expanded card never exceeds this share of the screen
NEAR_BOTTOM_SLACK = 8     # px from the bottom that still counts as "following"
LIVE_FLOOR_PAD = 6        # breathing room under the last line


def _palette():
    if _theme is not None:
        p = _theme.palette()
    else:
        p = {"field": "#142123", "border": "#314548", "fg": "#E7F0EC",
             "fg3": "#7C918A", "surface2": "#223234",
             "terra": "#E08A72"}
    return p


class LivePopup(QWidget):
    """A frameless card that collects the live preview text."""

    overlayGeometryChanged = pyqtSignal()
    concealed = pyqtSignal()

    def __init__(self, corner="bottom-left", below=None):
        super().__init__(None)
        self.setObjectName("LivePopup")
        self.corner = corner
        self.below = below
        self._overlay_coordinator = None
        self._expanded = False
        self.setProperty("expanded", False)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(WIDTH, MIN_HEIGHT)

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
        self.arrow.setProperty("expanded", False)
        self.arrow.setText("▼")
        self.arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Structural QSS only (no frozen colour): tone comes from QPalette
        # via _refresh_palette(), hover is the cursor + tooltip, not a tint.
        self.arrow.setStyleSheet(
            "QToolButton#live_popup_expand { background: transparent; border: none; "
            "font-size: 12px; padding: 2px 8px; border-radius: 6px; }"
        )
        self.arrow.clicked.connect(self._toggle_expanded)
        self._refresh_palette()
        self._apply_expanded_labels()
        self._place_arrow()

    def _refresh_palette(self):
        """Apply the current theme tone via QPalette and the arrow's own sheet.

        The arrow takes its disabled colour from its stylesheet rather than the
        palette: with the application sheet in play, Qt resolves a QToolButton's
        text through QStyleSheetStyle, and a palette colour set on the widget is
        simply not what gets drawn — the disabled arrow came out in the enabled
        colour. The value is still taken from the live palette, so nothing is
        frozen here; only the channel it travels on is different.
        """
        try:
            p = _palette()
            fg = QColor(p.get("fg", "#E7F0EC"))
            fg3 = QColor(p.get("fg3", "#7C918A"))
        except Exception:
            return
        self._arrow_fg, self._arrow_fg3 = fg, fg3
        try:
            self.arrow.setStyleSheet(
                "QToolButton#live_popup_expand { background: transparent; "
                "border: none; font-size: 12px; padding: 2px 8px; "
                "border-radius: 6px; }\n"
                "QToolButton#live_popup_expand:disabled "
                f"{{ color: {fg3.name()}; }}")
        except Exception:
            pass
        try:
            pal = self.text.palette()
            pal.setColor(self.text.backgroundRole(), QColor(0, 0, 0, 0))
            pal.setColor(pal.ColorRole.Text, fg)
            try:
                pal.setColor(pal.ColorRole.PlaceholderText, fg3)
            except Exception:
                # reason: A palette role this Qt may not name. The placeholder keeps the
                #         colour the theme gave it, which is what it would have looked like
                #         anyway.
                pass
            self.text.setPalette(pal)
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

    def _chrome_height(self):
        """Everything in the card that is not text.

        Measured as the difference between the card and its text viewport, rather
        than counted from the layout margins. With the application stylesheet
        applied, the text area carries 8px of padding above and below that the
        margins know nothing about — a margins-only estimate came up a whole line
        short, so every card scrolled its last line out of sight.
        """
        viewport = self.text.viewport().height()
        if viewport > 0:
            return max(0, self.height() - viewport)
        margins = self.layout().contentsMargins()
        # Before the first layout pass there is no viewport to measure; the sheet
        # gives text areas 8px above and below, which is exactly the part a
        # margins-only estimate misses.
        return margins.top() + margins.bottom() + 16

    def _content_height(self):
        """How tall the card has to be for the text it is holding.

        Counted, not asked for. `QPlainTextEdit` lays its blocks out lazily:
        `document().size()` answers with a block count rather than pixels, and
        `blockBoundingRect` only knows about the blocks that have already been
        drawn, so neither can be trusted for text that is scrolling. The height is
        computed from the font metrics and the wrapped line count instead.
        """
        metrics = self.text.fontMetrics()
        width = self.text.viewport().width()
        if width <= 0:
            # Before the first layout pass there is no viewport to measure.
            margins = self.layout().contentsMargins()
            width = max(1, WIDTH - margins.left() - margins.right())
        lines = 0
        block = self.text.document().begin()
        while block.isValid():
            advance = metrics.horizontalAdvance(block.text())
            lines += max(1, -(-advance // width))    # ceil, without the import
            block = block.next()
        return int(max(1, lines) * max(1, metrics.lineSpacing())
                   + 2 * self.text.document().documentMargin()
                   + self._chrome_height() + LIVE_FLOOR_PAD)

    def _expanded_cap(self):
        area = self._screen_area()
        if area is None:
            return HEIGHT * 2
        return int(area.height() * MAX_AREA_FRACTION)

    def target_height(self):
        """The height this card should be, given its text and its size state."""
        needed = self._content_height()
        cap = self._expanded_cap() if self._expanded else HEIGHT
        # int() because the document margin is a float: Qt refuses a float height.
        return int(max(MIN_HEIGHT, min(needed, cap)))

    def _fit_height(self):
        """Follow the text. Returns True when the height actually changed."""
        target = self.target_height()
        changed = target != self.height()
        if changed:
            self.resize(WIDTH, target)
        self._update_arrow_availability()
        return changed

    def _update_arrow_availability(self):
        """Offer the arrow only when there is more to reveal.

        With the card sized to its text, a short transcript fits in both states, so
        expanding would change nothing. A control that does nothing when pressed is
        worse than one that is not offered.
        """
        more = max(MIN_HEIGHT, min(self._content_height(), self._expanded_cap())) \
            > max(MIN_HEIGHT, min(self._content_height(), HEIGHT))
        self.arrow.setEnabled(more)
        if not more:
            self.arrow.setToolTip("")
            self.arrow.setAccessibleName("")

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
        """Give the card more room to show, or take it back.

        The height is the text's, in both states: expanding raises the cap rather
        than forcing a size, so a long transcript gets the room it needs and a
        short one does not grow a card full of nothing. The expanded cap is a share
        of the screen, and the card is re-anchored afterwards so it stays on it.
        """
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        try:
            self.setProperty("expanded", expanded)
            self.arrow.setProperty("expanded", expanded)
            self.style().unpolish(self.arrow)
            self.style().polish(self.arrow)
        except Exception:
            pass
        self.resize(WIDTH, self.target_height())
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
        # Signature element: a small live dot tying the card to the pill.
        # Paint-only; the arrow hit-rect and text margins are untouched.
        try:
            dot = QColor(p.get("terra", "#E08A72"))
        except Exception:
            dot = QColor("#E08A72")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        painter.drawEllipse(QPointF(17.5, 17.0), 3.5, 3.5)
        painter.setPen(QColor(p["fg"]))
        font = QFont(self.font())
        font.setPointSizeF(9.5)
        font.setBold(True)
        painter.setFont(font)
        header = QRect(28, 8, self.width() - 72, 18)
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
        # Fit before restoring the scroll: the fit decides how much of the
        # document is visible, so it has to happen first or the position means
        # something else by the time it is applied.
        if self._fit_height():
            self._reposition()
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

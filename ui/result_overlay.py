"""Result overlay shown after transcription completes.

Compact collapsed preview with Expand/Copy/Close; expanded shows full text with scrollbar.
Respects auto_paste setting (caller decides whether to auto paste, we only show).
Clipboard via paste.copy, follows theme palette.
"""

import sys

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QFontMetrics
from PyQt6.QtWidgets import QApplication, QWidget

try:
    from i18n import t
except Exception:
    def t(s, **k):
        return s.format(**k) if k else s

# geometry
COLLAPSED_WIDTH = 360
COLLAPSED_HEIGHT = 56
EXPANDED_WIDTH = 420
EXPANDED_MAX_HEIGHT = 180
MARGIN = 28
GAP = 10
RADIUS = 14
BTN_H = 28
BTN_W_EXPAND = 32
BTN_W_COPY = 64
BTN_W_CLOSE = 32


def _hex_to_qcolor(hex_str, alpha=255):
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


def _palette_colors():
    try:
        from ui import theme as _theme
        p = _theme.palette()
    except Exception:
        p = {
            "field": "#142123", "surface": "#1B292B", "surface2": "#223234",
            "border": "#314548", "fg": "#E7F0EC", "fg3": "#7C918A",
            "terra": "#E08A72", "sageDark": "#A8C7B5", "ok": "#75C59B",
            "err": "#DF8582", "warn": "#D8B870", "info": "#82B9CE",
        }
    def mix(a, b, share):
        av = tuple(int(a[i:i+2],16) for i in (1,3,5))
        bv = tuple(int(b[i:i+2],16) for i in (1,3,5))
        r = round(av[0]*share+bv[0]*(1-share))
        g = round(av[1]*share+bv[1]*(1-share))
        b_ = round(av[2]*share+bv[2]*(1-share))
        c = QColor(r,g,b_)
        return c
    BG = mix(p["field"], p["surface"], 0.92, 238) if "mix" not in dir() else _hex_to_qcolor(p["field"],238)
    # fallback simple
    try:
        BG = QColor(p["field"])
        BG.setAlpha(238)
    except Exception:
        pass
    BORDER = _hex_to_qcolor(p["border"], 255)
    TEXT = _hex_to_qcolor(p["fg"])
    MUTED = _hex_to_qcolor(p["fg3"])
    SURFACE2 = _hex_to_qcolor(p["surface2"])
    return {
        "BG": BG, "BORDER": BORDER, "TEXT": TEXT, "MUTED": MUTED,
        "SURFACE2": SURFACE2, "FG": TEXT, "p": p
    }


class ResultOverlay(QWidget):
    copyRequested = pyqtSignal(str)
    closeRequested = pyqtSignal()
    expandChanged = pyqtSignal(bool)

    def __init__(self, corner="bottom-left", below=None, parent=None):
        super().__init__(None)
        self.corner = corner
        self.below = below
        self._concealed = True
        self._text = ""
        self._preview = ""
        self._expanded = False
        self._hover_expand = False
        self._hover_copy = False
        self._hover_close = False
        self._pressed_expand = False
        self._pressed_copy = False
        self._pressed_close = False
        self._expand_rect = QRectF()
        self._copy_rect = QRectF()
        self._close_rect = QRectF()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._conceal)

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if sys.platform not in ("darwin", "win32"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self._label_font = None
        self._title_font = None

    @property
    def showing(self):
        return self.isVisible() and not self._concealed

    @property
    def expanded(self):
        return self._expanded

    @property
    def text(self):
        return self._text

    def _label_font_obj(self):
        if self._label_font is None:
            f = QFont(self.font())
            f.setPointSizeF(10.5)
            self._label_font = f
        return self._label_font

    def _title_font_obj(self):
        if self._title_font is None:
            f = QFont(self._label_font_obj())
            f.setPointSizeF(9.0)
            f.setBold(True)
            self._title_font = f
        return self._title_font

    def _format_preview(self, text):
        line = text.replace("\n", " ").strip()
        if not line:
            return ""
        # first 48 chars + ellipsis
        if len(line) > 48:
            return line[:48].rstrip() + "…"
        return line

    def show_result(self, text: str, msec=None):
        """Show result. If msec is None, stay until user closes. Otherwise auto-hide after msec."""
        txt = (text or "").strip()
        if not txt:
            return
        # bound length for display (but keep full for copy/expanded)
        if len(txt) > 4000:
            txt = txt[:4000].rstrip() + "…"
        self._text = txt
        self._preview = self._format_preview(txt)
        self._expanded = False
        self._update_geometry()
        self._reposition()
        if not self.isVisible():
            self.show()
        self._concealed = False
        self.raise_()
        self.update()
        self._hide_timer.stop()
        if msec is not None and msec > 0:
            self._hide_timer.start(int(msec))

    def set_expanded(self, expanded: bool):
        expanded = bool(expanded)
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._update_geometry()
        self._reposition()
        self.update()
        self.expandChanged.emit(expanded)

    def toggle_expanded(self):
        self.set_expanded(not self._expanded)

    def _update_geometry(self):
        if self._expanded:
            # expanded height based on text lines, capped
            # need font metrics to estimate
            fm = QFontMetrics(self._label_font_obj())
            avail_w = EXPANDED_WIDTH - 28  # margins
            # rough line count
            lines = 0
            for para in self._text.split("\n"):
                if not para:
                    lines += 1
                else:
                    w = fm.horizontalAdvance(para)
                    lines += max(1, (w // max(1, avail_w)) + 1)
            # each line ~18px + padding
            needed = 32 + 24 + lines * 18 + 18  # title + text + buttons
            h = max(120, min(EXPANDED_MAX_HEIGHT, needed))
            self.resize(EXPANDED_WIDTH, int(h))
        else:
            self.resize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)

    def _reposition(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        left = "left" in self.corner
        top = "top" in self.corner
        stacked = self.below is not None and getattr(self.below, "showing", False)
        step = (self.below.height() + GAP) if stacked else 0
        x = area.left() + MARGIN if left else area.right() - self.width() - MARGIN
        y = (area.top() + MARGIN + step if top else area.bottom() - self.height() - MARGIN - step)
        self.move(int(x), int(y))

    def _conceal(self):
        self._concealed = True
        self.hide()
        self._expanded = False
        self._hover_expand = False
        self._hover_copy = False
        self._hover_close = False

    def dismiss(self):
        self._hide_timer.stop()
        self._conceal()

    def _copy(self):
        try:
            import paste
            paste.copy(self._text)
        except Exception:
            try:
                QApplication.clipboard().setText(self._text)
            except Exception:
                pass
        self.copyRequested.emit(self._text)
        # brief feedback: show copied state via tooltip? For now keep visible
        # auto-hide after copy? Keep 1.2s then hide if not expanded
        if not self._expanded:
            self._hide_timer.start(1200)

    # ---- mouse handling -------------------------------------------------
    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        pt = QPointF(pos.x(), pos.y()) if hasattr(pos, "x") else QPointF(float(pos.x()), float(pos.y()))
        if self._expanded:
            # in expanded mode: copy and close are bottom row, expand at top-right
            if self._copy_rect.isValid() and self._copy_rect.contains(pt):
                self._pressed_copy = True
                self.update(self._copy_rect.toRect())
                event.accept()
                return
            if self._close_rect.isValid() and self._close_rect.contains(pt):
                self._pressed_close = True
                self.update(self._close_rect.toRect())
                event.accept()
                return
            if self._expand_rect.isValid() and self._expand_rect.contains(pt):
                self._pressed_expand = True
                event.accept()
                return
        else:
            if self._expand_rect.isValid() and self._expand_rect.contains(pt):
                self._pressed_expand = True
                self.update(self._expand_rect.toRect())
                event.accept()
                return
            if self._copy_rect.isValid() and self._copy_rect.contains(pt):
                self._pressed_copy = True
                self.update(self._copy_rect.toRect())
                event.accept()
                return
            if self._close_rect.isValid() and self._close_rect.contains(pt):
                self._pressed_close = True
                self.update(self._close_rect.toRect())
                event.accept()
                return
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        pt = QPointF(pos.x(), pos.y()) if hasattr(pos, "x") else QPointF(float(pos.x()), float(pos.y()))
        # update hovers
        for attr, rect_attr in [("_hover_expand","_expand_rect"), ("_hover_copy","_copy_rect"), ("_hover_close","_close_rect")]:
            rect = getattr(self, rect_attr)
            hover = rect.isValid() and rect.contains(pt) if rect.isValid() else False
            if getattr(self, attr) != hover:
                setattr(self, attr, hover)
                self.update(rect.toRect())
        event.accept()

    def mouseReleaseEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        pt = QPointF(pos.x(), pos.y()) if hasattr(pos, "x") else QPointF(float(pos.x()), float(pos.y()))
        if self._pressed_expand and self._expand_rect.contains(pt):
            self._pressed_expand = False
            self.toggle_expanded()
            event.accept()
            return
        if self._pressed_copy and self._copy_rect.contains(pt):
            self._pressed_copy = False
            self._copy()
            self.update(self._copy_rect.toRect())
            event.accept()
            return
        if self._pressed_close and self._close_rect.contains(pt):
            self._pressed_close = False
            self.closeRequested.emit()
            self.dismiss()
            event.accept()
            return
        # reset presses
        if self._pressed_expand:
            self._pressed_expand = False
            self.update(self._expand_rect.toRect())
        if self._pressed_copy:
            self._pressed_copy = False
            self.update(self._copy_rect.toRect())
        if self._pressed_close:
            self._pressed_close = False
            self.update(self._close_rect.toRect())
        event.accept()

    def leaveEvent(self, event):
        for attr, rect_attr in [("_hover_expand","_expand_rect"), ("_hover_copy","_copy_rect"), ("_hover_close","_close_rect")]:
            if getattr(self, attr):
                setattr(self, attr, False)
                self.update(getattr(self, rect_attr).toRect())
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    # ---- painting -------------------------------------------------------
    def paintEvent(self, _event):
        if self._concealed:
            return
        cols = _palette_colors()
        BG = cols["BG"]
        BORDER = cols["BORDER"]
        TEXT = cols["TEXT"]
        MUTED = cols["MUTED"]
        SURFACE2 = cols["SURFACE2"]
        p = _palette_colors()["p"] if "p" in cols else {}
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # main bg
        rect = QRectF(0.5, 0.5, self.width()-1, self.height()-1)
        painter.setPen(QPen(BORDER, 1))
        painter.setBrush(BG)
        painter.drawRoundedRect(rect, RADIUS, RADIUS)

        if self._expanded:
            # Title
            painter.setFont(self._title_font_obj())
            painter.setPen(TEXT)
            title = t("Transcription")
            painter.drawText(QRectF(14, 10, self.width()-80, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), title)
            # expand button top-right (collapse)
            self._expand_rect = QRectF(self.width()-36, 8, 28, 22)
            # draw expand bg
            bcol = QColor(SURFACE2 if self._hover_expand else BG)
            if self._pressed_expand:
                bcol = QColor(BORDER)
            # keep alpha
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bcol)
            painter.drawRoundedRect(self._expand_rect, 6, 6)
            painter.setPen(QPen(TEXT, 1.2))
            cx = self._expand_rect.center().x()
            cy = self._expand_rect.center().y()
            # up chevron (collapse)
            painter.drawPolyline(QPointF(cx-4, cy+2), QPointF(cx, cy-2), QPointF(cx+4, cy+2))
            # Text area
            painter.setFont(self._label_font_obj())
            painter.setPen(TEXT)
            text_rect = QRectF(14, 34, self.width()-28, self.height()-70)
            # draw with word wrap and clip
            painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self._text)
            # bottom row: Copy / Close
            btn_y = self.height() - 34
            # copy button
            self._copy_rect = QRectF(14, btn_y, BTN_W_COPY, BTN_H)
            copy_bg = QColor(p.get("terraDeep", "#C66F5D") if "terraDeep" in p else "#C66F5D")
            # use primary variant imitation
            # Actually use terraDeep for primary copy
            if self._hover_copy:
                copy_bg = QColor(p.get("terra", "#E08A72"))
            if self._pressed_copy:
                copy_bg = QColor(p.get("borderStrong", "#4A6261"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(copy_bg)
            painter.drawRoundedRect(self._copy_rect, 6, 6)
            painter.setPen(QColor("#FFF8F5"))
            painter.setFont(self._label_font_obj())
            painter.drawText(self._copy_rect, int(Qt.AlignmentFlag.AlignCenter), t("Copy"))
            # close button (X)
            self._close_rect = QRectF(self.width()- 14 - BTN_W_CLOSE, btn_y, BTN_W_CLOSE, BTN_H)
            close_bg = QColor(SURFACE2 if self._hover_close else BG)
            if self._pressed_close:
                close_bg = QColor(BORDER)
            painter.setPen(QPen(BORDER, 1) if not self._hover_close else QPen(TEXT, 1))
            painter.setBrush(close_bg)
            painter.drawRoundedRect(self._close_rect, 6, 6)
            painter.setPen(QPen(MUTED if not self._hover_close else TEXT, 1.4))
            cx2 = self._close_rect.center().x()
            cy2 = self._close_rect.center().y()
            painter.drawLine(QPointF(cx2-5, cy2-5), QPointF(cx2+5, cy2+5))
            painter.drawLine(QPointF(cx2+5, cy2-5), QPointF(cx2-5, cy2+5))
        else:
            # collapsed: single line preview + expand arrow + copy + close compact
            painter.setFont(self._label_font_obj())
            painter.setPen(TEXT)
            fm = QFontMetrics(self._label_font_obj())
            avail = self.width() - 14 - BTN_W_EXPAND - 8 - BTN_W_COPY - 8 - BTN_W_CLOSE - 12
            preview = fm.elidedText(self._preview or self._text.replace("\n"," ")[:48], Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(QRectF(14, 0, avail, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), preview)
            # expand button (chevron up)
            self._expand_rect = QRectF(self.width() - BTN_W_EXPAND - BTN_W_COPY - BTN_W_CLOSE - 16 - 8, (self.height()-22)/2, BTN_W_EXPAND, 22)
            exp_bg = QColor(SURFACE2 if self._hover_expand else BG)
            if self._pressed_expand:
                exp_bg = QColor(BORDER)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(exp_bg)
            painter.drawRoundedRect(self._expand_rect, 6, 6)
            painter.setPen(QPen(TEXT, 1.2))
            cx = self._expand_rect.center().x()
            cy = self._expand_rect.center().y()
            # down arrow to expand (since collapsed preview shows up arrow per spec)
            painter.drawPolyline(QPointF(cx-4, cy-1), QPointF(cx, cy+3), QPointF(cx+4, cy-1))
            # copy button small
            self._copy_rect = QRectF(self._expand_rect.right()+8, (self.height()-BTN_H)/2, BTN_W_COPY-16, BTN_H)
            # make copy as icon/text small
            copy_bg = QColor(SURFACE2 if self._hover_copy else BG)
            if self._pressed_copy:
                copy_bg = QColor(BORDER)
            painter.setPen(QPen(BORDER, 1) if not self._hover_copy else QPen(TEXT, 1))
            painter.setBrush(copy_bg)
            painter.drawRoundedRect(self._copy_rect, 6, 6)
            painter.setPen(TEXT)
            painter.setFont(self._label_font_obj())
            # use smaller font for collapsed copy
            painter.drawText(self._copy_rect, int(Qt.AlignmentFlag.AlignCenter), t("Copy"))
            # close X
            self._close_rect = QRectF(self._copy_rect.right()+8, (self.height()-22)/2, 22, 22)
            close_bg = QColor(SURFACE2 if self._hover_close else BG)
            if self._pressed_close:
                close_bg = QColor(BORDER)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(close_bg)
            painter.drawRoundedRect(self._close_rect, 5, 5)
            painter.setPen(QPen(MUTED if not self._hover_close else TEXT, 1.3))
            cx2 = self._close_rect.center().x()
            cy2 = self._close_rect.center().y()
            painter.drawLine(QPointF(cx2-3.5, cy2-3.5), QPointF(cx2+3.5, cy2+3.5))
            painter.drawLine(QPointF(cx2+3.5, cy2-3.5), QPointF(cx2-3.5, cy2+3.5))

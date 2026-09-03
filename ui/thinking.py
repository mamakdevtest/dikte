"""Tiny thinking overlay: what the agent is doing right now.

Shows the current stage, a scrolling log of recent stages, and
pause / stop controls. Frameless, always on top, click-through
only when idle; during work the pause/stop buttons are hit-testable.
"""

import time
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QFrame, QScrollArea, QApplication
)

from . import theme as _theme
from . import icons as _icons


class ThinkingPopup(QWidget):
    """Frameless thought bubble. Created once by Dikte, shown on busy."""

    pauseToggled = pyqtSignal(bool)  # True = paused
    stopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(None)
        self.setObjectName("ThinkingPopup")
        self._paused = False
        self._log = []
        self._start_ts = None

        # window flags like Overlay but with input (buttons need clicks)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        import sys
        if sys.platform not in ("darwin", "win32"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(380, 176)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        card_l = QVBoxLayout(self.card)
        card_l.setContentsMargins(14, 12, 14, 12)
        card_l.setSpacing(8)

        # header
        head = QHBoxLayout()
        head.setSpacing(8)
        self.dot = QLabel(self.card)
        self.dot.setFixedSize(8, 8)
        self.dot.setProperty("dot", "info")
        head.addWidget(self.dot)
        self.title = QLabel("Dusunuyor…", self.card)
        self.title.setObjectName("thinkingTitle")
        _title_font = QFont(self.title.font())
        _title_font.setPointSizeF(13.0)
        _title_font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(_title_font)
        head.addWidget(self.title, 1)
        self.elapsed_lbl = QLabel("00:00", self.card)
        self.elapsed_lbl.setObjectName("meta")
        self.elapsed_lbl.setProperty("mono", "true")
        head.addWidget(self.elapsed_lbl)
        # spinner placeholder
        self.spinner = QLabel(self.card)
        self.spinner.setFixedSize(14, 14)
        head.addWidget(self.spinner)
        card_l.addLayout(head)

        # stage line
        self.stage_lbl = QLabel("", self.card)
        self.stage_lbl.setWordWrap(True)
        self.stage_lbl.setObjectName("thinkingStage")
        _stage_font = QFont(self.stage_lbl.font())
        _stage_font.setPointSizeF(12.5)
        self.stage_lbl.setFont(_stage_font)
        card_l.addWidget(self.stage_lbl)

        # log area
        self.log_area = QLabel("", self.card)
        self.log_area.setWordWrap(True)
        self.log_area.setObjectName("meta")
        self.log_area.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log_area.setMinimumHeight(42)
        # subtle separator (styled by app QSS QFrame#rowSeparator)
        self.sep = QFrame(self.card)
        self.sep.setObjectName("rowSeparator")
        self.sep.setFixedHeight(1)
        card_l.addWidget(self.sep)
        card_l.addWidget(self.log_area)

        # actions
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.pause_btn = QPushButton(self.card)
        self.pause_btn.setText("Duraklat")
        self.pause_btn.setProperty("variant", "ghost")
        self.pause_btn.setProperty("size", "sm")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setIcon(_icons.icon("pause", 13))
        btn_row.addWidget(self.pause_btn)
        self.stop_btn = QPushButton(self.card)
        self.stop_btn.setText("Durdur")
        self.stop_btn.setProperty("variant", "danger")
        self.stop_btn.setProperty("size", "sm")
        self.stop_btn.clicked.connect(self.stopRequested.emit)
        self.stop_btn.setIcon(_icons.icon("stop", 13))
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        self.close_btn = QPushButton(self.card)
        self.close_btn.setText("Kapat")
        self.close_btn.setProperty("variant", "secondary")
        self.close_btn.setProperty("size", "sm")
        self.close_btn.clicked.connect(self.hide_popup)
        btn_row.addWidget(self.close_btn)
        card_l.addLayout(btn_row)

        # apply theme QSS
        self._apply_theme()
        # timer for elapsed + spinner
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._on_tick)
        self._phase = 0

        self._concealed = True
        self.hide()

    def _apply_theme(self):
        """Refresh tone from the shared theme without frozen palette strings.

        Card/dot/separator/timestamps are styled by objectName + dynamic
        properties (``QFrame#card``, ``QLabel[dot="info"]``,
        ``QFrame#rowSeparator``, ``QLabel#meta``) from the application QSS;
        muted text roles fall back to QPalette so offscreen windows without a
        global stylesheet keep the same professional tone. Called live by the
        settings UI after a theme switch.
        """
        try:
            c = _theme.palette()
        except Exception:
            c = {}
        self.card.setObjectName("card")
        self.dot.setProperty("dot", "idle" if self._paused else "info")
        self.sep.setObjectName("rowSeparator")
        self.elapsed_lbl.setObjectName("meta")
        self.elapsed_lbl.setProperty("mono", "true")
        self.log_area.setObjectName("meta")
        try:
            fg = QColor(c.get("fg", "#E7F0EC"))
            fg2 = QColor(c.get("fg2", "#A8BCB5"))
            fg3 = QColor(c.get("fg3", "#7C918A"))
            for lbl, col in ((self.title, fg), (self.stage_lbl, fg2),
                             (self.elapsed_lbl, fg3), (self.log_area, fg3)):
                pal = lbl.palette()
                pal.setColor(pal.ColorRole.WindowText, col)
                pal.setColor(pal.ColorRole.Text, col)
                lbl.setPalette(pal)
        except Exception:
            pass
        # re-polish dynamic properties
        try:
            for w in (self.card, self.dot, self.sep,
                      self.elapsed_lbl, self.log_area,
                      self.title, self.stage_lbl):
                self.style().unpolish(w)
                self.style().polish(w)
        except Exception:
            pass

    # ---- public API ----
    def show_thinking(self, initial_stage="Dusunuyor…"):
        self._log.clear()
        self._start_ts = time.monotonic()
        self.stage_lbl.setText(initial_stage)
        self.title.setText("Dusunuyor…")
        self._paused = False
        try:
            self.dot.setProperty("dot", "info")
            self.style().unpolish(self.dot)
            self.style().polish(self.dot)
        except Exception:
            pass
        self.pause_btn.setText("Duraklat")
        self.pause_btn.setIcon(_icons.icon("pause", 13))
        self._update_log()
        self._appear()

    def push_stage(self, stage_text):
        # keep last 6 stages
        ts = time.strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {stage_text}")
        if len(self._log) > 6:
            self._log.pop(0)
        self.stage_lbl.setText(stage_text)
        self._update_log()
        if self._concealed:
            self._appear()
        else:
            self.update()

    def set_paused(self, paused):
        self._paused = paused
        self.pause_btn.setText("Devam" if paused else "Duraklat")
        self.pause_btn.setIcon(_icons.icon("play" if paused else "pause", 13))
        self.title.setText("Duraklatildi" if paused else "Dusunuyor…")
        try:
            self.dot.setProperty("dot", "idle" if paused else "info")
            self.style().unpolish(self.dot)
            self.style().polish(self.dot)
        except Exception:
            pass
        self.pauseToggled.emit(paused)

    def hide_popup(self):
        self._tick.stop()
        self._concealed = True
        self.hide()

    # ---- internals ----
    def _update_log(self):
        self.log_area.setText("\n".join(self._log[-4:]))

    def _appear(self):
        self._concealed = False
        self._reposition()
        self.show()
        self.raise_()
        if not self._tick.isActive():
            self._tick.start()

    def _reposition(self):
        # place near overlay corner but slightly offset so both visible
        # try to find overlay corner from config if available, default bottom-left
        corner = "bottom-left"
        try:
            import config as cfg
            corner = cfg.Config().get("overlay_corner", "bottom-left")
        except Exception:
            pass
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        m = 28
        x = area.left() + m if "left" in corner else area.right() - self.width() - m
        # stack above overlay: overlay is HEIGHT 56 + GAP 10, so popup sits 80px above
        y = area.bottom() - self.height() - m - 70 if "bottom" in corner else area.top() + m + 70
        self.move(int(x), int(y))

    def _toggle_pause(self):
        self.set_paused(not self._paused)
        self.pauseToggled.emit(self._paused)

    def _on_tick(self):
        self._phase += 0.12
        # update elapsed
        if self._start_ts is not None and not self._paused:
            secs = int(time.monotonic() - self._start_ts)
            self.elapsed_lbl.setText(f"{secs//60:02d}:{secs%60:02d}")
        # dot keeps its themed QLabel[dot="info"] tone (no per-tick QSS churn);
        # spinner repaint preserves the tick-driven activity cue.
        self.spinner.update()

    def paintEvent(self, ev):
        # card handles background, no extra
        super().paintEvent(ev)

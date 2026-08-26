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
        head.addWidget(self.dot)
        self.title = QLabel("Dusunuyor…", self.card)
        self.title.setStyleSheet("font-size: 13px; font-weight: 600;")
        head.addWidget(self.title, 1)
        self.elapsed_lbl = QLabel("00:00", self.card)
        self.elapsed_lbl.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        head.addWidget(self.elapsed_lbl)
        # spinner placeholder
        self.spinner = QLabel(self.card)
        self.spinner.setFixedSize(14, 14)
        head.addWidget(self.spinner)
        card_l.addLayout(head)

        # stage line
        self.stage_lbl = QLabel("", self.card)
        self.stage_lbl.setWordWrap(True)
        self.stage_lbl.setStyleSheet("font-size: 12.5px;")
        card_l.addWidget(self.stage_lbl)

        # log area
        self.log_area = QLabel("", self.card)
        self.log_area.setWordWrap(True)
        self.log_area.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log_area.setMinimumHeight(42)
        # subtle separator
        self.sep = QFrame(self.card)
        self.sep.setFixedHeight(1)
        card_l.addWidget(sep)
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
        c = _theme.palette()
        self.card.setStyleSheet(
            f"QFrame#card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}"
        )
        self.dot.setStyleSheet(f"background: {c['info']}; border-radius: 4px;")
        self.elapsed_lbl.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {c['fg3']};")
        self.log_area.setStyleSheet(f"font-size: 11.5px; color: {c['fg3']};")
        self.sep.setStyleSheet(f"background: {c['border']}; border: none;")
        # re-polish
        self.style().unpolish(self.card)
        self.style().polish(self.card)
        self.style().unpolish(self.dot)
        self.style().polish(self.dot)

    # ---- public API ----
    def show_thinking(self, initial_stage="Dusunuyor…"):
        self._log.clear()
        self._start_ts = time.monotonic()
        self.stage_lbl.setText(initial_stage)
        self.title.setText("Dusunuyor…")
        self._paused = False
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
        # spinner via stylesheet trick: rotate dot opacity
        # simple: pulse dot
        pulse = 0.5 + 0.5 * (abs((self._phase % 6.28) - 3.14) / 3.14)  # not used, placeholder
        # trigger repaint for spinner custom draw if needed
        self.spinner.update()
        # dot pulse
        alpha = 0.55 + 0.45 * (0.5 + 0.5 * __import__("math").sin(self._phase * 1.6))
        c = _theme.palette().get("info", "#82B9CE")
        # keep dot color with alpha via stylesheet
        # we can't animate alpha via stylesheet easily, so just update style each tick (light cost)
        try:
            self.dot.setStyleSheet(f"background: {c}; border-radius: 4px; opacity: {alpha:.2f};")
        except Exception:
            pass

    def paintEvent(self, ev):
        # card handles background, no extra
        super().paintEvent(ev)

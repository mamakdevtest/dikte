"""The small recording indicator that appears in a screen corner without taking focus."""

import math
import sys
import time
from collections import deque

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QByteArray, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QFontMetrics
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QWidget, QApplication

try:
    from i18n import t
except Exception:
    def t(s, **_k):
        return s.format(**_k) if _k else s

BARS = 31
HEIGHT = 72
MIN_WIDTH = 320
MAX_WIDTH = 620
MARGIN = 28
GAP = 10        # between two indicators sharing a corner

# The live pill has a fixed spacious composition so the waveform never moves
# when Pause changes to Resume. New samples enter at the right edge.
_LIVE_WIDTH = 520
_PILL_RADIUS = 24
_WAVE_LEFT = 78.0
_WAVE_GAP = 16.0
_TIMER_WIDTH = 76.0
_ACTION_SLOT = 108.0  # 1.5x the original 72 to host Pause+Stop
_ACTION_HIT = 48.0
_ACTION_VISUAL = 40.0
_STOP_HIT = 48.0
_STOP_VISUAL = 40.0
_ACTION_GAP = 8.0
_THINKING_HEIGHT = 36.0
_THINKING_GAP = 10.0
_FRAME_MS = 25
_QUIET_FRAME_MS = 120
_BUSY_FRAME_MS = 90

# Waveform model constants
_GATE = 0.045
_BASELINE = 0.015
_ATTACK_ALPHA = 0.55
_RELEASE_ALPHA = 0.12
# Audio chunks arrive roughly every 64 ms, while the overlay paints every
# 25 ms. These frame-sized steps keep the visual response smooth between
# signal deliveries instead of jumping once per audio chunk.
_FRAME_ATTACK_ALPHA = 0.28
_FRAME_RELEASE_ALPHA = 0.14
_VISUAL_EPSILON = 0.0005
_REVEAL_MS = 220


def _hex_to_qcolor(hex_str, alpha=255):
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


def _mix_qcolor(hex_a, hex_b, share_a, alpha=255):
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    r = round(a[0] * share_a + b[0] * (1 - share_a))
    g = round(a[1] * share_a + b[1] * (1 - share_a))
    b_ = round(a[2] * share_a + b[2] * (1 - share_a))
    c = QColor(r, g, b_)
    c.setAlpha(alpha)
    return c


_palette_cache = None
_palette_cache_key = None

def _palette_colors():
    global _palette_cache, _palette_cache_key
    theme_name = None
    p = None
    try:
        from ui import theme as _theme
        theme_name = _theme.current()
        if _palette_cache is not None and _palette_cache_key == theme_name:
            return _palette_cache
        p = _theme.palette()
    except Exception:
        theme_name = theme_name or "dark"
        if _palette_cache is not None and _palette_cache_key == theme_name:
            return _palette_cache
        p = {
            "field": "#142123", "surface": "#1B292B", "surface2": "#223234",
            "border": "#314548",
            "fg": "#E7F0EC", "fg3": "#7C918A", "terra": "#E08A72",
            "sageDark": "#A8C7B5", "info": "#82B9CE", "ok": "#75C59B",
            "err": "#DF8582", "warn": "#D8B870",
        }
    BG = _mix_qcolor(p["field"], p["surface"], 0.92, 238)
    BORDER = _hex_to_qcolor(p["border"], 255)
    TEXT = _hex_to_qcolor(p["fg"])
    MUTED = _hex_to_qcolor(p["fg3"])
    REC = _hex_to_qcolor(p["terra"])
    ASK = _hex_to_qcolor(p["sageDark"])
    BUSY = _hex_to_qcolor(p["info"])
    OK = _hex_to_qcolor(p["ok"])
    ERR = _hex_to_qcolor(p["err"])
    WARN = _hex_to_qcolor(p["warn"])
    THEM = _hex_to_qcolor(p["info"])
    STATE_COLORS = {"recording": REC, "asking": ASK, "meeting": REC, "busy": BUSY,
                    "done": OK, "warning": WARN, "error": ERR}
    out = {
        "BG": BG, "SURFACE2": _hex_to_qcolor(p["surface2"]),
        "BORDER": BORDER, "TEXT": TEXT, "MUTED": MUTED,
        "REC": REC, "ASK": ASK, "BUSY": BUSY, "OK": OK, "ERR": ERR, "WARN": WARN,
        "THEM": THEM, "STATE_COLORS": STATE_COLORS,
    }
    _palette_cache = out
    _palette_cache_key = theme_name
    return out


# Legacy constants kept for import compatibility — now derived from theme
_tmp = _palette_colors()
BG = _tmp["BG"]
BORDER = _tmp["BORDER"]
TEXT = _tmp["TEXT"]
MUTED = _tmp["MUTED"]
REC = _tmp["REC"]
BUSY = _tmp["BUSY"]
OK = _tmp["OK"]
ERR = _tmp["ERR"]
WARN = _tmp["WARN"]
THEM = _tmp["THEM"]
ASK = _tmp["ASK"]
STATE_COLORS = _tmp["STATE_COLORS"]
LIVE = ("recording", "asking", "meeting")
PAUSED_STATE = "paused"

# ---- deterministic helpers for tests ----

def _gate(raw, gate=_GATE, baseline=_BASELINE):
    """Soft-knee gate: silence near baseline, then remapped to 1.0 with no jump.

    At gate (0.045) target = baseline+0.02 (=0.035), then ramps to 1.0.
    """
    raw = max(0.0, min(1.0, float(raw)))
    if raw <= gate:
        # no jump: baseline + proportional small range 0.02
        return baseline + (raw / gate) * 0.02 if gate > 0 else baseline
    # continuous soft-knee: start at baseline+0.02, map to 1
    knee = baseline + 0.02
    return knee + ((raw - gate) / (1 - gate)) * (1 - knee)


def _smooth_step(prev, target, attack=_ATTACK_ALPHA, release=_RELEASE_ALPHA):
    """EMA with fast attack, soft release."""
    alpha = attack if target > prev else release
    return prev + alpha * (target - prev)


def _easing(t):
    """Cubic ease-out 1-(1-t)^3, t in [0,1]."""
    t = max(0.0, min(1.0, float(t)))
    return 1 - (1 - t) ** 3


def _envelope(bars=BARS):
    """Fade older bars slightly while keeping the newest edge prominent."""
    if bars <= 1:
        return [1.0]
    return [0.68 + 0.32 * i / (bars - 1) for i in range(bars)]


class WaveformState:
    """Bounded audio history with a smooth, right-to-left display stream.

    History is bounded deque(maxlen=BARS) of (ts, raw, smoothed) only from
    push() calls. Each new gated sample is appended at the right edge; the
    render frame interpolates every bar toward the shifted target row.
    """

    def __init__(self, bars=BARS):
        self.bars = bars
        self._deque = deque(maxlen=bars)
        self._envelope = tuple(_envelope(bars))
        self._smoothed = _BASELINE
        self._target = _BASELINE
        self._history_levels = deque([_BASELINE] * bars, maxlen=bars)
        self._target_levels = tuple(_BASELINE for _ in range(bars))
        self._smoothed_levels = tuple(_BASELINE for _ in range(bars))
        self._paused = False
        self._display_levels = tuple(_BASELINE for _ in range(bars))
        self._refresh_display_levels()

    @staticmethod
    def _display_value(value):
        normalized = max(0.0, min(1.0, float(value)))
        if normalized <= _BASELINE:
            return _BASELINE
        # A gentle display curve keeps quiet speech legible without making
        # loud input pin every bar to the top. Audio data is untouched.
        share = (normalized - _BASELINE) / (1.0 - _BASELINE)
        return _BASELINE + share ** 0.72 * (1.0 - _BASELINE)

    def _refresh_display_levels(self):
        """Update the immutable display tuple only when the model changes."""
        self._display_levels = tuple(
            max(0.0, min(1.0, self._display_value(level) * weight))
            for level, weight in zip(self._smoothed_levels, self._envelope)
        )

    def push(self, raw):
        raw = max(0.0, min(1.0, float(raw)))
        if self._paused:
            # inactive: stay at baseline, no attack
            self._target = _BASELINE
            self._smoothed = _BASELINE
        else:
            # Audio delivery and visual rendering have different cadences.
            # Only update the target here; the frame scheduler owns motion.
            self._target = _gate(raw)
            self._history_levels.append(self._target)
            self._target_levels = tuple(self._history_levels)
        ts = time.monotonic()
        self._deque.append((ts, raw, self._smoothed))
        return self._smoothed

    def advance(self):
        """Move every visible bar one small step toward its new target row."""
        if self._paused:
            return False
        before = self._smoothed_levels
        next_levels = []
        for previous, target in zip(before, self._target_levels):
            value = _smooth_step(
                previous,
                target,
                attack=_FRAME_ATTACK_ALPHA,
                release=_FRAME_RELEASE_ALPHA,
            )
            if abs(target - value) <= _VISUAL_EPSILON:
                value = target
            next_levels.append(value)
        self._smoothed_levels = tuple(next_levels)
        self._smoothed = self._smoothed_levels[-1] if next_levels else _BASELINE
        if self._smoothed_levels == before:
            return False
        self._refresh_display_levels()
        return True

    def get_display_levels(self):
        """Cached tuple of BARS values: smoothed * envelope, normalized 0..1."""
        # Use current smoothed scalar * envelope for fixed spatial bars
        return self._display_levels

    def get_smoothed(self):
        return self._smoothed

    @property
    def has_pending(self):
        """Whether another visual frame is needed to reach the target."""
        return any(
            abs(target - current) > _VISUAL_EPSILON
            for current, target in zip(self._smoothed_levels, self._target_levels)
        )

    def reset(self):
        self._deque.clear()
        self._smoothed = _BASELINE
        self._target = _BASELINE
        self._history_levels = deque([_BASELINE] * self.bars, maxlen=self.bars)
        self._target_levels = tuple(_BASELINE for _ in range(self.bars))
        self._smoothed_levels = tuple(_BASELINE for _ in range(self.bars))
        self._paused = False
        self._refresh_display_levels()

    def set_paused(self, paused: bool):
        self._paused = bool(paused)
        if self._paused:
            # keep history, but settle to baseline
            self._target = _BASELINE
            self._smoothed = _BASELINE
            self._target_levels = tuple(_BASELINE for _ in range(self.bars))
            self._smoothed_levels = tuple(_BASELINE for _ in range(self.bars))
            self._refresh_display_levels()

    @property
    def paused(self):
        return self._paused

    @property
    def history(self):
        return list(self._deque)


class Overlay(QWidget):
    """One indicator. Give it `below` and it stacks on top of that one instead
    of covering it, which is what lets a dictation and a command to the agent be
    under way at the same time and still both be visible."""

    pauseRequested = pyqtSignal()
    resumeRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    thinkingChanged = pyqtSignal(str)

    def __init__(self, corner="bottom-left", below=None, dismissable=False, interactive_live=False):
        super().__init__(None)
        self.corner = corner
        self.below = below
        self.dismissable = dismissable
        self.interactive_live = interactive_live
        self.muted = False
        self._stacked = False
        self.state = "idle"
        self.message = ""
        self.levels = [0.0] * BARS
        self.levels2 = [0.0] * BARS   # the other side, while a meeting records
        self.seconds = 0.0
        self._phase = 0.0
        self._concealed = True
        self._paused = False
        self._reveal_t0 = 0.0
        self._reveal_progress = 1.0
        self._pause_rect = QRectF()
        self._hover_pause = False
        self._button_pressed = False
        self._waveform_dirty = True
        self._timer_dirty = True
        self._layout_cache = None
        self._layout_cache_key = None
        self._action_renderer = None
        self._action_renderer_key = None
        self._label_font_cache = None
        self._timer_font_cache = None
        self._last_displayed_second = -1
        self._timer_text = "0:00"
        self._wave = WaveformState(BARS)
        self._wave2 = WaveformState(BARS)
        self._thinking_text = ""
        self._thinking_font_cache = None
        self._stop_rect = QRectF()
        self._hover_stop = False
        self._stop_pressed = False

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if sys.platform not in ("darwin", "win32"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        # Interactive live needs to receive mouse; dismissable also needs it.
        # Otherwise stay transparent to input.
        needs_input = bool(dismissable or interactive_live)
        if needs_input:
            # point cursor for interactive parts
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if interactive_live:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(MIN_WIDTH, HEIGHT)

        self._anim = QTimer(self)
        self._anim.setInterval(_FRAME_MS)
        self._anim.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim.timeout.connect(self._tick)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._conceal)

    # ---- public API --------------------------------------------------

    def show_recording(self, asking=False):
        """The same ribbon either way, in a different colour when what is being
        recorded is a command for Claude rather than something to paste."""
        self.state = "asking" if asking else "recording"
        self.message = ""
        self.seconds = 0.0
        self._paused = False
        self._wave.reset()
        self._wave2.reset()
        self._reveal_t0 = time.monotonic()
        self._reveal_progress = 0.0
        self._hover_pause = False
        self._button_pressed = False
        self._waveform_dirty = True
        self._reset_timer_cache()
        # keep backwards compat levels tiny baseline
        self.levels = [0.0] * BARS
        self.levels2 = [0.0] * BARS
        self.muted = False
        self._hide_timer.stop()
        self._appear()

    def show_resumed(self, asking=False):
        """Return a paused pill to live mode without restarting its session UI."""
        self.state = "asking" if asking else "recording"
        self.message = ""
        self._paused = False
        self._wave.set_paused(False)
        self._wave2.set_paused(False)
        self._hover_pause = False
        self._button_pressed = False
        self._waveform_dirty = True
        self._hide_timer.stop()
        self._appear()

    def show_meeting(self):
        """Both channels at once: your voice up, the other side down."""
        self.state = "meeting"
        self.message = ""
        self.seconds = 0.0
        self._paused = False
        self._wave.reset()
        self._wave2.reset()
        self._reveal_t0 = time.monotonic()
        self._reveal_progress = 0.0
        self._hover_pause = False
        self._button_pressed = False
        self._waveform_dirty = True
        self._reset_timer_cache()
        self.levels = [0.0] * BARS
        self.levels2 = [0.0] * BARS
        self._hide_timer.stop()
        self._appear()

    def show_busy(self, message):
        if self.muted:
            self.message = message
            return
        self.state = "busy"
        self.message = message
        self._hover_pause = False
        self._hide_timer.stop()
        self._appear()

    def show_done(self, message="", msec=2000):
        self._finish("done", message, msec)

    def show_warning(self, message, msec=9000):
        self._finish("warning", message, msec)

    def show_error(self, message, msec=6000):
        self._finish("error", message, msec)

    def _finish(self, state, message, msec):
        self.muted = False
        self.state = state
        self.message = message
        self._hover_pause = False
        self._button_pressed = False
        self._hover_stop = False
        self._stop_pressed = False
        # clear thinking when leaving busy
        if self._thinking_text:
            self._thinking_text = ""
            self._layout_cache = None
        # leaving LIVE, ensure reveal is complete
        self._reveal_progress = 1.0
        self._reveal_t0 = 0.0
        self._appear()
        self._hide_timer.start(msec)

    def show_paused(self, message="Paused"):
        """Paused style: waveform inactive, button becomes Resume."""
        self.state = PAUSED_STATE
        self.message = message
        self._paused = True
        self._wave.set_paused(True)
        self._wave2.set_paused(True)
        # keep levels at baseline display
        self.levels = list(self._wave.get_display_levels())
        self.levels2 = list(self._wave2.get_display_levels())
        self._hover_pause = False
        self._button_pressed = False
        self._waveform_dirty = True
        self._hide_timer.stop()
        self._appear()

    def set_paused(self, paused: bool):
        paused = bool(paused)
        if self._paused == paused:
            return
        self._paused = paused
        self._wave.set_paused(paused)
        self._wave2.set_paused(paused)
        if paused:
            if self.state in LIVE:
                # keep LIVE state but flag paused
                pass
            else:
                self.state = PAUSED_STATE
        else:
            if self.state == PAUSED_STATE:
                # resume to recording? Default to recording if unknown
                self.state = "recording"
            # else keep current LIVE state
        # update display levels to baseline / resume
        if paused:
            self.levels = list(self._wave.get_display_levels())
            self.levels2 = list(self._wave2.get_display_levels())
        self._waveform_dirty = True
        self._timer_dirty = True
        self._sync_animation_timer()
        self.update()

    @property
    def is_paused(self):
        return self._paused

    # ---- thinking panel ------------------------------------------------
    def set_thinking_status(self, text: str):
        """Show the secondary thinking panel above the main pill.

        Only externally emitted progress is shown; never fabricate reasoning.
        Call with empty string to hide. Follows same corner and does not steal focus.
        """
        try:
            cleaned = (text or "").strip()
        except Exception:
            cleaned = ""
        # Elide very long text and avoid secret leakage: keep first 180 chars
        if len(cleaned) > 180:
            cleaned = cleaned[:180].rstrip() + "…"
        if cleaned == self._thinking_text:
            return
        self._thinking_text = cleaned
        if cleaned:
            # Ensure overlay is visible if thinking is set while busy
            if self.state == "busy" or self.state in LIVE:
                # Keep thinking visible; resize to include panel
                self._resize_to_content()
                self._reposition()
                self.update()
        else:
            self._resize_to_content()
            self._reposition()
            self.update()
        self.thinkingChanged.emit(cleaned)

    def clear_thinking(self):
        self.set_thinking_status("")

    def _thinking_font(self):
        if self._thinking_font_cache is None:
            font = QFont(self._label_font())
            font.setPointSizeF(8.5)
            self._thinking_font_cache = font
        return self._thinking_font_cache

    @property
    def thinking_text(self):
        return self._thinking_text

    def dismiss(self):
        self._hide_timer.stop()
        self._conceal()

    def mousePressEvent(self, event):
        if self.interactive_live and self._should_show_pause_button():
            pos = event.position() if hasattr(event, "position") else event.pos()
            try:
                pt = QPointF(pos.x(), pos.y())
            except Exception:
                pt = QPointF(float(pos.x()), float(pos.y()))
            pause_rect = self._pause_button_rect()
            stop_rect = self._stop_button_rect()
            if not pause_rect.isValid():
                pause_rect = self._pause_rect
            if not stop_rect.isValid():
                stop_rect = self._stop_rect
            if pause_rect.contains(pt):
                self._button_pressed = True
                self._stop_pressed = False
                if self._paused or self.state == PAUSED_STATE:
                    self.resumeRequested.emit()
                else:
                    self.pauseRequested.emit()
                self.update(pause_rect.toRect())
                event.accept()
                return
            if stop_rect.contains(pt):
                self._stop_pressed = True
                self._button_pressed = False
                self.stopRequested.emit()
                self.update(stop_rect.toRect())
                event.accept()
                return
        if self.dismissable and self.state == "busy":
            self.muted = True
            self.dismiss()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.interactive_live and self._should_show_pause_button():
            pos = event.position() if hasattr(event, "position") else event.pos()
            try:
                pt = QPointF(pos.x(), pos.y())
            except Exception:
                pt = QPointF(float(pos.x()), float(pos.y()))
            pause_rect = self._pause_button_rect()
            stop_rect = self._stop_button_rect()
            if not pause_rect.isValid():
                pause_rect = self._pause_rect
            if not stop_rect.isValid():
                stop_rect = self._stop_rect
            hover_pause = pause_rect.contains(pt)
            hover_stop = stop_rect.contains(pt)
            if hover_pause != self._hover_pause:
                self._hover_pause = hover_pause
                self.update(pause_rect.toRect())
            if hover_stop != self._hover_stop:
                self._hover_stop = hover_stop
                self.update(stop_rect.toRect())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._button_pressed:
            self._button_pressed = False
            self.update(self._pause_button_rect().toRect())
        if self._stop_pressed:
            self._stop_pressed = False
            self.update(self._stop_button_rect().toRect())
        event.accept()

    def leaveEvent(self, event):
        if self._hover_pause:
            self._hover_pause = False
            self.update(self._pause_button_rect().toRect())
        if self._hover_stop:
            self._hover_stop = False
            self.update(self._stop_button_rect().toRect())
        super().leaveEvent(event)

    @property
    def showing(self):
        return self.isVisible() and not self._concealed

    def push_level(self, level):
        # Clamp raw level 0-1
        level = max(0.0, min(1.0, float(level)))
        self._wave.push(level)
        # keep levels for backwards compat as display levels
        self.levels = list(self._wave.get_display_levels())
        if self._wave.has_pending:
            self._waveform_dirty = True
            self._sync_animation_timer()

    def push_levels(self, mine, theirs):
        mine = max(0.0, min(1.0, float(mine)))
        theirs = max(0.0, min(1.0, float(theirs)))
        self._wave.push(mine)
        self._wave2.push(theirs)
        self.levels = list(self._wave.get_display_levels())
        self.levels2 = list(self._wave2.get_display_levels())
        if self._wave.has_pending or self._wave2.has_pending:
            self._waveform_dirty = True
            self._sync_animation_timer()

    def set_seconds(self, seconds):
        self.seconds = seconds
        displayed_second = max(0, int(seconds))
        if displayed_second == self._last_displayed_second:
            return
        self._last_displayed_second = displayed_second
        self._timer_text = self._format_time(displayed_second)
        self._timer_dirty = True
        if self.showing and (self.state in LIVE or self.state == PAUSED_STATE):
            self.update(self._layout()["timer_rect"].toRect())

    # ---- internals -----------------------------------------------------

    def _should_show_pause_button(self):
        if not self.interactive_live:
            return False
        # Meeting recording has no pause API; do not expose a dead control.
        return self.state in ("recording", "asking", PAUSED_STATE) or self._paused

    def _should_show_stop_button(self):
        # Same condition as pause — Stop is for the same recording session
        return self._should_show_pause_button()

    def _action_group_rect(self):
        if not self._should_show_pause_button():
            return QRectF()
        group_w = _ACTION_HIT + _ACTION_GAP + _STOP_HIT
        x = self.width() - group_w - 20.0
        offset = _THINKING_HEIGHT + _THINKING_GAP if (self._thinking_text and self.state == "busy") else 0
        y = offset + (HEIGHT - _ACTION_HIT) / 2.0
        return QRectF(x, y, group_w, _ACTION_HIT)

    def _pause_button_rect(self):
        if not self._should_show_pause_button():
            return QRectF()
        group = self._action_group_rect()
        return QRectF(group.left(), group.top(), _ACTION_HIT, _ACTION_HIT)

    def _stop_button_rect(self):
        if not self._should_show_stop_button():
            return QRectF()
        group = self._action_group_rect()
        return QRectF(group.left() + _ACTION_HIT + _ACTION_GAP, group.top(), _STOP_HIT, _STOP_HIT)

    def _action_rect(self):
        # Backward compat: return pause rect
        return self._pause_button_rect()

    def _layout(self):
        """Return stable logical subregions, rebuilding only after resize/state."""
        show_action = self._should_show_pause_button()
        thinking = bool(self._thinking_text) and self.state == "busy"
        key = (self.width(), self.height(), show_action, self.state == "meeting", thinking)
        if self._layout_cache is not None and self._layout_cache_key == key:
            return self._layout_cache

        # Main pill vertical offset when thinking panel is visible
        offset = _THINKING_HEIGHT + _THINKING_GAP if thinking else 0.0
        main_h = HEIGHT
        action = self._action_group_rect() if show_action else QRectF()
        timer_right = self.width() - 20.0 - (_ACTION_SLOT if show_action else 0.0)
        timer = QRectF(timer_right - _TIMER_WIDTH, offset, _TIMER_WIDTH, main_h)
        wave_right = timer.left() - _WAVE_GAP
        wave_left = min(_WAVE_LEFT, max(0.0, wave_right))
        available = max(1.0, min(float(self.width()) - wave_left,
                                   wave_right - wave_left))
        preferred_gap = 3.5
        bar_w = min(5.0, max(3.0,
                             (available - (BARS - 1) * preferred_gap) / BARS))
        if BARS * bar_w + (BARS - 1) * preferred_gap > available:
            # Keep the narrow-resize contract: bars never escape the widget,
            # even while a transient overlay is being squeezed very small.
            gap = 0.15
            bar_w = max(0.25, (available - (BARS - 1) * gap) / BARS)
        else:
            gap = preferred_gap
        step = bar_w + gap
        bars = tuple(QRectF(wave_left + i * step, offset, bar_w, 0.0)
                     for i in range(BARS))
        layout = {
            "indicator": QRectF(18.0, offset, 24.0, main_h),
            "waveform": QRectF(wave_left, offset, available, main_h),
            "timer_rect": timer,
            "action": action,
            "pause": self._pause_button_rect(),
            "stop": self._stop_button_rect(),
            "bars": bars,
            "thinking": QRectF(0.0, 0.0, float(self.width()), _THINKING_HEIGHT) if thinking else QRectF(),
            "main_top": offset,
        }
        self._layout_cache_key = key
        self._layout_cache = layout
        return layout

    def _update_region(self, name):
        rect = self._layout().get(name, QRectF())
        if rect.isValid():
            self.update(rect.toRect().adjusted(-2, -2, 2, 2))

    @staticmethod
    def _format_time(total_seconds):
        mins, secs = divmod(max(0, int(total_seconds)), 60)
        hours, mins = divmod(mins, 60)
        return f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"

    def _reset_timer_cache(self):
        self._last_displayed_second = -1
        self._timer_text = "0:00"
        self._timer_dirty = True

    def _sync_animation_timer(self):
        """Use one scheduler, and stop it entirely in static/paused states."""
        revealing = self._reveal_t0 != 0.0 and self._reveal_progress < 1.0
        is_live = self.state in LIVE and not self._paused
        if not self.showing or self.state == "hidden":
            self._anim.stop()
            return
        if revealing:
            interval = _FRAME_MS
        elif is_live:
            interval = _FRAME_MS if self._waveform_dirty else _QUIET_FRAME_MS
        elif self.state == "busy":
            interval = _BUSY_FRAME_MS
        else:
            self._anim.stop()
            return
        if self._anim.interval() != interval:
            self._anim.setInterval(interval)
        if not self._anim.isActive():
            self._anim.start()

    def _appear(self):
        self._resize_to_content()
        self._reposition()
        if not self.isVisible():
            self.show()
        if self._concealed:
            self.raise_()
            self._concealed = False
        # init reveal if entering LIVE or paused
        if self.state in LIVE or self.state == PAUSED_STATE:
            # A paused/resumed transition keeps a completed reveal completed.
            if self._reveal_progress < 1.0 and self._reveal_t0 == 0.0:
                self._reveal_t0 = time.monotonic()
        else:
            self._reveal_progress = 1.0
            self._reveal_t0 = 0.0
        self._sync_animation_timer()
        self.update()

    def _conceal(self):
        self._anim.stop()
        self.state = "hidden"
        self._concealed = True
        self._paused = False
        self._wave.set_paused(False)
        self._wave2.set_paused(False)
        self._reveal_progress = 1.0
        self._reveal_t0 = 0.0
        if self._thinking_text:
            self._thinking_text = ""
            self._layout_cache = None
        self.update()
        if self.dismissable:
            self.resize(1, 1)
        # keep interactive_live size? Still shrink only if dismissable

    def resizeEvent(self, event):
        self._layout_cache = None
        self._layout_cache_key = None
        super().resizeEvent(event)

    def _resize_to_content(self):
        if self.state in LIVE or self.state == PAUSED_STATE:
            width = _LIVE_WIDTH
        else:
            metrics = QFontMetrics(self._label_font())
            extra = 76 + (18 if self._can_dismiss else 0)
            width = max(MIN_WIDTH,
                        min(MAX_WIDTH, metrics.horizontalAdvance(self.message) + extra))
        height = HEIGHT
        if self._thinking_text and self.state == "busy":
            height = int(HEIGHT + _THINKING_GAP + _THINKING_HEIGHT)
        self.resize(int(width), int(height))

    def _reposition(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        left = "left" in self.corner
        top = "top" in self.corner
        self._stacked = self.below is not None and self.below.showing
        step = (self.below.height() + GAP) if self._stacked else 0
        x = area.left() + MARGIN if left else area.right() - self.width() - MARGIN
        y = (area.top() + MARGIN + step if top
             else area.bottom() - self.height() - MARGIN - step)
        self.move(int(x), int(y))

    def _tick(self):
        revealing = self._reveal_t0 != 0.0 and self._reveal_progress < 1.0
        if revealing:
            elapsed = (time.monotonic() - self._reveal_t0) * 1000.0
            prog = min(1.0, elapsed / _REVEAL_MS)
            self._reveal_progress = _easing(prog)
            if prog >= 1.0:
                self._reveal_t0 = 0.0

        if self.below is not None and self.below.showing != self._stacked:
            self._reposition()

        if revealing:
            self._update_region("waveform")
        is_paused = self._paused or self.state == PAUSED_STATE
        if is_paused:
            self._sync_animation_timer()
            return

        self._phase += 0.12
        if self.state in LIVE:
            waveform_changed = self._wave.advance()
            if self.state == "meeting":
                waveform_changed = self._wave2.advance() or waveform_changed
            if waveform_changed:
                self.levels = list(self._wave.get_display_levels())
                if self.state == "meeting":
                    self.levels2 = list(self._wave2.get_display_levels())
                self._waveform_dirty = True
            if self._waveform_dirty:
                self._update_region("waveform")
                self._waveform_dirty = (
                    self._wave.has_pending
                    or (self.state == "meeting" and self._wave2.has_pending)
                )
            # The dot remains subtly alive, but quiet input drops the render
            # cadence to _QUIET_FRAME_MS via the single scheduler.
            self._update_region("indicator")
        elif self.state == "busy":
            self._update_region("indicator")
        self._sync_animation_timer()

    def _label_font(self):
        if self._label_font_cache is None:
            font = QFont(self.font())
            font.setPointSizeF(10.5)
            self._label_font_cache = font
        return self._label_font_cache

    def _timer_font(self):
        if self._timer_font_cache is None:
            font = QFont(self._label_font())
            font.setPointSizeF(10.0)
            font.setFamilies(["JetBrains Mono", "Cascadia Code", "monospace"])
            self._timer_font_cache = font
        return self._timer_font_cache

    # ---- painting --------------------------------------------------

    def paintEvent(self, _event):
        if self.state == "hidden":
            return
        cols = _palette_colors()
        bg = cols["BG"]
        border = cols["BORDER"]
        muted = cols["MUTED"]
        state_colors = cols["STATE_COLORS"]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Thinking panel above main pill, if any (only when busy)
        thinking = bool(self._thinking_text) and self.state == "busy"
        offset = _THINKING_HEIGHT + _THINKING_GAP if thinking else 0.0
        if thinking:
            thinking_rect = QRectF(0.5, 0.5, self.width() - 1, _THINKING_HEIGHT - 1)
            painter.setPen(QPen(border, 1))
            painter.setBrush(bg)
            painter.drawRoundedRect(thinking_rect, 10, 10)
            # Thinking text
            painter.setFont(self._thinking_font())
            c = QColor(cols["TEXT"])
            c.setAlpha(230)
            painter.setPen(c)
            # Elide long text
            metrics = QFontMetrics(self._thinking_font())
            text = metrics.elidedText(self._thinking_text, Qt.TextElideMode.ElideRight, int(thinking_rect.width() - 24))
            painter.drawText(QRectF(thinking_rect.left() + 12, thinking_rect.top(), thinking_rect.width() - 24, thinking_rect.height()),
                             int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)

        # Main pill
        main_rect = QRectF(0.5, offset + 0.5, self.width() - 1, HEIGHT - 1)
        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(main_rect, _PILL_RADIUS, _PILL_RADIUS)

        accent = state_colors.get(self.state, muted)
        if self.state == PAUSED_STATE:
            accent = cols["ASK"]
        self._draw_indicator(painter, accent)

        if self.state in LIVE or self.state == PAUSED_STATE:
            self._draw_waveform(painter, accent)
            self._draw_time(painter)
            if self._should_show_pause_button():
                self._draw_pause_button(painter)
                self._draw_stop_button(painter)
        else:
            self._draw_message(painter)
            if self._can_dismiss:
                self._draw_dismiss(painter)

    def _draw_indicator(self, painter, accent):
        layout = self._layout()
        cx, cy = layout["indicator"].center().x(), layout["indicator"].center().y()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.state in LIVE or self.state == PAUSED_STATE:
            if self._paused or self.state == PAUSED_STATE:
                color = QColor(accent)
                color.setAlpha(220)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(cx, cy), 5.5, 5.5)
            else:
                pulse = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(self._phase * 1.6))
                color = QColor(accent)
                color.setAlphaF(0.78 + 0.22 * pulse)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(cx, cy), 5.5, 5.5)
        elif self.state == "busy":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(accent), 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            span = 100 * 16
            start = int(-self._phase * 320) % (360 * 16)
            painter.drawArc(QRectF(cx - 8, cy - 8, 16, 16), start, span)
        elif self.state == "done":
            pen = QPen(accent, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(
                QPointF(cx - 7, cy), QPointF(cx - 2, cy + 5.5), QPointF(cx + 7.5, cy - 6)
            )
        elif self.state == "warning":
            pen = QPen(accent, 2.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(cx, cy - 7), QPointF(cx, cy + 1.5))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(QPointF(cx, cy + 6), 1.5, 1.5)
        else:  # error
            pen = QPen(accent, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(cx - 6, cy - 6), QPointF(cx + 6, cy + 6))
            painter.drawLine(QPointF(cx + 6, cy - 6), QPointF(cx - 6, cy + 6))

    def _bars(self):
        """(x of the first bar, bar width, distance between two bars)."""
        bars = self._layout()["bars"]
        if not bars:
            return _WAVE_LEFT, 0.0, 0.0
        return bars[0].left(), bars[0].width(), bars[1].left() - bars[0].left()

    @staticmethod
    def _bar_colour(shaped, accent):
        # Kept for compat, new waveform uses gradient
        muted = _palette_colors()["MUTED"]
        color = QColor(accent if shaped > 0.04 else muted)
        color.setAlphaF(0.35 + 0.65 * min(1.0, shaped * 2.2))
        return color

    def _smooth_levels(self, levels):
        """3-point moving average for silky motion, preserves edges.
        Kept for compatibility but no longer used for LIVE rendering."""
        if len(levels) < 3:
            return list(levels)
        out = []
        for i, v in enumerate(levels):
            if i == 0 or i == len(levels) - 1:
                out.append(v)
            else:
                out.append((levels[i - 1] * 0.25 + v * 0.5 + levels[i + 1] * 0.25))
        return out

    def _draw_waveform(self, painter, accent=None):
        cols = _palette_colors()
        if accent is None:
            accent = cols["REC"]
        if self.state == "meeting":
            self._draw_dual_waveform(painter)
            return
        layout = self._layout()
        bars = layout["bars"]
        bar_w = bars[0].width()
        # Use layout's vertical center (accounts for thinking offset)
        mid = layout["waveform"].center().y()
        # WaveformState exposes a cached immutable tuple; no list is built here.
        display = self._wave.get_display_levels()
        # reveal clipping
        eased = getattr(self, "_reveal_progress", 1.0)
        full_w = bars[-1].right() - bars[0].left()
        need_clip = eased < 1.0
        if need_clip:
            painter.save()
            center_x = bars[0].left() + full_w / 2
            half_w = full_w * eased / 2
            # Clip should be vertically limited to main pill
            thinking_off = _THINKING_HEIGHT + _THINKING_GAP if self._thinking_text else 0.0
            clip = QRectF(center_x - half_w, thinking_off, half_w * 2, HEIGHT)
            painter.setClipRect(clip)
        # The right edge is the live edge: recent bars are brighter, older
        # bars softly recede to the left without any artificial motion.
        painter.setPen(Qt.PenStyle.NoPen)
        muted = QColor(cols["MUTED"])
        muted.setAlpha(105)
        active = QColor(accent)
        active.setAlpha(224)
        r = bar_w / 2
        last_index = max(1, len(display) - 1)
        for index, (base, level) in enumerate(zip(bars, display)):
            shaped = max(0.0, min(1.0, float(level)))
            h = 4.0 + shaped * 42.0
            if h > 46.0:
                h = 46.0
            y = mid - h / 2
            painter.setBrush(muted if shaped < 0.04 else active)
            painter.setOpacity(0.58 + 0.42 * index / last_index)
            painter.drawRoundedRect(QRectF(base.left(), y, bar_w, h), r, r)
        painter.setOpacity(1.0)
        if need_clip:
            painter.restore()

    def _draw_dual_waveform(self, painter):
        """Your microphone above the line, what the speakers play below it."""
        cols = _palette_colors()
        layout = self._layout()
        bars = layout["bars"]
        bar_w = bars[0].width()
        mid = layout["waveform"].center().y()
        mine_disp = self._wave.get_display_levels()
        theirs_disp = self._wave2.get_display_levels()
        eased = getattr(self, "_reveal_progress", 1.0)
        full_w = bars[-1].right() - bars[0].left()
        need_clip = eased < 1.0
        if need_clip:
            painter.save()
            center_x = bars[0].left() + full_w / 2
            half_w = full_w * eased / 2
            thinking_off = _THINKING_HEIGHT + _THINKING_GAP if self._thinking_text else 0.0
            clip = QRectF(center_x - half_w, thinking_off, half_w * 2, HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        r = bar_w / 2
        muted = QColor(cols["MUTED"])
        muted.setAlpha(95)
        mine_color = QColor(cols["REC"])
        mine_color.setAlpha(218)
        theirs_color = QColor(cols["THEM"])
        theirs_color.setAlpha(210)
        last_index = max(1, len(mine_disp) - 1)
        for index, (base, mine, theirs) in enumerate(zip(bars, mine_disp, theirs_disp)):
            x = base.left()
            for level, accent, up in (
                (mine, mine_color, True),
                (theirs, theirs_color, False),
            ):
                shaped = max(0.0, min(1.0, float(level)))
                h = 3.0 + shaped * 20.0
                if h > 23.0:
                    h = 23.0
                y = mid - 2.0 - h if up else mid + 2.0
                painter.setBrush(muted if shaped < 0.04 else accent)
                painter.setOpacity(0.58 + 0.42 * index / last_index)
                painter.drawRoundedRect(QRectF(x, y, bar_w, h), r, r)
        painter.setOpacity(1.0)
        if need_clip:
            painter.restore()

    def _draw_time(self, painter):
        painter.setFont(self._timer_font())
        color = QColor(_palette_colors()["TEXT"])
        color.setAlpha(235)
        painter.setPen(color)
        painter.drawText(
            self._layout()["timer_rect"],
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            self._timer_text,
        )
        self._timer_dirty = False

    def _action_icon_renderer(self, name, color):
        """Reuse the shared SVG glyphs, parsing each tint only once per state."""
        from ui import icons
        from ui import theme as _theme
        key = (_theme.current(), name, color)
        if self._action_renderer_key != key:
            self._action_renderer = QSvgRenderer(
                QByteArray(icons.svg(name, color).encode("utf-8")))
            self._action_renderer_key = key
        return self._action_renderer

    def _draw_pause_button(self, painter):
        rect = self._pause_button_rect()
        self._pause_rect = rect
        if not rect.isValid():
            return
        cols = _palette_colors()
        is_paused = self._paused or self.state == PAUSED_STATE
        visual = rect.adjusted(4.0, 4.0, -4.0, -4.0)
        bg = QColor(cols["SURFACE2"] if self._hover_pause else cols["BG"])
        if self._button_pressed:
            bg = QColor(cols["BORDER"])
        bg.setAlpha(242)
        border = QColor(cols["TEXT"] if self._hover_pause else cols["BORDER"])
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(visual)
        painter.setPen(QPen(border, 1.0 if not self._hover_pause else 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(visual)
        icon_rect = QRectF(visual.center().x() - 10.0, visual.center().y() - 10.0, 20.0, 20.0)
        icon_name = "play" if is_paused else "pause"
        renderer = self._action_icon_renderer(icon_name, cols["TEXT"].name())
        if renderer is not None and renderer.isValid():
            renderer.render(painter, icon_rect)

    def _draw_stop_button(self, painter):
        rect = self._stop_button_rect()
        self._stop_rect = rect
        if not rect.isValid():
            return
        cols = _palette_colors()
        visual = rect.adjusted(4.0, 4.0, -4.0, -4.0)
        bg = QColor(cols["SURFACE2"] if self._hover_stop else cols["BG"])
        if self._stop_pressed:
            bg = QColor(cols["BORDER"])
        bg.setAlpha(242)
        border = QColor(cols["TEXT"] if self._hover_stop else cols["BORDER"])
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(visual)
        painter.setPen(QPen(border, 1.0 if not self._hover_stop else 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(visual)
        # Stop icon: square
        icon_rect = QRectF(visual.center().x() - 7.0, visual.center().y() - 7.0, 14.0, 14.0)
        # Use rect with slight radius
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(cols["TEXT"]))
        painter.drawRoundedRect(icon_rect, 2.0, 2.0)

    @property
    def _can_dismiss(self):
        return self.dismissable and self.state == "busy"

    def _draw_dismiss(self, painter):
        # Use main pill center for y when thinking panel visible
        try:
            cy = self._layout()["indicator"].center().y()
        except Exception:
            offset = _THINKING_HEIGHT + _THINKING_GAP if self._thinking_text else 0.0
            cy = offset + HEIGHT / 2
        cx = self.width() - 18.0
        pen = QPen(QColor(_palette_colors()["MUTED"]), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
        painter.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))

    def _draw_message(self, painter):
        cols = _palette_colors()
        painter.setFont(self._label_font())
        painter.setPen({"error": cols["ERR"], "warning": cols["WARN"]}.get(self.state, cols["TEXT"]))
        offset = _THINKING_HEIGHT + _THINKING_GAP if self._thinking_text else 0.0
        box = QRectF(46, offset, self.width() - 60 - (18 if self._can_dismiss else 0),
                     HEIGHT)
        metrics = QFontMetrics(self._label_font())
        text = metrics.elidedText(self.message, Qt.TextElideMode.ElideRight, int(box.width()))
        painter.drawText(
            box, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text
        )

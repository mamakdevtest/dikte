"""Reusable native components, one per class in the prototype's ``dikte.css``.

Each class in the stylesheet maps to a small QWidget here; the styling itself
lives in ``ui/theme.py``'s QSS, which reads the same dynamic properties these
set (``variant``, ``chip``, ``dot``, ``note``, ``mono``, …). ToggleSwitch is the
one exception: it paints its own animated knob, since Qt QSS has no ``::after``.
"""

from PyQt6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QBoxLayout, QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import theme
from . import icons as _icons


def _mix(hex_a, hex_b, share_a):
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return QColor(*[round(a[i] * share_a + b[i] * (1 - share_a)) for i in range(3)])


# ---- text ---------------------------------------------------------------

def Meta(text="", parent=None):
    label = QLabel(text, parent)
    label.setObjectName("meta")
    label.setWordWrap(True)
    return label


def MonoLabel(text="", parent=None):
    label = QLabel(text, parent)
    label.setProperty("mono", True)
    return label


def KbdChip(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("kbd")
    return label


def Title(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("pageTitle")
    return label


def Subtitle(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("pageSub")
    label.setWordWrap(True)
    return label


# ---- status -------------------------------------------------------------

def Dot(kind="idle", parent=None):
    label = QLabel(parent)
    label.setProperty("dot", kind)
    label.setFixedSize(7, 7)
    return label


class StatusChip(QFrame):
    """A pill with an optional leading dot: chip-sage / chip-gray / chip-tan /
    chip-red / chip-ok."""

    def __init__(self, text="", variant="sage", dot=None, parent=None):
        super().__init__(parent)
        self.setProperty("chip", variant)
        self.dot = Dot(dot) if dot else None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(5)
        if self.dot:
            layout.addWidget(self.dot)
        label = QLabel(text)
        layout.addWidget(label)


class InfoNote(QLabel):
    """A note-info / note-warn / note-err / note-ok box."""

    def __init__(self, text="", variant="info", parent=None):
        super().__init__(text, parent)
        self.setProperty("note", variant)
        self.setWordWrap(True)


class Spinner(QWidget):
    """A small rotating ring; only the busy state is drawn."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._phase = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(360.0)
        self._anim.setDuration(800)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._tick)
        self._anim.start()

    def _tick(self, value):
        self._phase = float(value)
        self.update()

    def paintEvent(self, event):
        c = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(c["sageDark"]), 2)
        p.setPen(pen)
        rect = QRectF(2, 2, 10, 10)
        p.drawArc(rect, int(-self._phase * 16), 100 * 16)
        p.end()


class EmptyState(QWidget):
    def __init__(self, icon_name, title, desc, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 52, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        ic = QLabel()
        ic.setObjectName("emptyIcon")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon = ic
        layout.addWidget(ic)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setObjectName("emptyTitle")
        self._title = t
        layout.addWidget(t)
        d = QLabel(desc)
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setObjectName("emptyDesc")
        self._desc = d
        layout.addWidget(d)
        layout.addStretch(1)
        self._refresh_palette()

    def _refresh_palette(self):
        c = theme.palette()
        if hasattr(self, "_icon") and self._icon is not None:
            self._icon.setPixmap(_icons.pixmap(self._icon_name, 19, c["fg3"]))
        if hasattr(self, "_desc") and self._desc is not None:
            # Colour comes from QSS QLabel#emptyDesc so theme.apply() repaints.
            self._desc.style().unpolish(self._desc)
            self._desc.style().polish(self._desc)
        if hasattr(self, "_title") and self._title is not None:
            self._title.style().unpolish(self._title)
            self._title.style().polish(self._title)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_palette()


# ---- buttons ------------------------------------------------------------

_VARIANTS = ("primary", "ink", "secondary", "ghost", "danger", "rec", "seg")


def btn(text, variant="secondary", size=None, icon_name=None, icon_color=None,
        parent=None):
    """A styled QPushButton; `size` is "sm" for the 26px-tall button."""
    button = QPushButton(text, parent)
    button.setProperty("variant", variant if variant in _VARIANTS else "secondary")
    if size == "sm":
        button.setProperty("size", "sm")
        button.setFixedHeight(26)
    else:
        button.setFixedHeight(32)
    if icon_name:
        button.setIcon(_icons.icon(icon_name, 15, icon_color or theme.palette()["fg2"]))
    return button


def icon_button(icon_name, variant="ghost", size=None, tooltip="", parent=None):
    """A square button carrying only an icon."""
    button = btn("", variant, size, icon_name=icon_name, parent=parent)
    button.setToolTip(tooltip)
    button.setFixedWidth(26 if size == "sm" else 32)
    return button


# ---- toggle -------------------------------------------------------------

class ToggleSwitch(QCheckBox):
    """The 34x18 pill with a sliding knob, sage when checked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._knob = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._set_knob)
        self.toggled.connect(self._animate)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _set_knob(self, value):
        self._knob = float(value)
        self.update()

    def paintEvent(self, event):
        c = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self._knob > 0.5
        if not self.isEnabled():
            track = _mix(c["borderStrong"], c["surface2"], 0.62)
            border = QColor(c["borderStrong"])
            knob = QColor(c["surface2"])
        elif on:
            track = QColor(c["sageDark"])
            border = QColor(c["sageDark"])
            knob = QColor(c["surface"])
        else:
            track = _mix(c["borderStrong"], c["surface2"], 0.62)
            border = QColor(c["borderStrong"])
            knob = QColor(c["surface"])
        p.setPen(QPen(border, 1))
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0.5, 0.5, 33, 17), 8.5, 8.5)
        x = 2.0 + self._knob * 16.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(knob)
        p.drawEllipse(QRectF(x, 2.5, 12, 12))
        p.end()


# ---- cards and rows -----------------------------------------------------

class SectionCard(QFrame):
    """card + card-h + card-b: a title/description header and a body column."""

    def __init__(self, title="", desc="", control=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if title or desc or control is not None:
            head = QWidget()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(20, 14, 20, 12)
            hl.setSpacing(14)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(2)
            if title:
                t = QLabel(title)
                t.setObjectName("cardTitle")
                text.addWidget(t)
            if desc:
                d = QLabel(desc)
                d.setObjectName("cardDesc")
                d.setWordWrap(True)
                text.addWidget(d)
            hl.addLayout(text, 1)
            if control is not None:
                hl.addWidget(control, 0, Qt.AlignmentFlag.AlignTop)
            outer.addWidget(head)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 8)
        self.body.setSpacing(0)
        outer.addLayout(self.body, 1)

    def add(self, widget):
        self.body.addWidget(widget)
        return widget

    def add_row(self, row):
        return self.add(row)


class SettingRow(QWidget):
    """row / row-main / row-label / row-help / row-control, with the dependent
    indent and the is-off dimming the stylesheet describes."""

    def __init__(self, label="", help_text="", control=None, parent=None,
                 dependent=False):
        super().__init__(parent)
        self._off_effect = QGraphicsOpacityEffect(self)
        self._off_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._off_effect)
        self._dependent = bool(dependent)
        self._narrow = False

        layout = QHBoxLayout(self)
        if dependent:
            layout.setContentsMargins(44, 12, 20, 12)
        else:
            layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(24)

        main = QVBoxLayout()
        main.setContentsMargins(0, 5, 0, 0)
        main.setSpacing(3)
        if label:
            l = QLabel(label)
            l.setObjectName("rowLabel")
            main.addWidget(l)
        if help_text:
            h = QLabel(help_text)
            h.setObjectName("rowHelp")
            h.setWordWrap(True)
            main.addWidget(h)
        layout.addLayout(main, 1)
        self.control_area = QWidget()
        cl = QHBoxLayout(self.control_area)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        cl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        if control is not None:
            cl.addWidget(control)
        layout.addWidget(self.control_area, 0)
        self._control_layout = cl
        self._main_layout = main

    def add_control(self, widget):
        self._control_layout.addWidget(widget)
        return widget

    def setNarrow(self, narrow: bool):
        narrow = bool(narrow)
        if getattr(self, "_narrow", False) == narrow:
            return
        self._narrow = narrow
        outer = self.layout()
        if outer is None:
            return
        # Detach existing children without deleting the stored layouts/widgets.
        while outer.count():
            item = outer.takeAt(0)
            # item will be deleted, but its widget/layout remains referenced.
        # Switch direction via QBoxLayout (QHBoxLayout/QVBoxLayout are QBoxLayout).
        try:
            outer.setDirection(
                QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
            )
        except Exception:
            pass
        if narrow:
            outer.setContentsMargins(20, 12, 20, 12)
            outer.setSpacing(8)
            outer.addLayout(self._main_layout)
            outer.addWidget(self.control_area)
            self.control_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            # control layout should stretch full width
            self._control_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        else:
            outer.setContentsMargins(44 if self._dependent else 20, 12, 20, 12)
            outer.setSpacing(24)
            outer.addLayout(self._main_layout, 1)
            outer.addWidget(self.control_area, 0)
            self.control_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            self._control_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.updateGeometry()
        self.style().unpolish(self)
        self.style().polish(self)

    # Back-compat alias for earlier camelCase callers
    def set_narrow(self, narrow: bool):
        return self.setNarrow(narrow)

    def set_off(self, off):
        self._off_effect.setOpacity(0.45 if off else 1.0)
        self.setEnabled(not off)


def switch_row(label="", help_text="", dependent=False):
    """A SettingRow whose control is a fresh ToggleSwitch."""
    toggle = ToggleSwitch()
    row = SettingRow(label, help_text, toggle, dependent=dependent)
    return row, toggle


def gate(toggle, rows):
    """Dim `rows` while `toggle` is off — the prototype's data-gate."""
    def update(checked):
        for row in rows:
            if isinstance(row, SettingRow):
                row.set_off(not checked)
            else:
                row.setEnabled(checked)
    toggle.toggled.connect(update)
    update(toggle.isChecked())
    return toggle


# ---- model row ----------------------------------------------------------

class ModelRow(QWidget):
    """Editable model combo + Fetch button + status dot in one row.

    Shared helper for the provider/model rows (transcribe, cleanup, meeting,
    assistant): the combo stays editable so a typed id survives a fetch, the
    Fetch button triggers ``on_fetch``, and the dot reflects fetch status.
    Colours come from QSS (``variant``/``dot`` props) so theme.apply() repaints.
    """

    def __init__(self, items=(), fetch_text=None, parent=None, on_fetch=None):
        super().__init__(parent)
        self.combo = QComboBox(self)
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if items:
            self.combo.addItems(list(items))
        self.fetch = btn(fetch_text or "Fetch", variant="secondary", size="sm",
                         parent=self)
        if on_fetch is not None:
            self.fetch.clicked.connect(on_fetch)
        # Status dot; ``status`` is an alias kept for callers.
        self.dot = Dot("idle", self)
        self.status = self.dot
        self.button = self.fetch
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.fetch, 0)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_status(self, kind="idle"):
        """Update the status dot (ok/sage/warn/err/info/idle/rec)."""
        self.dot.setProperty("dot", kind)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)
        return self.dot

    def set_models(self, models, keep_current=True):
        """Replace combo items, keeping the typed value when asked."""
        current = self.combo.currentText() if keep_current else ""
        self.combo.clear()
        self.combo.addItems(list(models))
        if keep_current and current:
            self.combo.setCurrentText(current)
        return self.combo

    def currentText(self):
        return self.combo.currentText()

    def setCurrentText(self, text):
        self.combo.setCurrentText(text)


def model_row(items=(), fetch_text=None, parent=None, on_fetch=None):
    """Build a ModelRow and return (row, combo, fetch_button)."""
    row = ModelRow(items, fetch_text, parent, on_fetch)
    return row, row.combo, row.fetch


# ---- segmented control --------------------------------------------------

class SegmentedControl(QWidget):
    """seg / seg-btn: a set of mutually-exclusive buttons."""

    def __init__(self, options, parent=None, on_change=None):
        super().__init__(parent)
        self.setObjectName("seg")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.buttons = []
        for label, value in options:
            b = QPushButton(label)
            b.setProperty("variant", "seg")
            b.setFixedHeight(27)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("value", value)
            if on_change is not None:
                b.clicked.connect(lambda _=False, v=value: on_change(v))
            layout.addWidget(b)
            self.buttons.append(b)
        if self.buttons:
            self.set_active(self.buttons[0].property("value"))

    def set_active(self, value):
        for b in self.buttons:
            checked = b.property("value") == value
            b.setChecked(checked)
            b.setProperty("active", checked)
            b.style().unpolish(b)
            b.style().polish(b)


# ---- overlay picker ------------------------------------------------------

class CornerPicker(QWidget):
    """2x2 grid of corner cells matching dikte.css .corner-picker.

    Each cell is 44x34 with a mini-pill (16x10). Active cell gets sage tint.
    Emits ``cornerChanged(str)`` with values like ``"bottom-left"``.
    """

    cornerChanged = pyqtSignal(str)

    _GRID = [
        ("top-left", 0, 0),
        ("top-right", 0, 1),
        ("bottom-left", 1, 0),
        ("bottom-right", 1, 1),
    ]

    def __init__(self, corner="bottom-left", parent=None):
        super().__init__(parent)
        self.setObjectName("cornerPicker")
        self._corner = corner if corner in [c for c, _, _ in self._GRID] else "bottom-left"
        self._buttons = {}
        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        for name, row, col in self._GRID:
            btn = QPushButton(self)
            btn.setProperty("cornerCell", True)
            btn.setFixedSize(44, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(False)
            # Pill centered inside button via child label positioned manually
            pill = QLabel(btn)
            pill.setFixedSize(16, 10)
            # Style via stylesheet; keep reference to update on active change
            pill.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            pill.move((44 - 16) // 2, (34 - 10) // 2)
            pill.setObjectName("miniPill")
            # Store for updates
            btn._pill = pill  # type: ignore[attr-defined]
            btn.clicked.connect(lambda _=False, n=name: self.setCorner(n))
            layout.addWidget(btn, row, col)
            self._buttons[name] = btn
        self._apply_active()

    def _apply_active(self):
        for name, btn in self._buttons.items():
            active = name == self._corner
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            pill = getattr(btn, "_pill", None)
            if pill is not None:
                pill.setProperty("miniPill", "active" if active else "idle")
                pill.style().unpolish(pill)
                pill.style().polish(pill)

    def corner(self):
        return self._corner

    def setCorner(self, corner: str):
        if corner not in self._buttons:
            return
        if self._corner == corner:
            return
        self._corner = corner
        self._apply_active()
        self.cornerChanged.emit(corner)

    # Alias for snake_case callers
    def set_corner(self, corner: str):
        return self.setCorner(corner)


class MiniScreen(QFrame):
    """150x96 preview with a movable MiniOv badge, matching .mini-screen."""

    def __init__(self, corner="bottom-left", parent=None):
        super().__init__(parent)
        self.setObjectName("miniScreen")
        self.setFixedSize(150, 96)
        self._corner = corner
        # MiniOv is a QLabel container with dot, bars, timer.
        # Use QLabel so QSS QLabel#miniOv applies, but we add child layout.
        self._ov = QLabel(self)
        self._ov.setObjectName("miniOv")
        self._ov.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Build inner content for the ov: dot + bars + timer
        row = QHBoxLayout(self._ov)
        row.setContentsMargins(5, 4, 6, 4)
        row.setSpacing(5)
        dot = QLabel(self._ov)
        dot.setFixedSize(4, 4)
        dot.setProperty("ov", "dot")
        row.addWidget(dot)
        bars = QWidget(self._ov)
        bars_layout = QHBoxLayout(bars)
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(1)
        bars_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        for h in (3, 6, 4, 7, 5):
            bar = QLabel(bars)
            bar.setFixedSize(2, h)
            bar.setProperty("ov", "bar")
            bars_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
        bars.setFixedHeight(8)
        row.addWidget(bars)
        timer = QLabel("0:12", self._ov)
        timer.setProperty("ov", "timer")
        row.addWidget(timer)
        self._ov.adjustSize()
        self._reposition()

    def _reposition(self):
        # Position miniOv within 150x96 according to corner.
        ov = self._ov
        ov.adjustSize()
        w = ov.sizeHint().width() or 62
        h = ov.sizeHint().height() or 18
        # Ensure reasonable fallback if layout not yet calculated
        if w < 40:
            w = 62
        if h < 12:
            h = 18
        pad = 6
        if self._corner == "bottom-left":
            x, y = pad, self.height() - h - pad
        elif self._corner == "bottom-right":
            x, y = self.width() - w - pad, self.height() - h - pad
        elif self._corner == "top-left":
            x, y = pad, pad
        elif self._corner == "top-right":
            x, y = self.width() - w - pad, pad
        else:
            x, y = pad, self.height() - h - pad
        ov.move(int(x), int(y))
        ov.show()

    def setCorner(self, corner: str):
        if corner not in ("bottom-left", "bottom-right", "top-left", "top-right"):
            return
        if self._corner == corner:
            return
        self._corner = corner
        self._reposition()

    def corner(self):
        return self._corner

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()

    # Alias
    def set_corner(self, corner: str):
        return self.setCorner(corner)

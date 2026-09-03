"""Dashboard home page — 4 stat cards, 2 QPainter charts, recent lists."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QListWidget, QListWidgetItem,
    QPushButton,
)

from i18n import t

from ..widgets import SectionCard
from . import page, scrolled
from .. import theme


class DailyBarChart(QWidget):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = list(data) if data else []  # list of (label, count)
        self.setMinimumHeight(140)
        self.setMinimumWidth(200)
        self.setMouseTracking(True)

    def set_data(self, data):
        self._data = list(data) if data else []
        self.update()

    def _geometry(self):
        rect = self.rect().adjusted(8, 12, -8, -24)
        n = len(self._data)
        bar_w = max(4, min(22, (rect.width() - (n + 1) * 6) // max(1, n)))
        gap = 6 if n > 10 else 8
        total_w = n * bar_w + (n - 1) * gap if n else 0
        x0 = rect.x() + (rect.width() - total_w) // 2 if n else rect.x()
        return rect, n, bar_w, gap, x0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            c = theme.palette()
            rect, n, bar_w, gap, x0 = self._geometry()
            if not self._data or max(v for _, v in self._data) == 0:
                p.setPen(QColor(c.get("fg3", "#71847E")))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("No data yet"))
                return
            max_v = max(v for _, v in self._data) or 1
            p.setPen(QPen(QColor(c.get("border", "#CBD9D2")), 1))
            base_y = rect.bottom()
            total_w = n * bar_w + (n - 1) * gap
            p.drawLine(x0, base_y, x0 + total_w, base_y)
            sage = QColor(c.get("sageDark", "#3F6B5A"))
            sage_light = QColor(c.get("sage", "#B7CCBD"))
            for i, (label, val) in enumerate(self._data):
                h = int((val / max_v) * (rect.height() - 20)) if max_v else 0
                x = x0 + i * (bar_w + gap)
                y = base_y - h
                p.setBrush(QBrush(sage if val == max_v and max_v > 0 else sage_light))
                p.setPen(Qt.PenStyle.NoPen)
                if h > 0:
                    p.drawRoundedRect(QRectF(x, y, bar_w, h), 3, 3)
                if val > 0:
                    p.setPen(QColor(c.get("fg2", "#536963")))
                    f = QFont()
                    f.setPointSize(7)
                    p.setFont(f)
                    p.drawText(QRectF(x - 4, y - 14, bar_w + 8, 12),
                               Qt.AlignmentFlag.AlignCenter, str(val))
                try:
                    short = label[5:] if len(label) >= 10 else label
                except Exception:
                    short = str(label)
                p.setPen(QColor(c.get("fg3", "#71847E")))
                f2 = QFont()
                f2.setPointSize(7)
                p.setFont(f2)
                p.drawText(QRectF(x - 8, base_y + 4, bar_w + 16, 12),
                           Qt.AlignmentFlag.AlignCenter, short)
        finally:
            p.end()

    def mouseMoveEvent(self, event):
        if not self._data:
            return
        _rect, n, bar_w, gap, x0 = self._geometry()
        try:
            x = event.position().x() if hasattr(event, "position") else event.x()
        except Exception:
            return
        idx = int((x - x0) // (bar_w + gap)) if bar_w + gap else -1
        if 0 <= idx < n:
            lab, val = self._data[idx]
            self.setToolTip(f"{lab}: {val}")
        else:
            self.setToolTip("")


class ProviderDonut(QWidget):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = dict(data) if data else {}
        self.setMinimumHeight(140)
        self.setMinimumWidth(180)

    def set_data(self, data):
        self._data = dict(data) if data else {}
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            c = theme.palette()
            if not self._data or sum(self._data.values()) == 0:
                p.setPen(QColor(c.get("fg3", "#71847E")))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("No data yet"))
                return
            total = sum(self._data.values())
            colors = [c.get("sageDark", "#3F6B5A"), c.get("sage", "#B7CCBD"),
                      c.get("terra", "#C96D59"), c.get("fg2", "#536963"),
                      "#8AA39B", "#B8CFC4"]
            rect = self.rect().adjusted(12, 12, -12, -24)
            size = min(rect.width(), rect.height() - 10)
            if size <= 0:
                return
            cx = rect.center().x()
            cy = rect.center().y() - 4
            outer = size / 2
            inner = outer * 0.52
            start = -90 * 16
            for idx, (label, val) in enumerate(
                    sorted(self._data.items(), key=lambda kv: -kv[1])):
                span = int(360 * 16 * val / total) if total else 0
                p.setBrush(QBrush(QColor(colors[idx % len(colors)])))
                p.setPen(QPen(QColor(c.get("surface", "#FFFFFF")), 2))
                if span > 0:
                    p.drawPie(int(cx - outer), int(cy - outer),
                              int(outer * 2), int(outer * 2), start, span)
                start += span
            p.setBrush(QBrush(QColor(c.get("surface", "#FFFFFF"))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - inner), int(cy - inner),
                          int(inner * 2), int(inner * 2))
            p.setPen(QColor(c.get("fg", "#17211F")))
            f = QFont()
            f.setBold(True)
            f.setPointSize(11)
            p.setFont(f)
            p.drawText(QRectF(cx - inner, cy - 10, inner * 2, 14),
                       Qt.AlignmentFlag.AlignCenter, str(total))
            p.setPen(QColor(c.get("fg3", "#71847E")))
            f2 = QFont()
            f2.setPointSize(7)
            p.setFont(f2)
            p.drawText(QRectF(cx - inner, cy + 6, inner * 2, 10),
                       Qt.AlignmentFlag.AlignCenter, t("total"))
            parts = [f"{k} {v}" for k, v in
                     sorted(self._data.items(), key=lambda kv: -kv[1])[:4]]
            txt = " · ".join(parts)
            if txt:
                p.setPen(QColor(c.get("fg2", "#536963")))
                p.drawText(QRectF(rect.x(), rect.bottom() + 6, rect.width(), 14),
                           Qt.AlignmentFlag.AlignCenter, txt)
        finally:
            p.end()


def _stat_card(title, value, subtitle=""):
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(2)
    lab = QLabel(title)
    lab.setStyleSheet(f"color: {theme.palette().get('fg3','#71847E')}; font-size: 11px;")
    lay.addWidget(lab)
    val = QLabel(str(value))
    val.setStyleSheet(f"color: {theme.palette().get('fg','#17211F')}; font-size: 22px; font-weight: 700;")
    lay.addWidget(val)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet(f"color: {theme.palette().get('fg2','#536963')}; font-size: 11.5px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)
    return card


def _quick_actions(window, outer):
    try:
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for label, slot_name in [(t("Start recording"), "toggle"),
                                 (t("Ask"), "toggle_ask"),
                                 (t("Record a meeting"), "toggle_meeting")]:
            b = QPushButton(label)
            b.setProperty("variant", "secondary")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(_make_handler(window, slot_name))
            actions.addWidget(b)
        actions.addStretch(1)
        outer.addLayout(actions)
    except Exception:
        pass


def _make_handler(window, slot):
    def _fn():
        try:
            ctrl = getattr(window, "_controller", None) or getattr(window, "controller", None)
            if ctrl is None:
                return
            fn = getattr(ctrl, slot, None) or getattr(ctrl, f"_{slot}", None)
            if fn:
                fn()
        except Exception:
            pass
    return _fn


def build(window):
    try:
        from ..stats import history_stats, meetings_stats, daily_counts, provider_usage
        hs = history_stats(limit=500)
        ms = meetings_stats()
        dc = daily_counts(days=14)
        pu = provider_usage()
    except Exception:
        hs = {"total": 0, "last_7d": 0, "avg_duration": 0, "success_rate": 0}
        ms = {"total": 0, "last_30d": 0, "total_duration": 0}
        dc = []
        pu = {}

    body, outer = page(t("Dashboard"), t("Genel bakış — son dikte ve toplantılarınız"))
    _quick_actions(window, outer)

    # 4 cards
    cards = QHBoxLayout()
    cards.setSpacing(10)
    avg_txt = f"{hs.get('avg_duration',0):.1f}s {t('avg')}" if hs.get('total') else t("—")
    cards.addWidget(_stat_card(t("Total dictations"), hs.get("total", 0), avg_txt))
    cards.addWidget(_stat_card(t("Last 7 days"), hs.get("last_7d", 0), f"{hs.get('success_rate',0):.0f}% {t('success')}"))
    cards.addWidget(_stat_card(t("Meetings"), ms.get("total", 0), f"{ms.get('last_30d',0)} {t('last 30 days')}"))
    total_min = int(ms.get("total_duration", 0) // 60)
    cards.addWidget(_stat_card(t("Meeting time"), f"{total_min} {t('min')}", t("total duration")))
    outer.addLayout(cards)

    # charts row
    charts = QHBoxLayout()
    charts.setSpacing(12)
    left_card = SectionCard(t("Daily dictations"), t("Last 14 days"))
    bar = DailyBarChart(dc)
    window._dash_bar = bar
    window._dash_bar_data = dc
    left_card.add(bar)
    charts.addWidget(left_card, 1)
    right_card = SectionCard(t("By provider"), t("Distribution"))
    donut = ProviderDonut(pu)
    window._dash_donut = donut
    window._donut = donut
    right_card.add(donut)
    charts.addWidget(right_card, 1)
    outer.addLayout(charts)

    # recent lists
    recent = QHBoxLayout()
    recent.setSpacing(12)
    left_list_card = SectionCard(t("Recent dictations"), t("Last 5"))
    lst = QListWidget()
    lst.setMaximumHeight(130)
    try:
        import config
        rows = list(reversed(config.read_history(limit=5)))
        if not rows:
            lst.addItem(t("No dictations yet"))
            lst.setEnabled(False)
        else:
            for r in rows:
                txt = (r.get("text") or r.get("raw") or "").replace("\n", " ")[:90]
                ts = r.get("ts", "")
                item = QListWidgetItem(f"{ts}  {txt}")
                item.setData(Qt.ItemDataRole.UserRole, r)
                lst.addItem(item)
        lst.itemClicked.connect(lambda _item=None: _goto_tab(window, ("History", "Geçmiş")))
        lst.itemDoubleClicked.connect(lambda _item=None: _goto_tab(window, ("History", "Geçmiş")))
    except Exception:
        pass
    left_list_card.add(lst)
    recent.addWidget(left_list_card, 1)
    right_list_card = SectionCard(t("Recent meetings"), t("Last 3"))
    ml = QListWidget()
    ml.setMaximumHeight(130)
    try:
        import config as cfg
        import meeting as mt
        mrows = list(reversed(cfg.read_meetings()))[:3]
        if not mrows:
            ml.addItem(t("No meetings yet"))
            ml.setEnabled(False)
        else:
            for r in mrows:
                title = (r.get("title") or "").strip() or mt.fallback_title(r.get("ts", ""))
                ts = r.get("ts", "")
                item = QListWidgetItem(f"{title}  —  {ts}")
                item.setData(Qt.ItemDataRole.UserRole, r)
                ml.addItem(item)
        ml.itemClicked.connect(lambda _item=None: _goto_tab(window, ("Minutes", "Tutanak")))
        ml.itemDoubleClicked.connect(lambda _item=None: _goto_tab(window, ("Minutes", "Tutanak")))
    except Exception:
        pass
    right_list_card.add(ml)
    recent.addWidget(right_list_card, 1)
    outer.addLayout(recent)

    def refresh():
        try:
            from ..stats import daily_counts as dc2, provider_usage as pu2
            if hasattr(window, "_dash_bar"):
                window._dash_bar.set_data(dc2(days=14))
            if hasattr(window, "_dash_donut"):
                window._dash_donut.set_data(pu2())
            if hasattr(window, "_donut") and window._donut is not getattr(window, "_dash_donut", None):
                window._donut.set_data(pu2())
        except Exception:
            pass
    window._dash_refresh = refresh

    outer.addStretch(1)
    return scrolled(body)


def _goto_tab(window, needles):
    try:
        if hasattr(window, "tabs"):
            for i in range(window.tabs.count()):
                text = window.tabs.tabText(i)
                if any(n in text for n in needles):
                    window.tabs.setCurrentIndex(i)
                    break
    except Exception:
        pass

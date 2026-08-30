"""Dashboard home page — 4 stat cards, 2 QPainter charts, recent lists."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QListWidget, QListWidgetItem,
    QPushButton,
)

from i18n import t

from ..widgets import SectionCard, Title, Subtitle, EmptyState
from . import page, scrolled
from .. import theme


class DailyBarChart(QWidget):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []  # list of (label, count)
        self.setMinimumHeight(140)
        self.setMinimumWidth(200)

    def set_data(self, data):
        self._data = list(data) if data else []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = theme.palette()
        rect = self.rect().adjusted(8, 12, -8, -24)
        if not self._data or max(v for _, v in self._data) == 0:
            p.setPen(QColor(c.get("fg3", "#71847E")))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("No data yet"))
            return
        max_v = max(v for _, v in self._data) or 1
        n = len(self._data)
        bar_w = max(4, min(22, (rect.width() - (n + 1) * 6) // max(1, n)))
        gap = 6 if n > 10 else 8
        total_w = n * bar_w + (n - 1) * gap
        x0 = rect.x() + (rect.width() - total_w) // 2
        # baseline
        p.setPen(QPen(QColor(c.get("border", "#CBD9D2")), 1))
        base_y = rect.bottom()
        p.drawLine(x0, base_y, x0 + total_w, base_y)
        sage = QColor(c.get("sageDark", "#3F6B5A"))
        sage_light = QColor(c.get("sage", "#B7CCBD"))
        for i, (label, val) in enumerate(self._data):
            h = int((val / max_v) * (rect.height() - 20)) if max_v else 0
            x = x0 + i * (bar_w + gap)
            y = base_y - h
            # bar
            col = sage if val == max_v and max_v > 0 else sage_light
            p.setBrush(QBrush(col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, h), 3, 3)
            # value label on top if non-zero
            if val > 0:
                p.setPen(QColor(c.get("fg2", "#536963")))
                f = QFont()
                f.setPointSize(7)
                p.setFont(f)
                p.drawText(QRectF(x - 4, y - 14, bar_w + 8, 12), Qt.AlignmentFlag.AlignCenter, str(val))
            # date label (MM-DD)
            try:
                short = label[5:] if len(label) >= 10 else label
            except Exception:
                short = str(label)
            p.setPen(QColor(c.get("fg3", "#71847E")))
            f2 = QFont()
            f2.setPointSize(7)
            p.setFont(f2)
            p.drawText(QRectF(x - 8, base_y + 4, bar_w + 16, 12), Qt.AlignmentFlag.AlignCenter, short)
        p.end()

    def mouseMoveEvent(self, event):
        # tooltip: nearest bar
        if not self._data:
            return
        c = theme.palette()
        rect = self.rect().adjusted(8, 12, -8, -24)
        n = len(self._data)
        bar_w = max(4, min(22, (rect.width() - (n + 1) * 6) // max(1, n)))
        gap = 6 if n > 10 else 8
        total_w = n * bar_w + (n - 1) * gap
        x0 = rect.x() + (rect.width() - total_w) // 2
        x = event.position().x() if hasattr(event, "position") else event.x()
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
        c = theme.palette()
        if not self._data or sum(self._data.values()) == 0:
            p.setPen(QColor(c.get("fg3", "#71847E")))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("No data yet"))
            return
        total = sum(self._data.values())
        # palette cycle
        colors = [c.get("sageDark", "#3F6B5A"), c.get("sage", "#B7CCBD"), c.get("accent", "#C96D59") if "accent" in c else "#C96D59",
                  c.get("terra", "#C96D59"), c.get("fg2", "#536963"), "#8AA39B", "#B8CFC4"]
        rect = self.rect().adjusted(12, 12, -12, -24)
        size = min(rect.width(), rect.height() - 10)
        cx = rect.center().x()
        cy = rect.center().y() - 4
        outer = size / 2
        inner = outer * 0.52
        start = -90 * 16
        idx = 0
        for label, val in sorted(self._data.items(), key=lambda kv: -kv[1]):
            span = int(360 * 16 * val / total) if total else 0
            col = QColor(colors[idx % len(colors)])
            idx += 1
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor(c.get("surface", "#fff")), 2))
            if span > 0:
                p.drawPie(int(cx - outer), int(cy - outer), int(outer * 2), int(outer * 2), start, span)
            start += span
        # hole
        p.setBrush(QBrush(QColor(c.get("surface", "#FFFFFF"))))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - inner), int(cy - inner), int(inner * 2), int(inner * 2))
        # center total
        p.setPen(QColor(c.get("fg", "#17211F")))
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(QRectF(cx - inner, cy - 10, inner * 2, 14), Qt.AlignmentFlag.AlignCenter, str(total))
        p.setPen(QColor(c.get("fg3", "#71847E")))
        f2 = QFont()
        f2.setPointSize(7)
        p.setFont(f2)
        p.drawText(QRectF(cx - inner, cy + 6, inner * 2, 10), Qt.AlignmentFlag.AlignCenter, t("total"))
        # legend below
        p.setPen(QColor(c.get("fg2", "#536963")))
        legend_y = rect.bottom() + 6
        # draw legend as text (simple)
        parts = []
        for k, v in sorted(self._data.items(), key=lambda kv: -kv[1])[:4]:
            parts.append(f"{k} {v}")
        txt = " · ".join(parts)
        if txt:
            p.drawText(QRectF(rect.x(), legend_y, rect.width(), 14), Qt.AlignmentFlag.AlignCenter, txt)
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
    # quick actions (optional)
    try:
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for label, slot_name in [(t("Start recording"), "toggle"), (t("Ask"), "toggle_ask"), (t("Record a meeting"), "toggle_meeting")]:
            b = QPushButton(label)
            b.setProperty("variant", "secondary")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            # connect via window -> dikte controller stored as window._dikte or via parent chain
            def _make(slot):
                def _fn():
                    try:
                        # DashboardWindow may hold controller ref
                        ctrl = getattr(window, "_controller", None) or getattr(window, "controller", None)
                        if ctrl is None and hasattr(window, "parent") and window.parent():
                            ctrl = getattr(window.parent(), "_controller", None)
                        # fallback: try to find via QApplication
                        if ctrl is None:
                            from PyQt6.QtWidgets import QApplication
                            app = QApplication.instance()
                            # Dikte instance not directly reachable; just no-op
                            return
                        fn = getattr(ctrl, slot, None) or getattr(ctrl, f"_{slot}", None)
                        if fn:
                            fn()
                    except Exception:
                        pass
                return _fn
            b.clicked.connect(_make(slot_name))
            actions.addWidget(b)
        actions.addStretch(1)
        outer.addLayout(actions)
    except Exception:
        pass

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
    # keep refs for refresh
    window._dash_bar = bar
    window._dash_bar_data = dc
    left_card.add(bar)
    charts.addWidget(left_card, 1)
    right_card = SectionCard(t("By provider"), t("Distribution"))
    donut = ProviderDonut(pu)
    window._dash_donut = donut
    charts.addWidget(right_card, 1)
    right_card.add(donut)
    outer.addLayout(charts)

    # recent lists
    recent = QHBoxLayout()
    recent.setSpacing(12)
    # last 5 dictations
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
        def _open_hist(item):
            try:
                # navigate to History tab (index lookup by title)
                if hasattr(window, "tabs") and hasattr(window, "shell"):
                    for i in range(window.tabs.count()):
                        if "History" in window.tabs.tabText(i) or "Geçmiş" in window.tabs.tabText(i):
                            window.tabs.setCurrentIndex(i)
                            break
            except Exception:
                pass
        lst.itemClicked.connect(_open_hist)
        lst.itemDoubleClicked.connect(_open_hist)
    except Exception:
        pass
    left_list_card.add(lst)
    recent.addWidget(left_list_card, 1)
    # last 3 meetings
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
        def _open_min(item):
            try:
                if hasattr(window, "tabs"):
                    for i in range(window.tabs.count()):
                        if "Minutes" in window.tabs.tabText(i) or "Tutanak" in window.tabs.tabText(i):
                            window.tabs.setCurrentIndex(i)
                            break
            except Exception:
                pass
        ml.itemClicked.connect(_open_min)
        ml.itemDoubleClicked.connect(_open_min)
    except Exception:
        pass
    right_list_card.add(ml)
    recent.addWidget(right_list_card, 1)
    outer.addLayout(recent)

    # refresh helper
    def refresh():
        try:
            from ..stats import history_stats as hs2, meetings_stats as ms2, daily_counts as dc2, provider_usage as pu2
            hs_ = hs2(limit=500)
            # update cards? simplest: rebuild handled by caller; here update charts
            if hasattr(window, "_dash_bar"):
                window._dash_bar.set_data(dc2(days=14))
            if hasattr(window, "_dash_donut"):
                window._dash_donut.set_data(pu2())
        except Exception:
            pass
    window._dash_refresh = refresh

    outer.addStretch(1)
    return scrolled(body)

import subprocess
import sys
import unittest

from tests.support import DikteTest


def _run_subprocess(code):
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result


class DashboardTests(DikteTest):
    def test_dashboard_window_tabs(self):
        code = """
import config as cfg
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from ui.app_window import DashboardWindow
import config
conf = config.Config()
# mock background threads
from unittest import mock
import settings_ui
with mock.patch.object(settings_ui.SettingsWindow, "_fetch_cli_versions", lambda self, defs: None), \
     mock.patch.object(settings_ui.SettingsWindow, "_load_audio_devices", lambda self: None):
    w = DashboardWindow(conf, meetings=None)
    print(w.tabs.count())
    print(w.tabs.tabText(0))
    print(w.dashboard_index)
    print(w.api_tab_index)
    print(w.tabs.currentIndex())
    w.close()
    w.deleteLater()
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QApplication as QA
    QA.sendPostedEvents(w, QEvent.Type.DeferredDelete)
    QA.processEvents()
    app.quit()
"""
        r = _run_subprocess(code)
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[0], "11")
        self.assertEqual(lines[1], "Dashboard")
        self.assertEqual(lines[2], "0")
        self.assertEqual(lines[3], "2")

    def test_dashboard_charts_no_crash(self):
        from PyQt6.QtWidgets import QApplication
        from ui.pages.dashboard import DailyBarChart, ProviderDonut
        _app = QApplication.instance() or QApplication([])
        bar = DailyBarChart([])
        bar.resize(300, 150)
        bar.show()
        _app.processEvents()
        bar.set_data([("2026-08-10", 0), ("2026-08-11", 3)])
        bar.show()
        _app.processEvents()
        donut = ProviderDonut({})
        donut.resize(300, 150)
        donut.show()
        _app.processEvents()
        donut.set_data({"local": 2, "openai": 1})
        donut.show()
        _app.processEvents()
        bar.close()
        donut.close()
        bar.deleteLater()
        donut.deleteLater()
        _app.processEvents()

    def test_dashboard_stats_integration(self):
        from ui import stats
        hs = stats.history_stats()
        self.assertIn("total", hs)
        code = """
import config as cfg
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from ui.app_window import DashboardWindow
import config
conf = config.Config()
from unittest import mock
import settings_ui
with mock.patch.object(settings_ui.SettingsWindow, "_fetch_cli_versions", lambda self, defs: None), \
     mock.patch.object(settings_ui.SettingsWindow, "_load_audio_devices", lambda self: None):
    w = DashboardWindow(conf, meetings=None)
    if hasattr(w, "_dash_refresh"):
        w._dash_refresh()
    from PyQt6.QtWidgets import QApplication as QA
    from PyQt6.QtCore import QEvent
    QA.processEvents()
    w.close()
    w.deleteLater()
    QA.sendPostedEvents(w, QEvent.Type.DeferredDelete)
    QA.processEvents()
    app.quit()
    print("ok")
"""
        r = _run_subprocess(code)
        self.assertEqual(r.returncode, 0, msg=r.stderr)

    def test_settings_window_unchanged(self):
        from PyQt6.QtWidgets import QApplication
        import settings_ui
        import config as cfg
        _app = QApplication.instance() or QApplication([])
        conf = cfg.Config()
        w = settings_ui.SettingsWindow(conf, meetings=None)
        try:
            self.assertEqual(w.tabs.count(), 10)
            self.assertEqual(w.api_tab_index, 1)
        finally:
            from PyQt6.QtCore import QEvent
            w.close()
            w.deleteLater()
            QApplication.sendPostedEvents(w, QEvent.Type.DeferredDelete)
            _app.processEvents()


class TheCardsSayTheyDoNotKnow(DikteTest):
    """`0 dictations` is a claim about the user's data.

    When the history cannot be read, the card must not make it: the two states — an
    empty history and an unreadable one — looked identical on screen, and the second
    one is the one that means something is wrong.
    """

    def test_a_history_that_could_not_be_read_shows_a_dash(self):
        code = """
import sys
from PyQt6.QtWidgets import QApplication, QLabel
app = QApplication(sys.argv)
from unittest import mock
import config
import settings_ui
import ui.stats as stats
unreadable = {"total": 0, "last_7d": 0, "by_provider": {}, "avg_duration": 0,
              "success_rate": 0, "unreadable": True}
from ui.app_window import DashboardWindow
conf = config.Config()
with mock.patch.object(settings_ui.SettingsWindow, "_fetch_cli_versions", lambda self, defs: None), \\
     mock.patch.object(settings_ui.SettingsWindow, "_load_audio_devices", lambda self: None), \\
     mock.patch.object(stats, "history_stats", lambda limit=500: dict(unreadable)):
    w = DashboardWindow(conf, meetings=None)
    texts = [lab.text() for lab in w.findChildren(QLabel)]
print("dash:", texts.count("\\u2014"), "told:", "history could not be read" in texts)
w.close()
app.quit()
"""
        r = _run_subprocess(code)
        self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)
        self.assertIn("dash: 2 told: True", r.stdout, msg=r.stdout)

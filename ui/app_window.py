"""DashboardWindow — Dikte's main window: Dashboard + all settings pages."""

from settings_ui import SettingsWindow

try:
    from i18n import t
except Exception:
    def t(s, **_k):
        return s.format(**_k) if _k else s

try:
    from ui.pages import dashboard as dashboard_page
except Exception:
    dashboard_page = None


class DashboardWindow(SettingsWindow):
    """Main window — SettingsWindow plus Dashboard at index 0."""

    def __init__(self, conf, meetings=None, controller=None, parent=None):
        super().__init__(conf, meetings=meetings, parent=parent)
        self._controller = controller
        if dashboard_page is not None:
            try:
                widget = dashboard_page.build(self)
                self.shell.tabs.insertTab(0, widget, t("Dashboard"))
                self.shell.tabs.tabBar().hide()
                from PyQt6.QtCore import QSize, Qt
                from PyQt6.QtWidgets import QPushButton
                from ui import theme, icons
                btn = QPushButton()
                btn.setObjectName("navItem")
                btn.setProperty("active", False)
                btn.setIconSize(QSize(16, 16))
                btn.setText("  " + t("Dashboard"))
                try:
                    btn.setIcon(icons.icon("dashboard", 16, theme.palette()["fg3"]))
                except Exception:
                    try:
                        btn.setIcon(icons.icon("sliders", 16, theme.palette()["fg3"]))
                    except Exception:
                        pass
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self.shell._nav_layout.insertWidget(0, btn)
                self.shell._nav.insert(0, (btn, "dashboard"))
                self.shell._nav_titles.insert(0, t("Dashboard"))
                for i, (b, icon) in enumerate(self.shell._nav):
                    try:
                        b.clicked.disconnect()
                    except Exception:
                        pass
                    b.clicked.connect(lambda _=False, idx=i: self.shell.set_page(idx))
                self.dashboard_index = 0
                try:
                    self.api_tab_index = self.api_tab_index + 1
                except Exception:
                    self.api_tab_index = 1
                try:
                    if not conf.transcribe_ready():
                        self.shell.set_page(self.api_tab_index)
                    else:
                        self.shell.set_page(self.dashboard_index)
                except Exception:
                    pass
            except Exception as e:
                import traceback; traceback.print_exc()
                self.dashboard_index = 0
        else:
            self.dashboard_index = 0
        try:
            self.setWindowTitle(t("Dikte"))
        except Exception:
            pass
        self._controller = controller

    def showEvent(self, event):
        super().showEvent(event)
        try:
            if hasattr(self, "_dash_refresh") and callable(self._dash_refresh):
                self._dash_refresh()
        except Exception:
            pass

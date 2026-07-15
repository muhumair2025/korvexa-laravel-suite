import os
import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt

# Import views
from gui.onboarding_view import OnboardingView
from gui.services_view import ServicesView
from gui.switcher_view import SwitcherView
from gui.settings_view import SettingsView
from gui.about_view import AboutView
from gui.vhost_view import VHostView
from gui.laravel_view import LaravelView
from gui.database_view import DatabaseView

from PySide6.QtCore import Qt, QSettings

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laravel Development Suite")
        self.resize(1000, 700)
        self.setMinimumSize(950, 600)
        self.setMaximumSize(1200, 800)
        
        # Load and set application icon logo
        from PySide6.QtGui import QIcon
        icon_path = self.get_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = QSettings("LaravelDevSuite", "Settings")
        
        # Default environment directory under user profile to avoid Admin rights
        default_env = os.path.join(os.path.expanduser("~"), "php-laravel-env")
        self.env_root = self.settings.value("env_root", default_env)
        
        if not os.path.exists(self.env_root):
            try:
                os.makedirs(self.env_root, exist_ok=True)
            except Exception:
                pass
                
        self.log_dir = os.path.join(self.env_root, "logs")
        
        # Load and apply theme (defaults to dark)
        self.theme = self.settings.value("theme", "dark")
        self.apply_theme(self.theme)
        
        self.is_exiting = False
        self.init_ui()
        self.init_tray()
        
    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Native QTabWidget container
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Initialize only default active view on start (onboarding setup)
        self.onboarding_view = OnboardingView(self)
        self.tabs.addTab(self.onboarding_view, "Setup & Onboarding")
        
        # Lazy loaded views initialized to None
        self.services_view = None
        self.switcher_view = None
        self.vhost_view = None
        self.laravel_view = None
        self.database_view = None
        self.settings_view = None
        self.about_view = None
        
        # Create container widgets for lazy tabs
        self.tab_containers = {}
        lazy_tabs = [
            (1, "Services Control"),
            (2, "PHP Version Control"),
            (3, "Sites & Domains"),
            (4, "Laravel Projects"),
            (5, "Database Manager"),
            (6, "Logs & Settings"),
            (7, "About & Help")
        ]
        for idx, label in lazy_tabs:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            self.tabs.addTab(container, label)
            self.tab_containers[idx] = (container, container_layout)
            
        # Tab switch event mapping
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Trigger initial refresh
        self.on_tab_changed(0)
        
    def on_tab_changed(self, index):
        # Stop active timers to optimize CPU usage
        if self.services_view:
            self.services_view.stop_timer()
        if self.settings_view:
            self.settings_view.stop_timer()
            
        # Lazy load views on tab selection
        if index == 0:
            self.onboarding_view.refresh_status()
            
        elif index == 1:
            if not self.services_view:
                self.services_view = ServicesView(self)
                self.tab_containers[1][1].addWidget(self.services_view)
            self.services_view.start_timer()
            
        elif index == 2:
            if not self.switcher_view:
                self.switcher_view = SwitcherView(self)
                self.tab_containers[2][1].addWidget(self.switcher_view)
            self.switcher_view.refresh_status()
            
        elif index == 3:
            if not self.vhost_view:
                self.vhost_view = VHostView(self)
                self.tab_containers[3][1].addWidget(self.vhost_view)
            self.vhost_view.refresh_table()
            
        elif index == 4:
            if not self.laravel_view:
                self.laravel_view = LaravelView(self)
                self.tab_containers[4][1].addWidget(self.laravel_view)
            self.laravel_view.refresh_project_list()
            
        elif index == 5:
            if not self.database_view:
                self.database_view = DatabaseView(self)
                self.tab_containers[5][1].addWidget(self.database_view)
            self.database_view.refresh_all()
            
        elif index == 6:
            if not self.settings_view:
                self.settings_view = SettingsView(self)
                self.tab_containers[6][1].addWidget(self.settings_view)
            self.settings_view.start_timer()
            
        elif index == 7:
            if not self.about_view:
                self.about_view = AboutView(self)
                self.tab_containers[7][1].addWidget(self.about_view)
            
    def apply_theme(self, theme):
        self.theme = theme
        self.settings.setValue("theme", theme)
        
        from PySide6.QtWidgets import QApplication, QStyleFactory
        from PySide6.QtGui import QPalette, QColor
        from PySide6.QtCore import Qt
        import ctypes
        
        app = QApplication.instance()
        
        # Reset custom stylesheet first to ensure clean native styling
        app.setStyleSheet("")
        
        if theme == "dark":
            app.setStyle(QStyleFactory.create("Fusion"))
            
            palette = QPalette()
            # Deep Slate/Modern Dark Palette
            bg = QColor(15, 23, 42)          # Slate 900
            base = QColor(30, 41, 59)        # Slate 800
            field = QColor(2, 6, 23)         # Slate 950
            text = QColor(241, 245, 249)     # Slate 100
            subtext = QColor(148, 163, 184)  # Slate 400
            accent = QColor(239, 68, 68)     # Laravel Red
            
            palette.setColor(QPalette.Window, bg)
            palette.setColor(QPalette.WindowText, text)
            palette.setColor(QPalette.Base, field)
            palette.setColor(QPalette.AlternateBase, base)
            palette.setColor(QPalette.ToolTipBase, bg)
            palette.setColor(QPalette.ToolTipText, text)
            palette.setColor(QPalette.Text, text)
            palette.setColor(QPalette.PlaceholderText, subtext)
            palette.setColor(QPalette.Button, base)
            palette.setColor(QPalette.ButtonText, text)
            palette.setColor(QPalette.BrightText, Qt.white)
            palette.setColor(QPalette.Link, QColor(99, 102, 241)) # Indigo
            palette.setColor(QPalette.Highlight, accent)
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Disabled color roles
            palette.setColor(QPalette.Disabled, QPalette.WindowText, subtext.darker())
            palette.setColor(QPalette.Disabled, QPalette.Text, subtext.darker())
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, subtext.darker())
            palette.setColor(QPalette.Disabled, QPalette.Base, bg)
            palette.setColor(QPalette.Disabled, QPalette.Button, bg)
            
            app.setPalette(palette)
            
            # Enable Windows immersive dark title bar natively
            try:
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                state = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(state), ctypes.sizeof(state)
                )
            except Exception as e:
                logger.warning(f"Failed to set immersive dark title bar: {e}")
        else:
            # Revert to native system style
            app.setStyle(QStyleFactory.create("windowsvista"))
            
            # Reset palette to default light
            palette = QPalette()
            bg = QColor(240, 240, 240)
            base = QColor(255, 255, 255)
            text = QColor(0, 0, 0)
            
            palette.setColor(QPalette.Window, bg)
            palette.setColor(QPalette.WindowText, text)
            palette.setColor(QPalette.Base, base)
            palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
            palette.setColor(QPalette.Text, text)
            palette.setColor(QPalette.Button, bg)
            palette.setColor(QPalette.ButtonText, text)
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            app.setPalette(palette)
            
            # Disable Windows immersive dark title bar
            try:
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                state = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(state), ctypes.sizeof(state)
                )
            except Exception as e:
                logger.warning(f"Failed to disable immersive dark title bar: {e}")
                
        # Refresh icons on all views if they are initialized and not None
        if getattr(self, 'onboarding_view', None):
            self.onboarding_view.refresh_icons()
        if getattr(self, 'services_view', None):
            self.services_view.refresh_icons()
        if getattr(self, 'switcher_view', None):
            self.switcher_view.refresh_icons()
        if getattr(self, 'settings_view', None):
            self.settings_view.refresh_icons()
        if getattr(self, 'about_view', None):
            self.about_view.refresh_icons()
        if getattr(self, 'vhost_view', None):
            self.vhost_view.refresh_table()
            
        # Force redraw and resolve styles for all widgets in the application
        for widget in app.allWidgets():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def get_icon_color(self):
        return "#ffffff" if self.theme == "dark" else "#1e293b"

    def update_env_root(self, new_path):
        self.env_root = new_path
        self.log_dir = os.path.join(new_path, "logs")
        self.settings.setValue("env_root", new_path)
        
        # Refresh current tab
        self.on_tab_changed(self.tabs.currentIndex())
        
    def closeEvent(self, event):
        """Minimize to tray instead of closing, unless is_exiting is flagged."""
        from PySide6.QtWidgets import QSystemTrayIcon
        if not getattr(self, 'is_exiting', False):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Laravel Development Suite",
                "App is running in the background. Double-click tray icon to open.",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            try:
                # Stop services synchronously on application exit to guarantee cleanup
                from core.services import stop_service
                for key in ["nginx", "apache", "php-cgi", "mysql"]:
                    stop_service(key, self.env_root)
                
                # Unconditional taskkill fallback for all service processes to leave Task Manager clean
                import subprocess
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                for proc in ["nginx.exe", "httpd.exe", "mysqld.exe", "php-cgi.exe"]:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc], 
                        capture_output=True,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
            except Exception as e:
                logger.warning(f"Error stopping services during closeEvent: {e}")
            event.accept()

    def init_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        from PySide6.QtGui import QAction, QIcon
        import qtawesome as qta
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # Load app logo for system tray icon with fallback
        icon_path = self.get_icon_path()
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(qta.icon("fa5s.server", color="#ef4444"))
        
        tray_menu = QMenu()
        
        restore_action = QAction("Restore Window", self)
        restore_action.triggered.connect(self.showNormal)
        
        start_all_action = QAction("Start All Services", self)
        start_all_action.triggered.connect(self.tray_start_all_services)
        
        stop_all_action = QAction("Stop All Services", self)
        stop_all_action.triggered.connect(self.tray_stop_all_services)
        
        admin_db_action = QAction("Open phpMyAdmin", self)
        admin_db_action.triggered.connect(self.tray_open_phpmyadmin)
        
        exit_action = QAction("Exit Suite", self)
        exit_action.triggered.connect(self.force_exit)
        
        tray_menu.addAction(restore_action)
        tray_menu.addSeparator()
        tray_menu.addAction(start_all_action)
        tray_menu.addAction(stop_all_action)
        tray_menu.addAction(admin_db_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
    def tray_start_all_services(self):
        if not self.services_view:
            self.services_view = ServicesView(self)
            self.tab_containers[1][1].addWidget(self.services_view)
        self.services_view.start_all_services()
        
    def tray_stop_all_services(self):
        if not self.services_view:
            self.services_view = ServicesView(self)
            self.tab_containers[1][1].addWidget(self.services_view)
        self.services_view.stop_all_services()
        
    def tray_open_phpmyadmin(self):
        if not self.services_view:
            self.services_view = ServicesView(self)
            self.tab_containers[1][1].addWidget(self.services_view)
        self.services_view.open_phpmyadmin()

    def on_tray_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def force_exit(self):
        self.is_exiting = True
        self.tray_icon.hide()
        self.close()

    def get_icon_path(self):
        import sys
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, "assets", "app_logo.ico")
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "app_logo.ico")

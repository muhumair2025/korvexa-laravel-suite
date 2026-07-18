import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QDialog, QTextBrowser, QPushButton, QProgressBar, QLabel, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal

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
        
        # Check for updates in the background
        self.update_worker = UpdateCheckWorker()
        self.update_worker.update_available.connect(self.show_update_dialog)
        self.update_worker.start()
        
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
        
    def stop_all_threads(self):
        logger.info("Stopping all background threads...")
        
        # 1. Stop ServicesView workers
        if getattr(self, 'services_view', None) and self.services_view is not None:
            try:
                if getattr(self.services_view, 'status_worker', None):
                    self.services_view.status_worker.stop()
                    self.services_view.status_worker.wait(1000)
                if getattr(self.services_view, 'batch_worker', None) and self.services_view.batch_worker.isRunning():
                    self.services_view.batch_worker.wait(1000)
                for key, worker in list(getattr(self.services_view, 'active_action_workers', {}).items()):
                    if worker.isRunning():
                        worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning services_view threads: {e}")

        # 2. Stop SwitcherView workers
        if getattr(self, 'switcher_view', None) and self.switcher_view is not None:
            try:
                for attr in ['worker', 'scan_worker', 'switch_worker', 'restart_worker']:
                    worker = getattr(self.switcher_view, attr, None)
                    if worker and worker.isRunning():
                        try:
                            if hasattr(worker, 'stop'):
                                worker.stop()
                        except Exception:
                            pass
                        worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning switcher_view threads: {e}")

        # 3. Stop VHostView workers
        if getattr(self, 'vhost_view', None) and self.vhost_view is not None:
            try:
                worker = getattr(self.vhost_view, 'restart_worker', None)
                if worker and worker.isRunning():
                    worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning vhost_view threads: {e}")

        # 4. Stop LaravelView workers
        if getattr(self, 'laravel_view', None) and self.laravel_view is not None:
            try:
                for attr in ['create_worker', 'artisan_worker']:
                    worker = getattr(self.laravel_view, attr, None)
                    if worker and worker.isRunning():
                        if hasattr(worker, 'current_process') and worker.current_process is not None:
                            try:
                                worker.current_process.terminate()
                            except Exception:
                                pass
                        worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning laravel_view threads: {e}")

        # 5. Stop DatabaseView workers
        if getattr(self, 'database_view', None) and self.database_view is not None:
            try:
                worker = getattr(self.database_view, 'query_worker', None)
                if worker and worker.isRunning():
                    worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning database_view threads: {e}")

        # 6. Stop OnboardingView workers
        if getattr(self, 'onboarding_view', None) and self.onboarding_view is not None:
            try:
                for attr in ['scan_worker', 'worker']:
                    worker = getattr(self.onboarding_view, attr, None)
                    if worker and worker.isRunning():
                        try:
                            if hasattr(worker, 'pause'):
                                worker.pause()
                        except Exception:
                            pass
                        if hasattr(worker, 'current_process') and worker.current_process is not None:
                            try:
                                worker.current_process.terminate()
                            except Exception:
                                pass
                        worker.wait(1000)
            except Exception as e:
                logger.warning(f"Error cleaning onboarding_view threads: {e}")

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
                # Stop all background threads gracefully first
                self.stop_all_threads()
                
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
            
            try:
                self.settings.sync()
            except Exception:
                pass
                
            event.accept()
            
            # Hard exit the process to prevent any PySide6/QThread teardown deadlocks in Python interpreter
            import os
            os._exit(0)

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

    def show_update_dialog(self, update_info):
        dialog = UpdateDialog(update_info, self)
        if dialog.exec() == QDialog.Accepted:
            progress_dialog = UpdateProgressDialog(update_info["download_url"], self)
            progress_dialog.exec()

class UpdateCheckWorker(QThread):
    update_available = Signal(dict)
    
    def run(self):
        try:
            import urllib.request
            import json
            import ssl
            context = ssl._create_unverified_context()
            
            url = "https://api.github.com/repos/muhumair2025/korvexa-laravel-suite/releases/latest"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10, context=context) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            tag_name = data.get("tag_name", "").strip()
            latest_version = tag_name.lstrip("vV")
            
            # Use centralized APP_VERSION
            from core.version import APP_VERSION
            current_version = APP_VERSION
            
            def parse_version(v_str):
                return tuple(int(x) for x in v_str.split(".") if x.isdigit())
                
            if parse_version(latest_version) > parse_version(current_version):
                download_url = None
                assets = data.get("assets", [])
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe") or name.endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        break
                if not download_url:
                    download_url = data.get("html_url")
                    
                update_info = {
                    "version": latest_version,
                    "title": data.get("name", f"Version {latest_version}"),
                    "description": data.get("body", "No description provided."),
                    "download_url": download_url,
                    "tag": tag_name
                }
                self.update_available.emit(update_info)
        except Exception as e:
            logger.debug(f"Failed to check for updates: {e}")

class UpdateDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("Software Update Available")
        self.resize(500, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        title_lbl = QLabel("A new version of Laravel Development Suite is available!")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
        layout.addWidget(title_lbl)
        
        from core.version import APP_VERSION
        info_lbl = QLabel(f"New Version: {update_info['tag']} (Current Version: v{APP_VERSION})")
        info_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(info_lbl)
        
        desc_lbl = QLabel("Release Notes:")
        desc_lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(desc_lbl)
        
        self.notes_browser = QTextBrowser()
        self.notes_browser.setHtml(self.markdown_to_html(update_info["description"]))
        layout.addWidget(self.notes_browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_close = QPushButton("Skip Version")
        self.btn_close.setFixedHeight(28)
        self.btn_close.clicked.connect(self.reject)
        
        self.btn_update = QPushButton("Update Now")
        self.btn_update.setFixedHeight(28)
        self.btn_update.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;")
        self.btn_update.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)
        
    def markdown_to_html(self, text):
        import re
        # Escape HTML characters
        html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Replace code blocks
        html = re.sub(r"```(.*?)\n(.*?)```", r"<pre style='background-color:#1e293b; padding:8px; border-radius:4px;'><code>\2</code></pre>", html, flags=re.DOTALL)
        html = re.sub(r"`(.*?)`", r"<code style='background-color:#1e293b; padding:2px 4px; border-radius:3px;'>\1</code>", html)
        
        lines = html.split("\n")
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    formatted_lines.append("</ul>")
                    in_list = False
                formatted_lines.append("<br>")
                continue
                
            # Headers
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if header_match:
                if in_list:
                    formatted_lines.append("</ul>")
                    in_list = False
                level = len(header_match.group(1))
                content = header_match.group(2)
                # handle bold inside header
                content = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", content)
                formatted_lines.append(f"<h{level} style='margin-top:10px; margin-bottom:5px; color:#ef4444;'>{content}</h{level}>")
                continue
                
            # Lists
            list_match = re.match(r"^([-\*]|\d+\.)\s+(.*)$", line)
            if list_match:
                if not in_list:
                    formatted_lines.append("<ul style='margin-left: 15px;'>")
                    in_list = True
                content = list_match.group(2)
                # handle bold inside list
                content = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", content)
                formatted_lines.append(f"<li style='margin-bottom: 3px;'>{content}</li>")
                continue
                
            # If we were in list and line is not a list item
            if in_list:
                formatted_lines.append("</ul>")
                in_list = False
                
            # Bold
            line = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
            # Italics
            line = re.sub(r"\*(.*?)\*", r"<i>\1</i>", line)
            
            formatted_lines.append(f"<p style='margin: 2px 0;'>{line}</p>")
            
        if in_list:
            formatted_lines.append("</ul>")
            
        full_html = "\n".join(formatted_lines)
        return f"<div style='font-family: sans-serif; font-size: 11px; line-height: 1.4;'>{full_html}</div>"

class UpdateProgressDialog(QDialog):
    def __init__(self, download_url, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.setWindowTitle("Downloading Update")
        self.setFixedSize(350, 100)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        self.lbl = QLabel("Downloading update installer...")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        
        layout.addWidget(self.lbl)
        layout.addWidget(self.progress)
        
        self.worker = UpdateDownloaderWorker(download_url)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.start()
        
    def on_progress(self, percent, msg):
        self.progress.setValue(percent)
        self.lbl.setText(msg)
        
    def on_completed(self, success, file_path):
        if success and file_path and os.path.exists(file_path):
            if file_path.lower().endswith(".html") or not (file_path.lower().endswith(".exe") or file_path.lower().endswith(".zip")):
                import webbrowser
                webbrowser.open(self.download_url)
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
                return
                
            self.lbl.setText("Closing app and launching installer...")
            
            # Stop all services to avoid locks on dependencies/files
            try:
                import subprocess
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                for proc in ["nginx.exe", "httpd.exe", "mysqld.exe", "php-cgi.exe", "mailpit.exe"]:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc],
                        capture_output=True,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
            except Exception:
                pass
                
            try:
                os.startfile(file_path)
            except Exception:
                import subprocess
                subprocess.Popen([file_path], shell=True)
                
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        else:
            QMessageBox.critical(self, "Update Error", f"Failed to download update installer: {file_path}")
            self.reject()

class UpdateDownloaderWorker(QThread):
    progress = Signal(int, str)
    completed = Signal(bool, str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            import urllib.request
            import tempfile
            import ssl
            context = ssl._create_unverified_context()
            
            filename = self.url.split("/")[-1] or "update_setup.exe"
            temp_dir = tempfile.gettempdir()
            dest_path = os.path.join(temp_dir, filename)
            
            req = urllib.request.Request(
                self.url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=30, context=context) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                block_size = 8192
                
                with open(dest_path, 'wb') as f:
                    while True:
                        block = response.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        downloaded += len(block)
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            self.progress.emit(percent, f"Downloaded {downloaded/(1024*1024):.1f} MB / {total_size/(1024*1024):.1f} MB")
                            
            self.completed.emit(True, dest_path)
        except Exception as e:
            self.completed.emit(False, str(e))

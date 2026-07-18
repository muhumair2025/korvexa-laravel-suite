import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QGroupBox, QMessageBox, QProgressBar,
    QFrame, QScrollArea, QCheckBox, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
import qtawesome as qta

from core.detector import get_php_version
from core.installer import create_junction, configure_php
from gui.onboarding_view import InstallWorker
from core.services import get_service_status, start_service, stop_service

class ServiceRestartWorker(QThread):
    completed = Signal(bool, str)
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        try:
            running_services = []
            for srv in ["php-cgi", "nginx", "apache"]:
                if get_service_status(srv, self.env_root) == "Running":
                    running_services.append(srv)
                    
            for srv in running_services:
                stop_service(srv, self.env_root)
                
            log_dir = os.path.join(self.env_root, "logs")
            for srv in running_services:
                start_service(srv, self.env_root, log_dir)
                
            self.completed.emit(True, "Services restarted successfully.")
        except Exception as e:
            self.completed.emit(False, str(e))

logger = logging.getLogger(__name__)

class PhpScanWorker(QThread):
    completed = Signal(str, str, str, list)  # cli_version, active_junction, target, installed_versions
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        try:
            php_dir = os.path.join(self.env_root, "php")
            active_junction = os.path.join(php_dir, "active")
            
            cli_version = get_php_version()
            
            target = "None"
            if os.path.exists(active_junction):
                try:
                    target = os.readlink(active_junction)
                except Exception:
                    target = "Unknown"
                    
            installed_versions = []
            if os.path.exists(php_dir):
                for item in os.listdir(php_dir):
                    dir_path = os.path.join(php_dir, item)
                    if os.path.isdir(dir_path) and item != "active":
                        exe_path = os.path.join(dir_path, "php.exe")
                        if os.path.exists(exe_path):
                            ver = get_php_version(exe_path)
                            if ver:
                                installed_versions.append((item, ver))
                                
            self.completed.emit(cli_version or "", active_junction, target, installed_versions)
        except Exception as e:
            logger.error(f"Error in PhpScanWorker: {e}")
            self.completed.emit("", "", "", [])

class PhpSwitchWorker(QThread):
    completed = Signal(bool, str)
    
    def __init__(self, target_dir, active_junction, running_services, env_root, log_dir):
        super().__init__()
        self.target_dir = target_dir
        self.active_junction = active_junction
        self.running_services = running_services
        self.env_root = env_root
        self.log_dir = log_dir
        
    def run(self):
        try:
            for srv in self.running_services:
                stop_service(srv, self.env_root)
                
            success = create_junction(self.target_dir, self.active_junction)
            if not success:
                self.completed.emit(False, "Failed to link directory junction.")
                return
                
            configure_php(self.target_dir)
            
            for srv in self.running_services:
                start_service(srv, self.env_root, self.log_dir)
                
            self.completed.emit(True, "PHP runtime switched successfully.")
        except Exception as e:
            self.completed.emit(False, f"Exception: {e}")

class SwitcherView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.worker = None
        self.scan_worker = None
        self.switch_worker = None
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Header
        title_label = QLabel("PHP Version Manager")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        sub_label = QLabel("Switch PHP runtimes globally and manage extensions. Web servers will be auto-restarted to apply changes.")
        sub_label.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(sub_label)
        
        # Split body layout
        body_layout = QHBoxLayout()
        body_layout.setSpacing(15)
        
        # Left Panel (PHP Runtimes)
        left_panel = QFrame()
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(12)
        
        # 1. Active status group box
        status_group = QGroupBox("Active PHP Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(10, 15, 10, 10)
        
        self.active_ver_lbl = QLabel("Active PHP Version: Checking...")
        self.active_ver_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #008000;")
        
        self.junction_path_lbl = QLabel("Junction Link: Not configured")
        self.junction_path_lbl.setStyleSheet("font-size: 11px; font-family: 'Consolas', monospace;")
        
        self.target_path_lbl = QLabel("Resolves to: None")
        self.target_path_lbl.setStyleSheet("font-size: 11px; font-family: 'Consolas', monospace;")
        
        status_layout.addWidget(self.active_ver_lbl)
        status_layout.addWidget(self.junction_path_lbl)
        status_layout.addWidget(self.target_path_lbl)
        left_lay.addWidget(status_group)
        
        # 2. Switcher Control Group Box
        control_group = QGroupBox("Switch Version")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(10, 15, 10, 10)
        control_layout.setSpacing(10)
        
        select_row = QHBoxLayout()
        self.combo_versions = QComboBox()
        self.combo_versions.setMinimumWidth(200)
        self.combo_versions.setFixedHeight(24)
        select_row.addWidget(self.combo_versions)
        
        self.btn_switch = QPushButton("Apply Switch")
        self.btn_switch.setFixedSize(110, 24)
        self.btn_switch.setStyleSheet("font-weight: bold;")
        self.btn_switch.clicked.connect(self.switch_version)
        select_row.addWidget(self.btn_switch)
        select_row.addStretch()
        control_layout.addLayout(select_row)
        left_lay.addWidget(control_group)
        
        # 3. Download runtimes Group Box
        download_group = QGroupBox("Get Alternative PHP Runtimes")
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(10, 15, 10, 10)
        download_layout.setSpacing(10)
        
        # PHP 8.3 Row
        dl_row_83 = QHBoxLayout()
        dl_desc_83 = QLabel("Download PHP 8.3 standard runtime.")
        dl_desc_83.setStyleSheet("font-size: 11px;")
        dl_row_83.addWidget(dl_desc_83)
        
        self.btn_dl_83 = QPushButton("Get PHP 8.3")
        self.btn_dl_83.setFixedSize(140, 24)
        self.btn_dl_83.setIcon(qta.icon("fa5s.download"))
        self.btn_dl_83.setIconSize(QSize(11, 11))
        self.btn_dl_83.clicked.connect(self.download_php83)
        dl_row_83.addWidget(self.btn_dl_83)
        download_layout.addLayout(dl_row_83)
        
        # PHP 8.4 Row
        dl_row_84 = QHBoxLayout()
        dl_desc_84 = QLabel("Download PHP 8.4 standard runtime.")
        dl_desc_84.setStyleSheet("font-size: 11px;")
        dl_row_84.addWidget(dl_desc_84)
        
        self.btn_dl_84 = QPushButton("Get PHP 8.4")
        self.btn_dl_84.setFixedSize(140, 24)
        self.btn_dl_84.setIcon(qta.icon("fa5s.download"))
        self.btn_dl_84.setIconSize(QSize(11, 11))
        self.btn_dl_84.clicked.connect(self.download_php84)
        dl_row_84.addWidget(self.btn_dl_84)
        download_layout.addLayout(dl_row_84)
        
        # PHP 8.5 Row
        dl_row_85 = QHBoxLayout()
        dl_desc_85 = QLabel("Download PHP 8.5 performance runtime.")
        dl_desc_85.setStyleSheet("font-size: 11px;")
        dl_row_85.addWidget(dl_desc_85)
        
        self.btn_dl_85 = QPushButton("Get PHP 8.5")
        self.btn_dl_85.setFixedSize(140, 24)
        self.btn_dl_85.setIcon(qta.icon("fa5s.download"))
        self.btn_dl_85.setIconSize(QSize(11, 11))
        self.btn_dl_85.clicked.connect(self.download_php85)
        dl_row_85.addWidget(self.btn_dl_85)
        download_layout.addLayout(dl_row_85)
        
        self.dl_status_lbl = QLabel("")
        self.dl_status_lbl.setStyleSheet("font-size: 11px;")
        self.dl_progress = QProgressBar()
        self.dl_progress.setValue(0)
        self.dl_progress.setFixedHeight(14)
        self.dl_progress.setVisible(False)
        
        download_layout.addWidget(self.dl_status_lbl)
        download_layout.addWidget(self.dl_progress)
        left_lay.addWidget(download_group)
        left_lay.addStretch()
        
        body_layout.addWidget(left_panel, 1)
        
        # Right Panel (Extensions Manager)
        self.ext_group = QGroupBox("PHP Extensions Manager")
        self.ext_group.setStyleSheet("QGroupBox { font-weight: bold; color: #ef4444; }")
        ext_lay = QVBoxLayout(self.ext_group)
        ext_lay.setContentsMargins(10, 15, 10, 10)
        ext_lay.setSpacing(8)
        
        ext_desc = QLabel("Configure PHP extensions and ini settings for the active environment. Web servers will restart automatically to apply changes.")
        ext_desc.setStyleSheet("font-size: 10px; color: #64748b;")
        ext_desc.setWordWrap(True)
        ext_lay.addWidget(ext_desc)
        
        # Search Box for Extensions
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search extensions...")
        self.search_box.setFixedHeight(24)
        self.search_box.textChanged.connect(self.filter_extensions)
        self.search_action = self.search_box.addAction(qta.icon("fa5s.search", color=self.main_win.get_icon_color()), QLineEdit.LeadingPosition)
        ext_lay.addWidget(self.search_box)
        
        # Scroll area for extension items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 5, 0, 5)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addStretch() # Bottom stretch spacer
        
        scroll.setWidget(scroll_content)
        ext_lay.addWidget(scroll)
        
        # PHP ini Configuration variables Group Box
        self.cfg_group = QGroupBox("PHP ini Configuration")
        self.cfg_group.setStyleSheet("QGroupBox { font-weight: bold; color: #ef4444; }")
        cfg_form = QFormLayout(self.cfg_group)
        cfg_form.setSpacing(6)
        cfg_form.setContentsMargins(6, 12, 6, 6)
        
        self.cfg_fields = {}
        from core.php_extensions import PHP_CONFIG_VARIABLES
        for key, meta in PHP_CONFIG_VARIABLES.items():
            field = QLineEdit()
            field.setFixedHeight(22)
            field.setToolTip(meta["desc"])
            cfg_form.addRow(f"{meta['name']}:", field)
            self.cfg_fields[key] = field
            
        self.btn_save_cfg = QPushButton("Save & Apply Config")
        self.btn_save_cfg.setFixedHeight(24)
        self.btn_save_cfg.setStyleSheet("font-weight: bold;")
        self.btn_save_cfg.clicked.connect(self.save_php_configs)
        cfg_form.addRow("", self.btn_save_cfg)
        
        ext_lay.addWidget(self.cfg_group)
        
        # Extensions active status label
        self.ext_status_lbl = QLabel("Extensions ready.")
        self.ext_status_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #10b981;")
        ext_lay.addWidget(self.ext_status_lbl)
        
        body_layout.addWidget(self.ext_group, 1.2)
        
        layout.addLayout(body_layout)
        self.refresh_icons()
        
    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_dl_83.setIcon(qta.icon("fa5s.download", color=color))
        self.btn_dl_84.setIcon(qta.icon("fa5s.download", color=color))
        self.btn_dl_85.setIcon(qta.icon("fa5s.download", color=color))
        if hasattr(self, 'search_action') and self.search_action:
            self.search_action.setIcon(qta.icon("fa5s.search", color=color))
        
    def refresh_status(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
            
        def get_php_state():
            php_dir = os.path.join(self.main_win.env_root, "php")
            active_junction = os.path.join(php_dir, "active")
            mtime = 0
            if os.path.exists(php_dir):
                try:
                    mtime = os.path.getmtime(php_dir)
                except Exception:
                    pass
            target = "None"
            if os.path.exists(active_junction):
                try:
                    target = os.readlink(active_junction)
                except Exception:
                    target = "Unknown"
            return (mtime, target)

        from core.cache import cache_manager
        cache_key = f"php_status:{self.main_win.env_root}"
        cached = cache_manager.get(cache_key, validator_func=get_php_state)
        
        if cached is not None:
            cli_version, active_junction, target, installed_versions = cached
            self.on_scan_finished(cli_version, active_junction, target, installed_versions)
            return

        self.active_ver_lbl.setText("Active PHP Version: Checking...")
        self.combo_versions.setEnabled(False)
        self.btn_switch.setEnabled(False)
        
        self.scan_worker = PhpScanWorker(self.main_win.env_root)
        self.scan_worker.completed.connect(lambda c, a, t, i: self.on_scan_finished_and_cache(c, a, t, i, get_php_state))
        self.scan_worker.start()

    def on_scan_finished_and_cache(self, cli_version, active_junction, target, installed_versions, get_state_func):
        from core.cache import cache_manager
        cache_key = f"php_status:{self.main_win.env_root}"
        cache_manager.set(cache_key, (cli_version, active_junction, target, installed_versions), validator_state=get_state_func())
        self.on_scan_finished(cli_version, active_junction, target, installed_versions)
        
    def on_scan_finished(self, cli_version, active_junction, target, installed_versions):
        if cli_version:
            self.active_ver_lbl.setText(f"Active PHP Version: v{cli_version}")
            self.active_ver_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #10b981;")
        else:
            self.active_ver_lbl.setText("Active PHP Version: Not in System PATH")
            self.active_ver_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #ef4444;")
            
        if active_junction and os.path.exists(active_junction):
            self.junction_path_lbl.setText(f"Junction Link: {active_junction}")
            self.target_path_lbl.setText(f"Resolves to: {target}")
        else:
            self.junction_path_lbl.setText("Junction Link: Not configured")
            self.target_path_lbl.setText(f"Resolves to: {target}")
            
        self.combo_versions.clear()
        for folder_name, ver in installed_versions:
            self.combo_versions.addItem(f"PHP {ver} ({folder_name})", folder_name)
            
        if active_junction and os.path.exists(active_junction):
            folder_name = os.path.basename(target)
            index = self.combo_versions.findData(folder_name)
            if index >= 0:
                self.combo_versions.setCurrentIndex(index)
                
        has_versions = self.combo_versions.count() > 0
        
        is_dl_running = self.worker and self.worker.isRunning()
        is_switch_running = self.switch_worker and self.switch_worker.isRunning()
        
        if is_dl_running or is_switch_running:
            self.btn_dl_83.setEnabled(False)
            self.btn_dl_84.setEnabled(False)
            self.btn_dl_85.setEnabled(False)
            self.combo_versions.setEnabled(False)
            self.btn_switch.setEnabled(False)
        else:
            self.combo_versions.setEnabled(has_versions)
            self.btn_switch.setEnabled(has_versions)
            
            php_dir = os.path.join(self.main_win.env_root, "php")
            
            # Check 8.3
            php83_dir = os.path.join(php_dir, "php-8.3.8")
            if os.path.exists(os.path.join(php83_dir, "php.exe")):
                self.btn_dl_83.setEnabled(False)
                self.btn_dl_83.setText("PHP 8.3 Registered")
            else:
                self.btn_dl_83.setEnabled(True)
                self.btn_dl_83.setText("Get PHP 8.3")
                
            # Check 8.4
            php84_dir = os.path.join(php_dir, "php-8.4.3")
            if os.path.exists(os.path.join(php84_dir, "php.exe")):
                self.btn_dl_84.setEnabled(False)
                self.btn_dl_84.setText("PHP 8.4 Registered")
            else:
                self.btn_dl_84.setEnabled(True)
                self.btn_dl_84.setText("Get PHP 8.4")
                
            # Check 8.5
            php85_dir = os.path.join(php_dir, "php-8.5.1")
            if os.path.exists(os.path.join(php85_dir, "php.exe")):
                self.btn_dl_85.setEnabled(False)
                self.btn_dl_85.setText("PHP 8.5 Registered")
            else:
                self.btn_dl_85.setEnabled(True)
                self.btn_dl_85.setText("Get PHP 8.5")
                
        self.load_extensions()
        
    def switch_version(self):
        if self.switch_worker and self.switch_worker.isRunning():
            return
            
        folder_name = self.combo_versions.currentData()
        if not folder_name:
            return
            
        php_dir = os.path.join(self.main_win.env_root, "php")
        target_dir = os.path.join(php_dir, folder_name)
        active_junction = os.path.join(php_dir, "active")
        
        running_services = []
        for srv in ["nginx", "apache", "php-cgi"]:
            if get_service_status(srv, self.main_win.env_root) == "Running":
                running_services.append(srv)
                
        if running_services:
            reply = QMessageBox.question(
                self, 
                "Services Restart Alert",
                f"The following services are running and will be stopped to switch PHP versions: {', '.join(running_services)}.\n\nDo you wish to proceed?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
                
        # Lock UI
        self.btn_switch.setEnabled(False)
        self.combo_versions.setEnabled(False)
        self.btn_dl_83.setEnabled(False)
        self.btn_dl_84.setEnabled(False)
        self.btn_dl_85.setEnabled(False)
        
        self.switch_worker = PhpSwitchWorker(
            target_dir, active_junction, running_services, 
            self.main_win.env_root, self.main_win.log_dir
        )
        self.switch_worker.completed.connect(self.on_switch_finished)
        self.switch_worker.start()
        
    def on_switch_finished(self, success, message):
        self.switch_worker = None
        self.refresh_status()
        if success:
            QMessageBox.information(self, "PHP Switched", message)
        else:
            QMessageBox.critical(self, "Junction Error", f"Failed to switch PHP runtime: {message}")
            
    def download_php83(self):
        self.download_php_version("php83")
        
    def download_php84(self):
        self.download_php_version("php84")
        
    def download_php85(self):
        self.download_php_version("php85")
        
    def download_php_version(self, version_key):
        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.btn_dl_83.setEnabled(False)
        self.btn_dl_84.setEnabled(False)
        self.btn_dl_85.setEnabled(False)
        self.combo_versions.setEnabled(False)
        self.btn_switch.setEnabled(False)
        
        self.worker = InstallWorker(version_key, self.main_win.env_root)
        self.worker.progress.connect(self.on_dl_progress)
        self.worker.completed.connect(self.on_dl_finished)
        self.worker.start()
        
    def on_dl_progress(self, msg, percentage):
        self.dl_status_lbl.setText(msg)
        self.dl_progress.setValue(percentage)
        
    def on_dl_finished(self, tool_name, status, error_msg=""):
        self.dl_progress.setVisible(False)
        self.dl_status_lbl.setText("")
        self.refresh_status()
        if status == "success":
            QMessageBox.information(self, "PHP Download Complete", f"{tool_name.upper()} downloaded and registered successfully. You can select it in the dropdown.")
        else:
            QMessageBox.critical(self, "Download Error", f"Could not download {tool_name.upper()}.\n\nDetails: {error_msg}")
            
    def load_extensions(self):
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        active_ini = os.path.join(self.main_win.env_root, "php", "active", "php.ini")
        if not os.path.exists(active_ini):
            no_ini_lbl = QLabel("Active php.ini not found. Switch PHP version or install one first.")
            no_ini_lbl.setStyleSheet("color: #ef4444; font-size: 11px;")
            self.scroll_layout.insertWidget(0, no_ini_lbl)
            return
            
        from core.php_extensions import get_extension_states, POPULAR_EXTENSIONS, is_extension_available
        states = get_extension_states(active_ini)
        
        # Discover all actual DLL files inside active ext/ directory
        ext_dir = os.path.join(self.main_win.env_root, "php", "active", "ext")
        discovered_keys = set()
        if os.path.exists(ext_dir):
            try:
                for file in os.listdir(ext_dir):
                    if file.lower().endswith(".dll"):
                        if file.lower().startswith("php_"):
                            name_key = file[4:-4].lower()
                            discovered_keys.add(name_key)
                        elif "xdebug" in file.lower():
                            discovered_keys.add("xdebug")
                        elif "opcache" in file.lower():
                            discovered_keys.add("opcache")
            except Exception:
                pass

        # Build consolidated extensions catalog to show
        all_exts = {}
        # A. Start with POPULAR_EXTENSIONS
        for key, meta in POPULAR_EXTENSIONS.items():
            all_exts[key] = meta.copy()
            
        # B. Add discovered DLL keys
        for key in discovered_keys:
            if key not in all_exts:
                all_exts[key] = {
                    "name": key.upper(),
                    "desc": f"Discovered local PHP extension library ({key}.dll).",
                    "type": "extension"
                }
                
        # C. Add keys found in php.ini
        for key, state in states.items():
            if key not in all_exts:
                all_exts[key] = {
                    "name": key.upper(),
                    "desc": f"Extension defined in php.ini ({key}).",
                    "type": state["type"]
                }
                
        is_dark = getattr(self.main_win, 'theme', 'dark') == "dark"
        card_style = (
            "QFrame {"
            "  background-color: #1e293b;"
            "  border: 1px solid #334155;"
            "  border-radius: 4px;"
            "}"
            if is_dark else
            "QFrame {"
            "  background-color: #f8fafc;"
            "  border: 1px solid #e2e8f0;"
            "  border-radius: 4px;"
            "}"
        )
        
        query = self.search_box.text().strip().lower()
        
        inserted_idx = 0
        for key, meta in all_exts.items():
            if query and query not in meta["name"].lower() and query not in meta["desc"].lower():
                continue
                
            state = states.get(key, {"enabled": False, "found": False})
            available = is_extension_available(self.main_win.env_root, key)
            
            card = QFrame()
            card.setStyleSheet(card_style)
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(8, 6, 8, 6)
            
            text_lay = QVBoxLayout()
            name_lbl = QLabel(meta["name"])
            name_lbl.setStyleSheet("font-size: 12px; font-weight: bold; border: none; background: transparent;")
            
            desc_lbl = QLabel(meta["desc"])
            desc_lbl.setStyleSheet("font-size: 10px; color: #94a3b8; border: none; background: transparent;")
            desc_lbl.setWordWrap(True)
            
            text_lay.addWidget(name_lbl)
            text_lay.addWidget(desc_lbl)
            card_lay.addLayout(text_lay, 3)
            
            status_tag = QLabel()
            status_tag.setStyleSheet("font-size: 10px; font-weight: bold; border: none; background: transparent;")
            
            chk = QCheckBox()
            chk.setChecked(state["enabled"])
            
            if not available:
                status_tag.setText("Missing DLL")
                status_tag.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold; border: none; background: transparent;")
                chk.setEnabled(False)
                chk.setToolTip("DLL not found in php/active/ext/")
            else:
                if state["enabled"]:
                    status_tag.setText("Active")
                    status_tag.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold; border: none; background: transparent;")
                else:
                    status_tag.setText("Disabled")
                    status_tag.setStyleSheet("color: #64748b; font-size: 10px; font-weight: normal; border: none; background: transparent;")
                    
            chk.clicked.connect(lambda checked, k=key: self.toggle_extension(k, checked))
            
            card_lay.addWidget(status_tag, 1, Qt.AlignVCenter | Qt.AlignRight)
            card_lay.addWidget(chk, 0, Qt.AlignVCenter)
            
            self.scroll_layout.insertWidget(inserted_idx, card)
            inserted_idx += 1
            
        from core.php_extensions import get_config_variables
        config_vals = get_config_variables(active_ini)
        for k, val in config_vals.items():
            if k in self.cfg_fields:
                self.cfg_fields[k].blockSignals(True)
                self.cfg_fields[k].setText(val)
                self.cfg_fields[k].blockSignals(False)
                
    def filter_extensions(self, text):
        self.load_extensions()
        
    def toggle_extension(self, key, enable):
        active_ini = os.path.join(self.main_win.env_root, "php", "active", "php.ini")
        if not os.path.exists(active_ini):
            return
            
        from core.php_extensions import set_extension_state
        success, msg = set_extension_state(active_ini, key, enable)
        
        if success:
            self.ext_status_lbl.setText(f"Applying change: {key}...")
            self.ext_status_lbl.setStyleSheet("color: #eab308; font-weight: bold;")
            self.restart_services_after_extension_change()
        else:
            QMessageBox.critical(self, "Extension Error", f"Failed to apply extension state:\n{msg}")
            self.load_extensions()
            
    def save_php_configs(self):
        active_ini = os.path.join(self.main_win.env_root, "php", "active", "php.ini")
        if not os.path.exists(active_ini):
            QMessageBox.warning(self, "Config File Missing", "Active php.ini not found.")
            return
            
        from core.php_extensions import set_config_variable
        
        changed = []
        for key, field in self.cfg_fields.items():
            val = field.text().strip()
            if val:
                success, msg = set_config_variable(active_ini, key, val)
                if success:
                    changed.append(key)
                else:
                    QMessageBox.critical(self, "Config Error", f"Failed to save {key}:\n{msg}")
                    return
                    
        if changed:
            self.ext_status_lbl.setText("Applying configurations...")
            self.ext_status_lbl.setStyleSheet("color: #eab308; font-weight: bold;")
            self.restart_services_after_extension_change()
        else:
            QMessageBox.information(self, "No Changes", "No configuration fields were updated.")
            
    def restart_services_after_extension_change(self):
        self.ext_group.setEnabled(False)
        self.ext_status_lbl.setText("Restarting web services to apply settings...")
        self.ext_status_lbl.setStyleSheet("color: #f59e0b; font-weight: bold;")
        
        self.restart_worker = ServiceRestartWorker(self.main_win.env_root)
        self.restart_worker.completed.connect(self.on_extension_restart_finished)
        self.restart_worker.start()
        
    def on_extension_restart_finished(self, success, msg):
        self.ext_group.setEnabled(True)
        if success:
            self.ext_status_lbl.setText("PHP configuration updated and services restarted!")
            self.ext_status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.ext_status_lbl.setText("Settings active, but services failed to restart.")
            self.ext_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
            QMessageBox.warning(self, "Restart Warning", f"Could not restart web services:\n{msg}")
            
        self.load_extensions()

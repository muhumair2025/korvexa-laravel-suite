import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QGroupBox, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
import qtawesome as qta

from core.detector import get_php_version
from core.installer import create_junction, configure_php
from gui.onboarding_view import InstallWorker
from core.services import get_service_status, start_service, stop_service

logger = logging.getLogger(__name__)

class PhpScanWorker(QThread):
    finished = Signal(str, str, str, list)  # cli_version, active_junction, target, installed_versions
    
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
                                
            self.finished.emit(cli_version or "", active_junction, target, installed_versions)
        except Exception as e:
            logger.error(f"Error in PhpScanWorker: {e}")
            self.finished.emit("", "", "", [])

class PhpSwitchWorker(QThread):
    finished = Signal(bool, str)
    
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
                self.finished.emit(False, "Failed to link directory junction.")
                return
                
            configure_php(self.target_dir)
            
            for srv in self.running_services:
                start_service(srv, self.env_root, self.log_dir)
                
            self.finished.emit(True, "PHP runtime switched successfully.")
        except Exception as e:
            self.finished.emit(False, f"Exception: {e}")

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
        layout.setSpacing(15)
        
        # Header
        title_label = QLabel("PHP Version Manager")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        sub_label = QLabel("Switch between installed PHP runtimes globally. Running servers will be auto-restarted to pick up changes.")
        sub_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(sub_label)
        
        # Active status group box
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
        layout.addWidget(status_group)
        
        # Switcher Control Group Box
        control_group = QGroupBox("Switch Version")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(10, 15, 10, 10)
        control_layout.setSpacing(10)
        
        select_row = QHBoxLayout()
        self.combo_versions = QComboBox()
        self.combo_versions.setMinimumWidth(220)
        self.combo_versions.setFixedHeight(24)
        select_row.addWidget(self.combo_versions)
        
        self.btn_switch = QPushButton("Apply Switch")
        self.btn_switch.setFixedSize(110, 24)
        self.btn_switch.setStyleSheet("font-weight: bold;")
        self.btn_switch.clicked.connect(self.switch_version)
        select_row.addWidget(self.btn_switch)
        select_row.addStretch()
        control_layout.addLayout(select_row)
        layout.addWidget(control_group)
        
        # Download runtimes Group Box
        download_group = QGroupBox("Get Alternative PHP Runtimes")
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(10, 15, 10, 10)
        download_layout.setSpacing(10)
        
        dl_row = QHBoxLayout()
        dl_desc = QLabel("Download and register PHP 8.3 on your machine to test scripts against updated releases.")
        dl_desc.setStyleSheet("font-size: 11px;")
        dl_row.addWidget(dl_desc)
        
        self.btn_dl_83 = QPushButton("Get PHP 8.3")
        self.btn_dl_83.setFixedSize(110, 24)
        self.btn_dl_83.setIcon(qta.icon("fa5s.download"))
        self.btn_dl_83.setIconSize(QSize(11, 11))
        self.btn_dl_83.clicked.connect(self.download_php83)
        dl_row.addWidget(self.btn_dl_83)
        download_layout.addLayout(dl_row)
        
        self.dl_status_lbl = QLabel("")
        self.dl_status_lbl.setStyleSheet("font-size: 11px;")
        self.dl_progress = QProgressBar()
        self.dl_progress.setValue(0)
        self.dl_progress.setFixedHeight(14)
        self.dl_progress.setVisible(False)
        
        download_layout.addWidget(self.dl_status_lbl)
        download_layout.addWidget(self.dl_progress)
        
        layout.addWidget(download_group)
        layout.addStretch()
        
    def refresh_status(self):
        php_dir = os.path.join(self.main_win.env_root, "php")
        active_junction = os.path.join(php_dir, "active")
        
        cli_version = get_php_version()
        if cli_version:
            self.active_ver_lbl.setText(f"Active PHP Version: v{cli_version}")
            self.active_ver_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #008000;")
        else:
            self.active_ver_lbl.setText("Active PHP Version: Not in System PATH")
            self.active_ver_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #d13438;")
            
        if os.path.exists(active_junction):
            self.junction_path_lbl.setText(f"Junction Link: {active_junction}")
            try:
                target = os.readlink(active_junction)
                self.target_path_lbl.setText(f"Resolves to: {target}")
            except Exception:
                self.target_path_lbl.setText("Resolves to: Unknown (Verify symbolic rights)")
        else:
            self.junction_path_lbl.setText("Junction Link: Not configured")
            self.target_path_lbl.setText("Resolves to: None")
            
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
                            
        self.combo_versions.clear()
        for folder_name, ver in installed_versions:
            self.combo_versions.addItem(f"PHP {ver} ({folder_name})", folder_name)
            
        if os.path.exists(active_junction):
            try:
                target = os.readlink(active_junction)
                folder_name = os.path.basename(target)
                index = self.combo_versions.findData(folder_name)
                if index >= 0:
                    self.combo_versions.setCurrentIndex(index)
            except Exception:
                pass
                
        has_versions = self.combo_versions.count() > 0
        self.btn_switch.setEnabled(has_versions)
        
        php83_dir = os.path.join(php_dir, "php-8.3.8")
        if os.path.exists(os.path.join(php83_dir, "php.exe")):
            self.btn_dl_83.setEnabled(False)
            self.btn_dl_83.setText("PHP 8.3 Registered")
        else:
            self.btn_dl_83.setEnabled(True)
            self.btn_dl_83.setText("Get PHP 8.3")
            
        if self.worker and self.worker.isRunning():
            self.btn_dl_83.setEnabled(False)
            self.combo_versions.setEnabled(False)
            self.btn_switch.setEnabled(False)
        else:
            self.combo_versions.setEnabled(True)
            
    def refresh_status(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
            
        self.active_ver_lbl.setText("Active PHP Version: Checking...")
        self.combo_versions.setEnabled(False)
        self.btn_switch.setEnabled(False)
        
        self.scan_worker = PhpScanWorker(self.main_win.env_root)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.start()
        
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
            self.combo_versions.setEnabled(False)
            self.btn_switch.setEnabled(False)
        else:
            self.combo_versions.setEnabled(has_versions)
            self.btn_switch.setEnabled(has_versions)
            
            php_dir = os.path.join(self.main_win.env_root, "php")
            php83_dir = os.path.join(php_dir, "php-8.3.8")
            if os.path.exists(os.path.join(php83_dir, "php.exe")):
                self.btn_dl_83.setEnabled(False)
                self.btn_dl_83.setText("PHP 8.3 Registered")
            else:
                self.btn_dl_83.setEnabled(True)
                self.btn_dl_83.setText("Get PHP 8.3")
                
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
        
        self.switch_worker = PhpSwitchWorker(
            target_dir, active_junction, running_services, 
            self.main_win.env_root, self.main_win.log_dir
        )
        self.switch_worker.finished.connect(self.on_switch_finished)
        self.switch_worker.start()
        
    def on_switch_finished(self, success, message):
        self.switch_worker = None
        self.refresh_status()
        if success:
            QMessageBox.information(self, "PHP Switched", message)
        else:
            QMessageBox.critical(self, "Junction Error", f"Failed to switch PHP runtime: {message}")
            
    def download_php83(self):
        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.btn_dl_83.setEnabled(False)
        
        self.worker = InstallWorker("php83", self.main_win.env_root)
        self.worker.progress.connect(self.on_dl_progress)
        self.worker.finished.connect(self.on_dl_finished)
        self.worker.start()
        
    def on_dl_progress(self, msg, percentage):
        self.dl_status_lbl.setText(msg)
        self.dl_progress.setValue(percentage)
        
    def on_dl_finished(self, tool_name, success):
        self.dl_progress.setVisible(False)
        self.dl_status_lbl.setText("")
        self.refresh_status()
        if success:
            QMessageBox.information(self, "PHP Download Complete", "PHP 8.3 downloaded and registered successfully. You can select it in the dropdown.")
        else:
            QMessageBox.critical(self, "Download Error", "Could not download PHP 8.3. Please inspect stdout logs.")

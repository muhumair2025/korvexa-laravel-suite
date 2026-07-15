import os
import time
import logging
import webbrowser
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGroupBox, QGridLayout, QPlainTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
import qtawesome as qta

from core.services import (
    get_service_status, start_service, stop_service, is_process_running,
    get_running_processes_ctypes, SERVICES, is_port_in_use
)

logger = logging.getLogger(__name__)

class StatusWorker(QThread):
    status_updated = Signal(dict)
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        self.running = True
        
    def run(self):
        while self.running:
            try:
                running_procs = get_running_processes_ctypes()
                results = {}
                for name in ["nginx", "apache", "mysql", "php-cgi"]:
                    srv = SERVICES[name]
                    port_active = is_port_in_use(srv["port"])
                    proc_active = srv["process_name"].lower() in running_procs
                    
                    if port_active or proc_active:
                        status = "Running"
                    else:
                        status = "Stopped"
                    results[name] = status
                
                self.status_updated.emit(results)
            except Exception as e:
                logger.error(f"Error in StatusWorker: {e}")
                
            # Sleep in increments so we can exit quickly when stopped
            for _ in range(25):  # 2.5s total
                if not self.running:
                    break
                self.msleep(100)
                
    def stop(self):
        self.running = False


class ServiceActionWorker(QThread):
    completed = Signal(str, str, bool, str)  # key, action, success, message
    
    def __init__(self, key, action, env_root, log_dir):
        super().__init__()
        self.key = key
        self.action = action
        self.env_root = env_root
        self.log_dir = log_dir
        
    def run(self):
        try:
            if self.action == "start":
                if self.key == "nginx":
                    php_cgi_status = get_service_status("php-cgi", self.env_root)
                    if php_cgi_status == "Stopped":
                        start_service("php-cgi", self.env_root, self.log_dir)
                success, msg = start_service(self.key, self.env_root, self.log_dir)
            elif self.action == "stop":
                success, msg = stop_service(self.key, self.env_root)
            else:
                success, msg = False, "Unknown action"
            self.completed.emit(self.key, self.action, success, msg)
        except Exception as e:
            self.completed.emit(self.key, self.action, False, f"Exception: {e}")


class BatchServiceWorker(QThread):
    completed = Signal(bool, str)  # success, message
    log_msg = Signal(str)
    
    def __init__(self, action, env_root, log_dir):
        super().__init__()
        self.action = action  # "start" or "stop"
        self.env_root = env_root
        self.log_dir = log_dir
        
    def run(self):
        try:
            if self.action == "start":
                for key in ["mysql", "php-cgi", "nginx"]:
                    status = get_service_status(key, self.env_root)
                    if status == "Stopped":
                        self.log_msg.emit(f"Auto-launching {key}...")
                        start_service(key, self.env_root, self.log_dir)
            else:
                for key in ["nginx", "apache", "php-cgi", "mysql"]:
                    status = get_service_status(key, self.env_root)
                    if status == "Running":
                        self.log_msg.emit(f"Auto-stopping {key}...")
                        stop_service(key, self.env_root)
            self.completed.emit(True, "Batch operation completed.")
        except Exception as e:
            self.completed.emit(False, str(e))

logger = logging.getLogger(__name__)

class ServicesView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.status_worker = None
        self.active_action_workers = {}
        self.batch_worker = None
        
        self.init_ui()
        
    def start_timer(self):
        if not self.status_worker or not self.status_worker.isRunning():
            self.status_worker = StatusWorker(self.main_win.env_root)
            self.status_worker.status_updated.connect(self.on_status_updated)
            self.status_worker.start()
        
    def stop_timer(self):
        if self.status_worker and self.status_worker.isRunning():
            self.status_worker.stop()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Header Controls Horizontal Block
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_label = QLabel("Services & Port Control")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        sub_label = QLabel("Manage local database engines, web servers, and fast CGI gateways.")
        sub_label.setStyleSheet("font-size: 11px;")
        title_layout.addWidget(title_label)
        title_layout.addWidget(sub_label)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Action Buttons
        self.btn_start_all = QPushButton(" Start All")
        self.btn_start_all.setIcon(qta.icon("fa5s.play", color="#008000"))
        self.btn_start_all.clicked.connect(self.start_all_services)
        self.btn_start_all.setFixedSize(100, 26)
        
        self.btn_stop_all = QPushButton(" Stop All")
        self.btn_stop_all.setIcon(qta.icon("fa5s.stop", color="#d13438"))
        self.btn_stop_all.clicked.connect(self.stop_all_services)
        self.btn_stop_all.setFixedSize(100, 26)
        
        self.btn_shell = QPushButton(" Shell")
        self.btn_shell.setIcon(qta.icon("fa5s.terminal"))
        self.btn_shell.clicked.connect(self.open_environment_shell)
        self.btn_shell.setFixedSize(90, 26)
        
        header_layout.addWidget(self.btn_start_all)
        header_layout.addWidget(self.btn_stop_all)
        header_layout.addWidget(self.btn_shell)
        layout.addLayout(header_layout)
        
        # Main Dashboard Panel (Unified Groupbox Container)
        dashboard_group = QGroupBox("Modules")
        dashboard_layout = QVBoxLayout(dashboard_group)
        dashboard_layout.setContentsMargins(10, 15, 10, 10)
        
        # Grid layout for XAMPP-like columns
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(8)
        self.grid.setHorizontalSpacing(10)
        
        # Table Headers
        headers = ["Module Name", "Status & Ports", "Actions", "Admin Panel", "Config Files", "Logs View"]
        for col_idx, header_text in enumerate(headers):
            lbl = QLabel(header_text)
            lbl.setStyleSheet("font-weight: bold; color: #555555; font-size: 11px; border-bottom: 1px solid #cccccc; padding-bottom: 4px;")
            self.grid.addWidget(lbl, 0, col_idx)
            
        self.service_keys = ["nginx", "apache", "mysql", "php-cgi"]
        self.service_names = {
            "nginx": "Nginx Web Server",
            "apache": "Apache Web Server",
            "mysql": "MariaDB Database",
            "php-cgi": "PHP FastCGI Gateway"
        }
        self.service_ports = {
            "nginx": 8080,
            "apache": 8081,
            "mysql": 3306,
            "php-cgi": 9000
        }
        
        self.rows = {}
        for row_idx, key in enumerate(self.service_keys, start=1):
            row_widgets = self.create_service_row(row_idx, key)
            self.rows[key] = row_widgets
            
        dashboard_layout.addLayout(self.grid)
        layout.addWidget(dashboard_group)
        
        # Bottom Console (resembles XAMPP event logger)
        console_group = QGroupBox("Real-time Event Logger")
        console_layout = QVBoxLayout(console_group)
        console_layout.setContentsMargins(8, 10, 8, 8)
        
        self.console_text = QPlainTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px;")
        self.console_text.setFixedHeight(120)
        console_layout.addWidget(self.console_text)
        
        layout.addWidget(console_group)
        
        self.log_event("XAMPP/Laragon control dashboard loaded. Idle.")
        self.refresh_icons()
        
    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_shell.setIcon(qta.icon("fa5s.terminal", color=color))
        
    def create_service_row(self, row_idx, key):
        # 1. Module Name
        name_lbl = QLabel(self.service_names[key])
        name_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.grid.addWidget(name_lbl, row_idx, 0)
        
        # 2. Status Label (resembles XAMPP port/status highlight)
        status_lbl = QLabel("Stopped")
        status_lbl.setStyleSheet("color: #d13438; font-weight: bold; font-size: 11px;")
        self.grid.addWidget(status_lbl, row_idx, 1)
        
        # 3. Action button (Toggle Start/Stop)
        btn_action = QPushButton("Start")
        btn_action.setObjectName("start_btn")
        btn_action.setFixedHeight(22)
        btn_action.setFixedWidth(80)
        btn_action.clicked.connect(lambda: self.toggle_service(key))
        self.grid.addWidget(btn_action, row_idx, 2)
        
        # 4. Admin button
        btn_admin = QPushButton("Admin")
        btn_admin.setFixedHeight(22)
        btn_admin.setFixedWidth(80)
        btn_admin.setEnabled(False)
        btn_admin.clicked.connect(lambda: self.open_admin_panel(key))
        self.grid.addWidget(btn_admin, row_idx, 3)
        
        # 5. Config button
        btn_config = QPushButton("Config")
        btn_config.setFixedHeight(22)
        btn_config.setFixedWidth(80)
        btn_config.clicked.connect(lambda: self.open_config_file(key))
        self.grid.addWidget(btn_config, row_idx, 4)
        
        # 6. Logs button
        btn_logs = QPushButton("Logs")
        btn_logs.setFixedHeight(22)
        btn_logs.setFixedWidth(80)
        btn_logs.clicked.connect(lambda: self.open_log_file(key))
        self.grid.addWidget(btn_logs, row_idx, 5)
        
        return {
            "status_lbl": status_lbl,
            "btn_action": btn_action,
            "btn_admin": btn_admin
        }
        
    def log_event(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.console_text.appendPlainText(f"[{timestamp}] {text}")
        
    def refresh_status(self):
        pass

    def on_status_updated(self, results):
        for key in self.service_keys:
            if key in self.active_action_workers:
                continue
            if self.batch_worker and self.batch_worker.isRunning():
                continue
                
            status = results.get(key, "Stopped")
            widgets = self.rows[key]
            
            status_lbl = widgets["status_lbl"]
            btn_action = widgets["btn_action"]
            btn_admin = widgets["btn_admin"]
            
            port = self.service_ports[key]
            
            if status == "Running":
                if "Running" not in status_lbl.text():
                    self.log_event(f"{self.service_names[key]} detected running on port {port}.")
                status_lbl.setText(f"Running (Port: {port})")
                status_lbl.setStyleSheet("color: #10b981; font-weight: bold; font-size: 11px;")
                btn_action.setText("Stop")
                btn_action.setObjectName("stop_btn")
                btn_action.style().unpolish(btn_action)
                btn_action.style().polish(btn_action)
                btn_admin.setEnabled(True)
            else:
                if "Stopped" not in status_lbl.text():
                    self.log_event(f"{self.service_names[key]} has stopped.")
                status_lbl.setText("Stopped")
                status_lbl.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px;")
                btn_action.setText("Start")
                btn_action.setObjectName("start_btn")
                btn_action.style().unpolish(btn_action)
                btn_action.style().polish(btn_action)
                btn_admin.setEnabled(False)
                
    def toggle_service(self, key):
        if key in self.active_action_workers:
            return
        if self.batch_worker and self.batch_worker.isRunning():
            return
            
        widgets = self.rows[key]
        status_lbl = widgets["status_lbl"]
        btn_action = widgets["btn_action"]
        
        is_running = "Running" in status_lbl.text()
        btn_action.setEnabled(False)
        
        if is_running:
            self.log_event(f"Attempting to stop {self.service_names[key]}...")
            action = "stop"
        else:
            self.log_event(f"Attempting to start {self.service_names[key]}...")
            action = "start"
            
        worker = ServiceActionWorker(key, action, self.main_win.env_root, self.main_win.log_dir)
        worker.completed.connect(self.on_action_finished)
        self.active_action_workers[key] = worker
        worker.start()
        
    def on_action_finished(self, key, action, success, msg):
        if key in self.active_action_workers:
            del self.active_action_workers[key]
            
        widgets = self.rows[key]
        widgets["btn_action"].setEnabled(True)
        
        if success:
            act_word = "started" if action == "start" else "stopped"
            self.log_event(f"{self.service_names[key]} {act_word} successfully.")
        else:
            self.log_event(f"Error: {msg}")
            QMessageBox.critical(self, "Service Action Error", f"Failed to {action} {self.service_names[key]}: {msg}")
            
    def open_admin_panel(self, key):
        from core.services import SERVICES
        nginx_port = SERVICES["nginx"]["port"]
        apache_port = SERVICES["apache"]["port"]
        urls = {
            "nginx": f"http://localhost:{nginx_port}",
            "apache": f"http://localhost:{apache_port}",
            "mysql": f"http://localhost:{nginx_port}/phpmyadmin"
        }
        url = urls.get(key)
        if url:
            self.log_event(f"Routing web request to {url}")
            import webbrowser
            webbrowser.open(url)
            
    def open_phpmyadmin(self):
        self.open_admin_panel("mysql")
            
    def open_config_file(self, key):
        path_map = {
            "php-cgi": os.path.join(self.main_win.env_root, "php", "active", "php.ini"),
            "nginx": os.path.join(self.main_win.env_root, "nginx", "conf", "nginx.conf"),
            "mysql": os.path.join(self.main_win.env_root, "mariadb", "my.ini"),
            "apache": os.path.join(self.main_win.env_root, "apache", "conf", "httpd.conf")
        }
        
        if key == "mysql" and not os.path.exists(path_map["mysql"]):
            path_map["mysql"] = os.path.join(self.main_win.env_root, "mysql", "my.ini")
            
        config_path = path_map.get(key)
        if not config_path or not os.path.exists(config_path):
            QMessageBox.warning(self, "Config File Missing", f"Configuration file not found. Ensure {key} is installed first.\n\nPath: {config_path}")
            return
            
        self.log_event(f"Opening config file: {os.path.basename(config_path)}")
        try:
            os.startfile(config_path)
        except Exception:
            subprocess.Popen(['notepad.exe', config_path])
            
    def open_log_file(self, key):
        log_path = os.path.join(self.main_win.log_dir, f"{key}.log")
        if not os.path.exists(log_path):
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "w") as f:
                    f.write("")
            except Exception:
                pass
                
        if os.path.exists(log_path):
            self.log_event(f"Opening log file: {os.path.basename(log_path)}")
            try:
                os.startfile(log_path)
            except Exception:
                subprocess.Popen(['notepad.exe', log_path])
        else:
            QMessageBox.warning(self, "Log File Missing", f"Log file not created yet: {log_path}")
            
    def start_all_services(self):
        if self.batch_worker and self.batch_worker.isRunning():
            return
        self.log_event("Command received: Start All Services. Launching background task...")
        self.set_batch_ui_enabled(False)
        
        self.batch_worker = BatchServiceWorker("start", self.main_win.env_root, self.main_win.log_dir)
        self.batch_worker.log_msg.connect(self.log_event)
        self.batch_worker.completed.connect(self.on_batch_finished)
        self.batch_worker.start()
        
    def stop_all_services(self):
        if self.batch_worker and self.batch_worker.isRunning():
            return
        self.log_event("Command received: Stop All Services. Launching background task...")
        self.set_batch_ui_enabled(False)
        
        self.batch_worker = BatchServiceWorker("stop", self.main_win.env_root, self.main_win.log_dir)
        self.batch_worker.log_msg.connect(self.log_event)
        self.batch_worker.completed.connect(self.on_batch_finished)
        self.batch_worker.start()
        
    def on_batch_finished(self, success, msg):
        self.set_batch_ui_enabled(True)
        if success:
            self.log_event("Batch service operation completed successfully.")
        else:
            self.log_event(f"Batch service operation failed: {msg}")
            QMessageBox.critical(self, "Batch Action Error", f"Batch service operation failed: {msg}")
            
    def set_batch_ui_enabled(self, enabled):
        self.btn_start_all.setEnabled(enabled)
        self.btn_stop_all.setEnabled(enabled)
        for key in self.service_keys:
            self.rows[key]["btn_action"].setEnabled(enabled)
        
    def open_environment_shell(self):
        self.log_event("Launching local environment PowerShell session...")
        try:
            cmd = ['powershell.exe', '-NoExit', '-Command', f"cd '{self.main_win.env_root}'"]
            subprocess.Popen(cmd)
        except Exception as e:
            QMessageBox.critical(self, "Shell Error", f"Failed to launch PowerShell session: {e}")

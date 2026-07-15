import os
import logging
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QComboBox, 
    QPlainTextEdit, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, QSize
import qtawesome as qta

logger = logging.getLogger(__name__)

class SettingsView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        
        self.init_ui()
        
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.poll_active_log)
        
    def start_timer(self):
        self.log_timer.start(2000)  # Check log every 2s instead of 1.5s
        self.refresh_logs()
        
    def stop_timer(self):
        self.log_timer.stop()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Header
        title_label = QLabel("Settings & Service Logs")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Directory configuration Group Box
        dir_group = QGroupBox("Environment Base Directory")
        dir_layout = QVBoxLayout(dir_group)
        dir_layout.setContentsMargins(10, 15, 10, 10)
        
        dir_row = QHBoxLayout()
        self.txt_env_root = QLineEdit(self.main_win.env_root)
        self.txt_env_root.setReadOnly(True)
        self.txt_env_root.setFixedHeight(24)
        dir_row.addWidget(self.txt_env_root, 4)
        
        btn_browse = QPushButton("Browse...")
        btn_browse.setFixedSize(90, 24)
        btn_browse.clicked.connect(self.browse_env_root)
        dir_row.addWidget(btn_browse, 1)
        dir_layout.addLayout(dir_row)
        layout.addWidget(dir_group)
        
        # Theme configuration Group Box
        theme_group = QGroupBox("Visual Preferences")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.setContentsMargins(10, 15, 10, 10)
        
        theme_lbl = QLabel("Application Theme:")
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Dark Mode", "Light Mode"])
        self.combo_theme.setFixedHeight(24)
        self.combo_theme.setMinimumWidth(150)
        
        if self.main_win.theme == "light":
            self.combo_theme.setCurrentIndex(1)
        else:
            self.combo_theme.setCurrentIndex(0)
            
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(theme_lbl)
        theme_layout.addWidget(self.combo_theme)
        theme_layout.addStretch()
        layout.addWidget(theme_group)
        
        # Ports Configuration Group Box
        port_group = QGroupBox("Service Port Settings")
        port_layout = QHBoxLayout(port_group)
        port_layout.setContentsMargins(10, 15, 10, 10)
        
        from PySide6.QtWidgets import QGridLayout
        port_grid = QGridLayout()
        port_grid.setSpacing(8)
        
        from PySide6.QtCore import QSettings
        settings = QSettings("LaravelDevSuite", "Settings")
        
        port_grid.addWidget(QLabel("Nginx:"), 0, 0)
        self.txt_port_nginx = QLineEdit(str(settings.value("port_nginx", 8080)))
        self.txt_port_nginx.setFixedWidth(50)
        self.txt_port_nginx.setFixedHeight(22)
        port_grid.addWidget(self.txt_port_nginx, 0, 1)
        
        port_grid.addWidget(QLabel("Apache:"), 0, 2)
        self.txt_port_apache = QLineEdit(str(settings.value("port_apache", 8081)))
        self.txt_port_apache.setFixedWidth(50)
        self.txt_port_apache.setFixedHeight(22)
        port_grid.addWidget(self.txt_port_apache, 0, 3)
        
        port_grid.addWidget(QLabel("MariaDB:"), 0, 4)
        self.txt_port_mysql = QLineEdit(str(settings.value("port_mysql", 3306)))
        self.txt_port_mysql.setFixedWidth(50)
        self.txt_port_mysql.setFixedHeight(22)
        port_grid.addWidget(self.txt_port_mysql, 0, 5)
        
        port_grid.addWidget(QLabel("PHP CGI:"), 0, 6)
        self.txt_port_php = QLineEdit(str(settings.value("port_php-cgi", 9000)))
        self.txt_port_php.setFixedWidth(50)
        self.txt_port_php.setFixedHeight(22)
        port_grid.addWidget(self.txt_port_php, 0, 7)
        
        btn_save_ports = QPushButton("Save Ports")
        btn_save_ports.setFixedHeight(24)
        btn_save_ports.clicked.connect(self.save_custom_ports)
        
        port_layout.addLayout(port_grid)
        port_layout.addWidget(btn_save_ports)
        port_layout.addStretch()
        layout.addWidget(port_group)
        
        # Configurations quick launcher Group Box
        conf_group = QGroupBox("Edit Configuration Files")
        conf_layout = QVBoxLayout(conf_group)
        conf_layout.setContentsMargins(10, 15, 10, 10)
        
        btn_grid_layout = QHBoxLayout()
        self.btn_edit_php = QPushButton(" php.ini")
        self.btn_edit_php.setIcon(qta.icon("fa5s.edit"))
        self.btn_edit_php.clicked.connect(lambda: self.open_config("php"))
        
        self.btn_edit_nginx = QPushButton(" nginx.conf")
        self.btn_edit_nginx.setIcon(qta.icon("fa5s.edit"))
        self.btn_edit_nginx.clicked.connect(lambda: self.open_config("nginx"))
        
        self.btn_edit_my = QPushButton(" my.ini")
        self.btn_edit_my.setIcon(qta.icon("fa5s.edit"))
        self.btn_edit_my.clicked.connect(lambda: self.open_config("mysql"))
        
        self.btn_edit_apache = QPushButton(" httpd.conf")
        self.btn_edit_apache.setIcon(qta.icon("fa5s.edit"))
        self.btn_edit_apache.clicked.connect(lambda: self.open_config("apache"))
        
        for btn in [self.btn_edit_php, self.btn_edit_nginx, self.btn_edit_my, self.btn_edit_apache]:
            btn.setFixedHeight(28)
            btn.setIconSize(QSize(11, 11))
            btn.setStyleSheet("font-size: 11px;")
            btn_grid_layout.addWidget(btn)
            
        conf_layout.addLayout(btn_grid_layout)
        layout.addWidget(conf_group)
        
        # Real-time Log Group Box
        log_group = QGroupBox("System Output Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 15, 10, 10)
        log_layout.setSpacing(10)
        
        log_header = QHBoxLayout()
        self.combo_log_file = QComboBox()
        self.combo_log_file.addItems([
            "Nginx Server (nginx.log)", 
            "Apache Server (apache.log)", 
            "MariaDB Database (mysql.log)", 
            "PHP-CGI Gateway (php-cgi.log)"
        ])
        self.combo_log_file.setMinimumWidth(220)
        self.combo_log_file.setFixedHeight(24)
        self.combo_log_file.currentIndexChanged.connect(self.refresh_logs)
        log_header.addWidget(self.combo_log_file)
        
        log_header.addStretch()
        
        btn_clear_log = QPushButton("Clear Log File")
        btn_clear_log.setFixedSize(110, 24)
        btn_clear_log.clicked.connect(self.clear_active_log)
        log_header.addWidget(btn_clear_log)
        
        log_layout.addLayout(log_header)
        
        # Log Text Box (Native styled)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        self.refresh_icons()
        
    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_edit_php.setIcon(qta.icon("fa5s.edit", color=color))
        self.btn_edit_nginx.setIcon(qta.icon("fa5s.edit", color=color))
        self.btn_edit_my.setIcon(qta.icon("fa5s.edit", color=color))
        self.btn_edit_apache.setIcon(qta.icon("fa5s.edit", color=color))
        
    def browse_env_root(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Environment Root Directory", 
            self.main_win.env_root
        )
        if dir_path:
            norm_path = os.path.abspath(dir_path)
            self.txt_env_root.setText(norm_path)
            self.main_win.update_env_root(norm_path)
            QMessageBox.information(self, "Directory Updated", f"Environment directory updated to: {norm_path}")
            
    def on_theme_changed(self, index):
        theme = "dark" if index == 0 else "light"
        self.main_win.apply_theme(theme)
            
    def get_active_log_path(self):
        log_map = {
            0: "nginx.log",
            1: "apache.log",
            2: "mysql.log",
            3: "php-cgi.log"
        }
        idx = self.combo_log_file.currentIndex()
        filename = log_map.get(idx, "nginx.log")
        return os.path.join(self.main_win.log_dir, filename)
        
    def refresh_logs(self):
        self.log_text.clear()
        self.poll_active_log()
        
    def poll_active_log(self):
        log_path = self.get_active_log_path()
        if not os.path.exists(log_path):
            self.log_text.setPlainText("Log file is empty or service has not been run yet.")
            return
            
        try:
            with open(log_path, "rb") as f:
                try:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    chunk_size = min(32768, size)
                    if chunk_size > 0:
                        f.seek(size - chunk_size)
                        chunk = f.read(chunk_size)
                        text = chunk.decode("utf-8", errors="ignore")
                        lines = text.splitlines()
                        if len(lines) > 1 and size > chunk_size:
                            lines = lines[1:]
                        recent_lines = lines[-150:]
                        content = "\n".join(recent_lines)
                    else:
                        content = ""
                except Exception:
                    f.seek(0)
                    content = f.read().decode("utf-8", errors="ignore")
                    
            if self.log_text.toPlainText() != content:
                scrollbar = self.log_text.verticalScrollBar()
                at_bottom = scrollbar.value() == scrollbar.maximum()
                
                self.log_text.setPlainText(content)
                
                if at_bottom:
                    scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logger.error(f"Error polling log file: {e}")
            
    def clear_active_log(self):
        log_path = self.get_active_log_path()
        if os.path.exists(log_path):
            try:
                with open(log_path, "w") as f:
                    f.write("")
                self.refresh_logs()
            except Exception as e:
                QMessageBox.warning(self, "File Lock Error", f"Could not clear log file (locked by running service): {e}")
                
    def open_config(self, key):
        path_map = {
            "php": os.path.join(self.main_win.env_root, "php", "active", "php.ini"),
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
            
        try:
            os.startfile(config_path)
        except Exception as e:
            try:
                subprocess.Popen(['notepad.exe', config_path])
            except Exception:
                QMessageBox.critical(self, "Editor Error", f"Failed to launch text editor: {e}")

    def save_custom_ports(self):
        from PySide6.QtCore import QSettings
        settings = QSettings("LaravelDevSuite", "Settings")
        
        try:
            settings.setValue("port_nginx", int(self.txt_port_nginx.text()))
            settings.setValue("port_apache", int(self.txt_port_apache.text()))
            settings.setValue("port_mysql", int(self.txt_port_mysql.text()))
            settings.setValue("port_php-cgi", int(self.txt_port_php.text()))
            
            # Reload values into core SERVICES dictionary
            from core.services import load_custom_ports
            load_custom_ports()
            
            QMessageBox.information(
                self, 
                "Success", 
                "Custom ports successfully saved! Restart any running services to apply changes."
            )
        except ValueError:
            QMessageBox.critical(
                self, 
                "Error", 
                "Invalid port number. Please enter numeric digits only."
            )

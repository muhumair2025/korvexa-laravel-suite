import os
import json
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QTableWidget, 
    QTableWidgetItem, QMessageBox, QHeaderView, QFrame,
    QDialog, QFormLayout, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal, QSize
import qtawesome as qta

logger = logging.getLogger(__name__)

class VHostRestartWorker(QThread):
    completed = Signal()
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        from core.services import get_service_status, start_service, stop_service
        if get_service_status("nginx", self.env_root) == "Running":
            stop_service("nginx", self.env_root)
            start_service("nginx", self.env_root, os.path.join(self.env_root, "logs"))
            
        if get_service_status("apache", self.env_root) == "Running":
            stop_service("apache", self.env_root)
            start_service("apache", self.env_root, os.path.join(self.env_root, "logs"))
        self.completed.emit()

class EditHostDialog(QDialog):
    def __init__(self, domain, path, ssl=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Virtual Host")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        form = QFormLayout()
        self.txt_domain = QLineEdit(domain)
        self.txt_domain.setFixedHeight(26)
        
        path_layout = QHBoxLayout()
        self.txt_path = QLineEdit(path)
        self.txt_path.setFixedHeight(26)
        btn_browse = QPushButton("Browse...")
        btn_browse.setFixedHeight(26)
        btn_browse.clicked.connect(self.browse)
        path_layout.addWidget(self.txt_path, 3)
        path_layout.addWidget(btn_browse, 1)
        
        self.chk_ssl = QCheckBox("Enable SSL (HTTPS)")
        self.chk_ssl.setChecked(ssl)
        
        form.addRow("Domain Name:", self.txt_domain)
        form.addRow("Document Root:", path_layout)
        form.addRow("SSL Status:", self.chk_ssl)
        layout.addLayout(form)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Public Directory", self.txt_path.text())
        if folder:
            self.txt_path.setText(folder.replace("\\", "/"))
            
    def get_values(self):
        return (
            self.txt_domain.text().strip().lower(),
            self.txt_path.text().strip().replace("\\", "/"),
            self.chk_ssl.isChecked()
        )

class VHostView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.settings = QSettings("LaravelDevSuite", "Settings")
        self.restart_worker = None
        self.load_hosts()
        
        self.init_ui()
        
    def load_hosts(self):
        # Format: [{"domain": "my-app.test", "path": "C:/path/to/public"}]
        raw_data = self.settings.value("virtual_hosts", "[]")
        try:
            self.hosts_list = json.loads(raw_data)
        except Exception:
            self.hosts_list = []
            
    def save_hosts(self):
        self.settings.setValue("virtual_hosts", json.dumps(self.hosts_list))
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header Info
        header_card = QFrame()
        header_card.setObjectName("tool_card")
        header_card.setFrameShape(QFrame.StyledPanel)
        header_layout = QVBoxLayout(header_card)
        
        title_label = QLabel("Local Virtual Domains (.test)")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;")
        desc_label = QLabel(
            "Map custom local domain names to project directories (e.g. mapping http://my-blog.test to your public/ folder). "
            "Note: adding domains requires Windows User Account Control (UAC) elevation to write to the system hosts file."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        layout.addWidget(header_card)
        
        # Add Host Entry Row
        add_card = QFrame()
        add_card.setObjectName("tool_card")
        add_card.setFrameShape(QFrame.StyledPanel)
        add_layout = QHBoxLayout(add_card)
        add_layout.setSpacing(10)
        
        self.txt_domain = QLineEdit()
        self.txt_domain.setPlaceholderText("e.g. my-app.test")
        self.txt_domain.setFixedHeight(26)
        
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Browse Laravel public/ directory...")
        self.txt_path.setFixedHeight(26)
        
        btn_browse = QPushButton("Browse...")
        btn_browse.setFixedHeight(26)
        btn_browse.clicked.connect(self.browse_path)
        
        self.chk_ssl = QCheckBox("SSL (HTTPS)")
        self.chk_ssl.setFixedHeight(26)
        self.chk_ssl.setStyleSheet("font-size: 11px; font-weight: bold;")
        
        btn_add = QPushButton(" Add Domain")
        btn_add.setIcon(qta.icon("fa5s.plus", color="#ffffff"))
        btn_add.setFixedHeight(26)
        btn_add.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.add_vhost)
        
        add_layout.addWidget(QLabel("Domain:"), 0)
        add_layout.addWidget(self.txt_domain, 2)
        add_layout.addWidget(QLabel("Folder:"), 0)
        add_layout.addWidget(self.txt_path, 3)
        add_layout.addWidget(btn_browse, 1)
        add_layout.addWidget(self.chk_ssl, 1)
        add_layout.addWidget(btn_add, 1)
        
        layout.addWidget(add_card)
        
        # Hosts Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Local Domain Link", "Document Root Path", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(2, 190)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.table)
        
        # Friendly Tip label
        self.tip_lbl = QLabel(
            "💡 <b>Tip:</b> Use the action buttons next to each virtual host to open it in your browser, copy its URL, edit its details, or delete it. "
            "If Nginx/Apache are configured on custom ports (like 8080/8081), the URL requires the port suffix (e.g. http://myapp.test:8080). "
            "To access domains directly without any port suffix (e.g. http://myapp.test), go to 'Logs & Settings' and change Nginx's port to 80!"
        )
        self.tip_lbl.setWordWrap(True)
        self.tip_lbl.setStyleSheet(
            "background-color: rgba(99, 102, 241, 0.15);"
            "color: #6366f1;"
            "border: 1px solid #6366f1;"
            "border-radius: 4px;"
            "padding: 8px;"
            "font-size: 11px;"
        )
        layout.addWidget(self.tip_lbl)
        
        self.refresh_table()

    def open_in_browser(self, link):
        import webbrowser
        webbrowser.open(link)
        
    def copy_domain(self, link):
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(link)
        if hasattr(self.main_win, 'statusBar') and self.main_win.statusBar():
            self.main_win.statusBar().showMessage(f"Copied {link} to clipboard!", 2000)

    def edit_vhost(self, idx):
        item = self.hosts_list[idx]
        old_domain = item["domain"]
        old_path = item["path"]
        old_ssl = item.get("ssl", False)
        
        dialog = EditHostDialog(old_domain, old_path, old_ssl, self)
        if dialog.exec():
            new_domain, new_path, new_ssl = dialog.get_values()
            
            if not new_domain or not new_path:
                QMessageBox.warning(self, "Validation Error", "Please fill in both the domain and folder path.")
                return
                
            if not new_domain.endswith(".test") and not new_domain.endswith(".local"):
                QMessageBox.warning(self, "Validation Error", "Local domains should end in .test or .local for safety.")
                return
                
            if new_domain != old_domain:
                for h in self.hosts_list:
                    if h["domain"] == new_domain:
                        QMessageBox.warning(self, "Validation Error", "This domain is already mapped.")
                        return
                        
                self.remove_hosts_entry(old_domain)
                self.remove_vhost_configs(old_domain)
                
                success, msg = self.add_hosts_entry(new_domain)
                if not success:
                    QMessageBox.critical(self, "Hosts File Error", f"Failed to map domain to hosts file:\n{msg}")
                    return
            
            self.write_vhost_configs(new_domain, new_path, new_ssl)
            
            self.hosts_list[idx] = {"domain": new_domain, "path": new_path, "ssl": new_ssl}
            self.save_hosts()
            self.refresh_table()
            
            self.trigger_servers_restart(
                f"Virtual host {new_domain} successfully updated!\n\n"
                "Web servers have been restarted to apply changes."
            )

    def refresh_table(self):
        from core.services import SERVICES
        nginx_port = SERVICES["nginx"]["port"]
        
        self.table.setRowCount(0)
        is_dark = getattr(self.main_win, 'theme', 'dark') == "dark"
        icon_color = "#f1f5f9" if is_dark else "#1e293b"
        
        if is_dark:
            btn_style = (
                "QPushButton {"
                "  background-color: #1e293b;"
                "  border: 1px solid #334155;"
                "  border-radius: 4px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #334155;"
                "}"
            )
            delete_style = (
                "QPushButton {"
                "  background-color: #1e293b;"
                "  border: 1px solid #ef4444;"
                "  border-radius: 4px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #ef4444;"
                "}"
            )
        else:
            btn_style = (
                "QPushButton {"
                "  background-color: #f1f5f9;"
                "  border: 1px solid #cbd5e1;"
                "  border-radius: 4px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #cbd5e1;"
                "}"
            )
            delete_style = (
                "QPushButton {"
                "  background-color: #f1f5f9;"
                "  border: 1px solid #ef4444;"
                "  border-radius: 4px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #ef4444;"
                "}"
            )
            
        for idx, item in enumerate(self.hosts_list):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            ssl_active = item.get("ssl", False)
            scheme = "https" if ssl_active else "http"
            if ssl_active:
                port = 443 if nginx_port == 80 else 8443
            else:
                port = nginx_port
                
            link = f"{scheme}://{item['domain']}"
            if port not in [80, 443]:
                link += f":{port}"
                
            domain_item = QTableWidgetItem(link)
            domain_item.setFlags(domain_item.flags() & ~Qt.ItemIsEditable)
            
            path_item = QTableWidgetItem(item['path'])
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            
            # Actions cell container
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignCenter)
            
            btn_open = QPushButton()
            btn_open.setToolTip("Open in Browser")
            btn_open.setIcon(qta.icon("fa5s.external-link-alt", color=icon_color))
            btn_open.setIconSize(QSize(10, 10))
            btn_open.setFixedSize(28, 22)
            btn_open.setStyleSheet(btn_style)
            btn_open.clicked.connect(lambda _, l=link: self.open_in_browser(l))
            
            btn_copy = QPushButton()
            btn_copy.setToolTip("Copy URL")
            btn_copy.setIcon(qta.icon("fa5s.copy", color=icon_color))
            btn_copy.setIconSize(QSize(10, 10))
            btn_copy.setFixedSize(28, 22)
            btn_copy.setStyleSheet(btn_style)
            btn_copy.clicked.connect(lambda _, l=link: self.copy_domain(l))
            
            btn_ssl = QPushButton()
            btn_ssl.setToolTip("Disable SSL" if ssl_active else "Enable SSL (HTTPS)")
            ssl_icon = "fa5s.lock" if ssl_active else "fa5s.lock-open"
            ssl_color = "#10b981" if ssl_active else icon_color
            btn_ssl.setIcon(qta.icon(ssl_icon, color=ssl_color))
            btn_ssl.setIconSize(QSize(10, 10))
            btn_ssl.setFixedSize(28, 22)
            btn_ssl.setStyleSheet(btn_style)
            btn_ssl.clicked.connect(lambda _, i=idx: self.toggle_ssl(i))
            
            btn_edit = QPushButton()
            btn_edit.setToolTip("Edit Domain / Path")
            btn_edit.setIcon(qta.icon("fa5s.edit", color=icon_color))
            btn_edit.setIconSize(QSize(10, 10))
            btn_edit.setFixedSize(28, 22)
            btn_edit.setStyleSheet(btn_style)
            btn_edit.clicked.connect(lambda _, i=idx: self.edit_vhost(i))
            
            btn_delete = QPushButton()
            btn_delete.setToolTip("Delete Host")
            btn_delete.setIcon(qta.icon("fa5s.trash", color="#ef4444"))
            btn_delete.setIconSize(QSize(10, 10))
            btn_delete.setFixedSize(28, 22)
            btn_delete.setStyleSheet(delete_style)
            btn_delete.clicked.connect(lambda _, i=idx: self.delete_vhost(i))
            
            action_layout.addWidget(btn_open)
            action_layout.addWidget(btn_copy)
            action_layout.addWidget(btn_ssl)
            action_layout.addWidget(btn_edit)
            action_layout.addWidget(btn_delete)
            
            self.table.setItem(row, 0, domain_item)
            self.table.setItem(row, 1, path_item)
            self.table.setCellWidget(row, 2, action_widget)
            
    def browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Public Directory")
        if folder:
            self.txt_path.setText(folder.replace("\\", "/"))
            
    def add_vhost(self):
        domain = self.txt_domain.text().strip().lower()
        path = self.txt_path.text().strip().replace("\\", "/")
        
        if not domain or not path:
            QMessageBox.warning(self, "Validation Error", "Please fill in both the domain and folder path.")
            return
            
        if not domain.endswith(".test") and not domain.endswith(".local"):
            QMessageBox.warning(self, "Validation Error", "Local domains should end in .test or .local for safety.")
            return
            
        # Check if duplicate
        for item in self.hosts_list:
            if item["domain"] == domain:
                QMessageBox.warning(self, "Validation Error", "This domain is already mapped.")
                return
                
        # 1. Add hosts entry via elevated prompt
        success, msg = self.add_hosts_entry(domain)
        if not success:
            QMessageBox.critical(self, "Hosts File Error", f"Failed to map domain to hosts file:\n{msg}")
            return
            
        # 2. Write Nginx and Apache virtual host files
        ssl_enabled = self.chk_ssl.isChecked()
        self.write_vhost_configs(domain, path, ssl_enabled)
        
        # 3. Save to settings list
        self.hosts_list.append({"domain": domain, "path": path, "ssl": ssl_enabled})
        self.save_hosts()
        
        self.txt_domain.clear()
        self.txt_path.clear()
        self.chk_ssl.setChecked(False)
        self.refresh_table()
        
        self.trigger_servers_restart(
            f"Virtual host {domain} successfully created!\n\n"
            "Web servers have been automatically restarted, and the new domain is now live."
        )
        
    def delete_vhost(self, idx):
        item = self.hosts_list[idx]
        domain = item["domain"]
        
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to remove the virtual host map for {domain}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return
            
        # 1. Remove hosts entry
        self.remove_hosts_entry(domain)
        
        # 2. Remove configuration files
        self.remove_vhost_configs(domain)
        
        # 3. Update settings
        self.hosts_list.pop(idx)
        self.save_hosts()
        self.refresh_table()
        
        self.trigger_servers_restart(
            f"Virtual host {domain} successfully removed.\n\n"
            "Web servers have been automatically restarted to apply configuration cleanup."
        )
        
    def trigger_servers_restart(self, success_msg):
        self.setEnabled(False) # Temporarily lock user input
        self.restart_worker = VHostRestartWorker(self.main_win.env_root)
        self.restart_worker.completed.connect(lambda: self.on_restart_finished(success_msg))
        self.restart_worker.start()
        
    def on_restart_finished(self, msg):
        self.setEnabled(True) # Re-enable UI controls
        QMessageBox.information(self, "Success", msg)
        
    def add_hosts_entry(self, domain):
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        entry = f"\n127.0.0.1 {domain}\n"
        
        # Check if already present
        try:
            if os.path.exists(hosts_path):
                with open(hosts_path, "r") as f:
                    content = f.read()
                    if f"127.0.0.1 {domain}" in content or f"127.0.0.1\t{domain}" in content:
                        return True, "Already exists"
        except Exception as e:
            return False, f"Could not read hosts file: {e}"
            
        # Try writing directly (in case app runs elevated)
        try:
            with open(hosts_path, "a") as f:
                f.write(entry)
            return True, "Direct write successful"
        except PermissionError:
            # Trigger runas UAC prompt with a temporary batch script
            import tempfile
            temp_dir = tempfile.gettempdir()
            bat_path = os.path.join(temp_dir, "add_host.bat")
            with open(bat_path, "w") as f:
                f.write(f'@echo off\nattrib -r {hosts_path}\necho 127.0.0.1 {domain}>> {hosts_path}\n')
            
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", bat_path, None, None, 0)
            if ret > 32:
                return True, "Written via UAC elevation"
            return False, "UAC elevation request denied by user."
        except Exception as e:
            return False, str(e)
            
    def remove_hosts_entry(self, domain):
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        if not os.path.exists(hosts_path):
            return
            
        try:
            with open(hosts_path, "r") as f:
                lines = f.readlines()
                
            new_lines = []
            for line in lines:
                if f"127.0.0.1 {domain}" in line or f"127.0.0.1\t{domain}" in line:
                    continue
                new_lines.append(line)
                
            # Try writing directly
            try:
                with open(hosts_path, "w") as f:
                    f.writelines(new_lines)
            except PermissionError:
                # Trigger runas UAC prompt to remove hosts entry
                import tempfile
                temp_dir = tempfile.gettempdir()
                bat_path = os.path.join(temp_dir, "remove_host.bat")
                
                # Write command to clean the file lines via temp file
                clean_temp = os.path.join(temp_dir, "hosts_clean")
                with open(clean_temp, "w") as f:
                    f.writelines(new_lines)
                    
                with open(bat_path, "w") as f:
                    f.write(f'@echo off\nattrib -r {hosts_path}\ncopy /y "{clean_temp}" "{hosts_path}"\ndel "{clean_temp}"\n')
                
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None, "runas", bat_path, None, None, 0)
        except Exception as e:
            logger.error(f"Error removing hosts file entry: {e}")
            
    def write_vhost_configs(self, domain, doc_root, ssl=False):
        from core.services import SERVICES
        nginx_port = SERVICES["nginx"]["port"]
        apache_port = SERVICES["apache"]["port"]
        
        nginx_ssl_port = 443 if nginx_port == 80 else 8443
        apache_ssl_port = 443 if apache_port == 80 else 8444
        
        # Paths
        nginx_vhost_dir = os.path.join(self.main_win.env_root, "nginx", "conf", "vhosts")
        apache_vhost_dir = os.path.join(self.main_win.env_root, "apache", "conf", "vhosts")
        
        os.makedirs(nginx_vhost_dir, exist_ok=True)
        os.makedirs(apache_vhost_dir, exist_ok=True)
        
        placeholder_nginx = os.path.join(nginx_vhost_dir, "_default.conf")
        if not os.path.exists(placeholder_nginx):
            with open(placeholder_nginx, "w") as f:
                f.write("# Default empty virtual hosts placeholder config\n")
                
        placeholder_apache = os.path.join(apache_vhost_dir, "_default.conf")
        if not os.path.exists(placeholder_apache):
            with open(placeholder_apache, "w") as f:
                f.write("# Default empty virtual hosts placeholder config\n")
        
        cert_directive_nginx = ""
        cert_directive_apache = ""
        
        if ssl:
            try:
                from core.ssl_manager import provision_certificate
                cert_path, key_path, method = provision_certificate(domain, self.main_win.env_root)
                
                cert_directive_nginx = f"""server {{
    listen       {nginx_ssl_port} ssl;
    server_name  {domain};
    root         "{doc_root}";
    index        index.php index.html index.htm;
    
    ssl_certificate      "{cert_path}";
    ssl_certificate_key  "{key_path}";
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;
    ssl_ciphers          HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers  on;
    
    access_log off;
    
    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
    
    location ~ \\.php$ {{
        fastcgi_pass   php-handler;
        fastcgi_index  index.php;
        fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;
        include        fastcgi_params;
    }}
}}
"""
                cert_directive_apache = f"""<IfModule ssl_module>
    <VirtualHost *:{apache_ssl_port}>
        ServerName {domain}
        DocumentRoot "{doc_root}"
        SSLEngine on
        SSLCertificateFile "{cert_path}"
        SSLCertificateKeyFile "{key_path}"
        <Directory "{doc_root}">
            AllowOverride All
            Require all granted
        </Directory>
    </VirtualHost>
</IfModule>
"""
            except Exception as e:
                logger.error(f"Could not provision SSL cert for {domain}: {e}")
                ssl = False
                
        # 1. Write Nginx Config
        nginx_conf = os.path.join(nginx_vhost_dir, f"{domain}.conf")
        nginx_content = f"""server {{
    listen       {nginx_port};
    server_name  {domain};
    root         "{doc_root}";
    index        index.php index.html index.htm;
    
    access_log off;
    
    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
    
    location ~ \\.php$ {{
        fastcgi_pass   php-handler;
        fastcgi_index  index.php;
        fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;
        include        fastcgi_params;
    }}
}}

{cert_directive_nginx}
"""
        with open(nginx_conf, "w") as f:
            f.write(nginx_content)
            
        # 2. Write Apache Config
        apache_conf = os.path.join(apache_vhost_dir, f"{domain}.conf")
        apache_content = f"""<VirtualHost *:{apache_port}>
    ServerName {domain}
    DocumentRoot "{doc_root}"
    <Directory "{doc_root}">
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>

{cert_directive_apache}
"""
        with open(apache_conf, "w") as f:
            f.write(apache_content)
            
    def remove_vhost_configs(self, domain):
        nginx_conf = os.path.join(self.main_win.env_root, "nginx", "conf", "vhosts", f"{domain}.conf")
        apache_conf = os.path.join(self.main_win.env_root, "apache", "conf", "vhosts", f"{domain}.conf")
        
        for path in [nginx_conf, apache_conf]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Failed to delete config file {path}: {e}")
                    
        # Optional: delete cert files
        cert_path = os.path.join(self.main_win.env_root, "certs", f"{domain}.pem")
        key_path = os.path.join(self.main_win.env_root, "certs", f"{domain}-key.pem")
        for path in [cert_path, key_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
                    
    def toggle_ssl(self, idx):
        item = self.hosts_list[idx]
        current_ssl = item.get("ssl", False)
        new_ssl = not current_ssl
        
        # Provision/update config
        self.write_vhost_configs(item["domain"], item["path"], new_ssl)
        
        # Save state
        item["ssl"] = new_ssl
        self.save_hosts()
        self.refresh_table()
        
        status_str = "enabled" if new_ssl else "disabled"
        self.trigger_servers_restart(
            f"SSL for domain {item['domain']} successfully {status_str}!\n\n"
            "Web servers have been restarted to apply changes."
        )

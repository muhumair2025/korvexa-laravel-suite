import os
import json
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QTableWidget, 
    QTableWidgetItem, QMessageBox, QHeaderView, QFrame
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal
import qtawesome as qta

logger = logging.getLogger(__name__)

class VHostRestartWorker(QThread):
    finished = Signal()
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        from core.services import get_service_status, start_service, stop_service
        # If Nginx is running, restart it
        if get_service_status("nginx", self.env_root) == "Running":
            stop_service("nginx", self.env_root)
            start_service("nginx", self.env_root, os.path.join(self.env_root, "logs"))
            
        # If Apache is running, restart it
        if get_service_status("apache", self.env_root) == "Running":
            stop_service("apache", self.env_root)
            start_service("apache", self.env_root, os.path.join(self.env_root, "logs"))
        self.finished.emit()

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
        
        btn_add = QPushButton(" Add Domain")
        btn_add.setIcon(qta.icon("fa5s.plus"))
        btn_add.setFixedHeight(26)
        btn_add.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.add_vhost)
        
        add_layout.addWidget(QLabel("Domain:"), 0)
        add_layout.addWidget(self.txt_domain, 2)
        add_layout.addWidget(QLabel("Folder:"), 0)
        add_layout.addWidget(self.txt_path, 3)
        add_layout.addWidget(btn_browse, 1)
        add_layout.addWidget(btn_add, 1)
        
        layout.addWidget(add_card)
        
        # Hosts Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Local Domain Link", "Document Root Path", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(2, 100)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        layout.addWidget(self.table)
        
        # Friendly Tip label
        self.tip_lbl = QLabel(
            "💡 <b>Tip:</b> Double-click a domain link in the table to open it in your browser. "
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
        
    def on_cell_double_clicked(self, row, column):
        if column == 0:
            item = self.table.item(row, column)
            if item:
                import webbrowser
                webbrowser.open(item.text())
                
    def refresh_table(self):
        from core.services import SERVICES
        nginx_port = SERVICES["nginx"]["port"]
        
        self.table.setRowCount(0)
        for idx, item in enumerate(self.hosts_list):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Append port to domain link if port is not standard 80
            link = f"http://{item['domain']}"
            if nginx_port != 80:
                link += f":{nginx_port}"
                
            domain_item = QTableWidgetItem(link)
            domain_item.setFlags(domain_item.flags() & ~Qt.ItemIsEditable)
            
            path_item = QTableWidgetItem(item['path'])
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            
            btn_delete = QPushButton("Delete")
            btn_delete.setStyleSheet("background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #ef4444; font-size: 10px;")
            btn_delete.setFixedHeight(20)
            btn_delete.clicked.connect(lambda _, r=idx: self.delete_vhost(r))
            
            self.table.setItem(row, 0, domain_item)
            self.table.setItem(row, 1, path_item)
            self.table.setCellWidget(row, 2, btn_delete)
            
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
        self.write_vhost_configs(domain, path)
        
        # 3. Save to settings list
        self.hosts_list.append({"domain": domain, "path": path})
        self.save_hosts()
        
        self.txt_domain.clear()
        self.txt_path.clear()
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
        self.restart_worker.finished.connect(lambda: self.on_restart_finished(success_msg))
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
            
    def write_vhost_configs(self, domain, doc_root):
        from core.services import SERVICES
        nginx_port = SERVICES["nginx"]["port"]
        apache_port = SERVICES["apache"]["port"]
        
        # Paths
        nginx_vhost_dir = os.path.join(self.main_win.env_root, "nginx", "conf", "vhosts")
        apache_vhost_dir = os.path.join(self.main_win.env_root, "apache", "conf", "vhosts")
        
        os.makedirs(nginx_vhost_dir, exist_ok=True)
        os.makedirs(apache_vhost_dir, exist_ok=True)
        
        # 1. Create a placeholder default configuration in Nginx/Apache to prevent empty wildcards errors
        placeholder_nginx = os.path.join(nginx_vhost_dir, "_default.conf")
        if not os.path.exists(placeholder_nginx):
            with open(placeholder_nginx, "w") as f:
                f.write("# Default empty virtual hosts placeholder config\n")
                
        placeholder_apache = os.path.join(apache_vhost_dir, "_default.conf")
        if not os.path.exists(placeholder_apache):
            with open(placeholder_apache, "w") as f:
                f.write("# Default empty virtual hosts placeholder config\n")
        
        # 2. Write Nginx Config
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
"""
        with open(nginx_conf, "w") as f:
            f.write(nginx_content)
            
        # 3. Write Apache Config
        apache_conf = os.path.join(apache_vhost_dir, f"{domain}.conf")
        apache_content = f"""<VirtualHost *:{apache_port}>
    ServerName {domain}
    DocumentRoot "{doc_root}"
    <Directory "{doc_root}">
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
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

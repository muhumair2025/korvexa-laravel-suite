import os
import json
import logging
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
    QMessageBox, QHeaderView, QFrame, QFormLayout, 
    QComboBox, QInputDialog, QGroupBox
)
from PySide6.QtCore import Qt, QSettings
import qtawesome as qta

logger = logging.getLogger(__name__)

class DatabaseView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.settings = QSettings("LaravelDevSuite", "Settings")
        self.load_saved_passwords()
        self.init_ui()
        
    def load_saved_passwords(self):
        raw = self.settings.value("db_passwords", "{}")
        try:
            self.saved_passwords = json.loads(raw)
        except Exception:
            self.saved_passwords = {}
            
    def save_passwords(self):
        self.settings.setValue("db_passwords", json.dumps(self.saved_passwords))
        
    def execute_sql(self, sql_query):
        from core.services import SERVICES
        port = SERVICES["mysql"]["port"]
        
        # Locate mysql.exe client
        mysql_exe = os.path.join(self.main_win.env_root, "mariadb", "bin", "mysql.exe")
        if not os.path.exists(mysql_exe):
            mysql_exe = os.path.join(self.main_win.env_root, "mysql", "bin", "mysql.exe")
            
        if not os.path.exists(mysql_exe):
            # Global search fallback
            import shutil
            mysql_exe = shutil.which("mysql") or "mysql.exe"
            
        cmd = [mysql_exe, "-u", "root", "-h", "127.0.0.1", "-P", str(port), "-e", sql_query]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            return res.returncode == 0, res.stdout, res.stderr
        except Exception as e:
            return False, "", str(e)
            
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Header Info Card
        header = QFrame()
        header.setObjectName("tool_card")
        header.setFrameShape(QFrame.StyledPanel)
        header_lay = QVBoxLayout(header)
        title = QLabel("Database & User Manager")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;")
        desc = QLabel("Manage MariaDB local databases, create users, assign privileges, and track password credentials.")
        desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        header_lay.addWidget(title)
        header_lay.addWidget(desc)
        layout.addWidget(header)
        
        body = QHBoxLayout()
        body.setSpacing(15)
        
        # Left Panel: Creation & Management Forms
        left_panel = QFrame()
        left_panel.setObjectName("tool_card")
        left_panel.setFrameShape(QFrame.StyledPanel)
        left_lay = QVBoxLayout(left_panel)
        left_lay.setSpacing(15)
        
        # 1. Create Database GroupBox
        db_group = QGroupBox("Create Database")
        db_group.setStyleSheet("QGroupBox { font-weight: bold; color: #ef4444; }")
        db_form = QFormLayout(db_group)
        db_form.setSpacing(8)
        
        self.txt_db_name = QLineEdit()
        self.txt_db_name.setPlaceholderText("e.g. my_project_db")
        self.txt_db_name.setFixedHeight(26)
        db_form.addRow("DB Name:", self.txt_db_name)
        
        btn_create_db = QPushButton(" Create Database")
        btn_create_db.setIcon(qta.icon("fa5s.database"))
        btn_create_db.setFixedHeight(26)
        btn_create_db.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; font-size: 11px;")
        btn_create_db.clicked.connect(self.create_database)
        db_form.addRow("", btn_create_db)
        
        left_lay.addWidget(db_group)
        
        # 2. Create User GroupBox
        user_group = QGroupBox("Create Database User")
        user_group.setStyleSheet("QGroupBox { font-weight: bold; color: #ef4444; }")
        user_form = QFormLayout(user_group)
        user_form.setSpacing(8)
        
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("e.g. db_user")
        self.txt_user.setFixedHeight(26)
        
        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("e.g. secret_pass")
        self.txt_pass.setFixedHeight(26)
        
        self.cmb_db_grant = QComboBox()
        self.cmb_db_grant.setFixedHeight(26)
        
        user_form.addRow("Username:", self.txt_user)
        user_form.addRow("Password:", self.txt_pass)
        user_form.addRow("Grant On:", self.cmb_db_grant)
        
        btn_create_user = QPushButton(" Create User Account")
        btn_create_user.setIcon(qta.icon("fa5s.user-plus"))
        btn_create_user.setFixedHeight(26)
        btn_create_user.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; font-size: 11px;")
        btn_create_user.clicked.connect(self.create_user)
        user_form.addRow("", btn_create_user)
        
        left_lay.addWidget(user_group)
        body.addWidget(left_panel, 1)
        
        # Right Panel: Tables
        right_panel = QFrame()
        right_panel.setObjectName("tool_card")
        right_panel.setFrameShape(QFrame.StyledPanel)
        right_lay = QVBoxLayout(right_panel)
        right_lay.setSpacing(12)
        
        table_style = """
            QTableWidget {
                border: 1px solid #1e293b;
                border-radius: 4px;
                gridline-color: #334155;
                background-color: transparent;
                selection-background-color: #ef4444;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #e2e8f0;
                border: none;
                padding: 4px 6px;
                font-weight: bold;
                font-size: 10px;
            }
        """
        
        # Databases Table Card
        db_table_lbl = QLabel("Active Databases")
        db_table_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")
        right_lay.addWidget(db_table_lbl)
        
        self.db_table = QTableWidget()
        self.db_table.setStyleSheet(table_style)
        self.db_table.setColumnCount(2)
        self.db_table.setHorizontalHeaderLabels(["Database Name", "Action"])
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.db_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.db_table.setColumnWidth(1, 80)
        self.db_table.verticalHeader().setVisible(False)
        self.db_table.setFixedHeight(150)
        right_lay.addWidget(self.db_table)
        
        # Users Table Card
        user_table_lbl = QLabel("Database Users & Credentials Tracker")
        user_table_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")
        right_lay.addWidget(user_table_lbl)
        
        self.user_table = QTableWidget()
        self.user_table.setStyleSheet(table_style)
        self.user_table.setColumnCount(3)
        self.user_table.setHorizontalHeaderLabels(["User @ Host", "Saved Password", "Actions"])
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.user_table.setColumnWidth(2, 160)
        self.user_table.verticalHeader().setVisible(False)
        right_lay.addWidget(self.user_table)
        
        body.addWidget(right_panel, 1.8)
        layout.addLayout(body)
        
        self.refresh_all()
        
    def refresh_all(self):
        self.refresh_databases()
        self.refresh_users()
        
    def refresh_databases(self):
        self.db_table.setRowCount(0)
        self.cmb_db_grant.clear()
        self.cmb_db_grant.addItem("All Databases (*.*)")
        
        success, stdout, stderr = self.execute_sql("SHOW DATABASES;")
        if not success:
            return
            
        excluded = ["information_schema", "performance_schema", "sys", "mysql"]
        databases = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.lower() == "database" or line.lower() in excluded:
                continue
            databases.append(line)
            
        for db in databases:
            row = self.db_table.rowCount()
            self.db_table.insertRow(row)
            
            db_item = QTableWidgetItem(db)
            db_item.setFlags(db_item.flags() & ~Qt.ItemIsEditable)
            
            btn_drop = QPushButton("Drop")
            btn_drop.setStyleSheet("background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #ef4444; font-size: 10px;")
            btn_drop.setFixedHeight(20)
            btn_drop.clicked.connect(lambda _, d=db: self.drop_database(d))
            
            self.db_table.setItem(row, 0, db_item)
            self.db_table.setCellWidget(row, 1, btn_drop)
            
            # Populate combobox
            self.cmb_db_grant.addItem(db)
            
    def refresh_users(self):
        self.user_table.setRowCount(0)
        success, stdout, stderr = self.execute_sql("SELECT User, Host FROM mysql.user;")
        if not success:
            return
            
        excluded = ["mariadb.sys", "mysql.sys", "mysql.session", "mysql.infoschema"]
        for line in stdout.splitlines():
            parts = line.strip().split()
            if not parts or len(parts) < 2 or parts[0].lower() == "user":
                continue
                
            username = parts[0]
            host = parts[1]
            if username.lower() in excluded:
                continue
                
            row = self.user_table.rowCount()
            self.user_table.insertRow(row)
            
            user_host = f"'{username}'@'{host}'"
            user_item = QTableWidgetItem(user_host)
            user_item.setFlags(user_item.flags() & ~Qt.ItemIsEditable)
            
            # Check for saved passwords
            saved_pass = self.saved_passwords.get(username, "Unknown (Not created here)")
            pass_item = QTableWidgetItem(saved_pass)
            pass_item.setFlags(pass_item.flags() & ~Qt.ItemIsEditable)
            
            # Action buttons cell container
            actions = QWidget()
            act_lay = QHBoxLayout(actions)
            act_lay.setContentsMargins(2, 2, 2, 2)
            act_lay.setSpacing(6)
            
            btn_pw = QPushButton("Pass")
            btn_pw.setStyleSheet("font-size: 10px; height: 18px;")
            btn_pw.clicked.connect(lambda _, u=username, h=host: self.change_password(u, h))
            
            btn_del = QPushButton("Delete")
            btn_del.setStyleSheet("background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #ef4444; font-size: 10px; height: 18px;")
            btn_del.clicked.connect(lambda _, u=username, h=host: self.drop_user(u, h))
            
            act_lay.addWidget(btn_pw)
            act_lay.addWidget(btn_del)
            
            self.user_table.setItem(row, 0, user_item)
            self.user_table.setItem(row, 1, pass_item)
            self.user_table.setCellWidget(row, 2, actions)
            
    def create_database(self):
        db_name = self.txt_db_name.text().strip()
        if not db_name:
            QMessageBox.warning(self, "Input Error", "Please enter a database name.")
            return
            
        success, stdout, stderr = self.execute_sql(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        if success:
            QMessageBox.information(self, "Database Created", f"Database '{db_name}' created successfully.")
            self.txt_db_name.clear()
            self.refresh_databases()
        else:
            QMessageBox.critical(self, "SQL Error", f"Failed to create database:\n{stderr}")
            
    def create_user(self):
        user = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()
        grant_target = self.cmb_db_grant.currentText()
        
        if not user or not password:
            QMessageBox.warning(self, "Input Error", "Please provide both database username and password.")
            return
            
        # Determine grant statement target
        if "(*.*)" in grant_target:
            sql_target = "*.*"
        else:
            sql_target = f"`{grant_target}`.*"
            
        # SQL Commands
        sql = (
            f"CREATE USER '{user}'@'localhost' IDENTIFIED BY '{password}';"
            f"GRANT ALL PRIVILEGES ON {sql_target} TO '{user}'@'localhost';"
            f"FLUSH PRIVILEGES;"
        )
        
        success, stdout, stderr = self.execute_sql(sql)
        if success:
            # Save password locally
            self.saved_passwords[user] = password
            self.save_passwords()
            
            QMessageBox.information(self, "User Created", f"User '{user}'@'localhost' created and granted rights on {grant_target} successfully.")
            self.txt_user.clear()
            self.txt_pass.clear()
            self.refresh_users()
        else:
            QMessageBox.critical(self, "SQL Error", f"Failed to create user:\n{stderr}")
            
    def drop_database(self, db_name):
        confirm = QMessageBox.question(
            self,
            "Drop Database",
            f"Warning: Are you sure you want to drop database '{db_name}'? This will delete all tables and data forever!",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return
            
        success, stdout, stderr = self.execute_sql(f"DROP DATABASE `{db_name}`;")
        if success:
            QMessageBox.information(self, "Database Dropped", f"Database '{db_name}' dropped successfully.")
            self.refresh_databases()
        else:
            QMessageBox.critical(self, "SQL Error", f"Failed to drop database:\n{stderr}")
            
    def drop_user(self, username, host):
        confirm = QMessageBox.question(
            self,
            "Delete User",
            f"Are you sure you want to delete database user '{username}'@'{host}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return
            
        success, stdout, stderr = self.execute_sql(f"DROP USER '{username}'@'{host}';")
        if success:
            # Clean up local saved password if any
            if username in self.saved_passwords:
                del self.saved_passwords[username]
                self.save_passwords()
                
            QMessageBox.information(self, "User Deleted", f"Database user '{username}'@'{host}' deleted successfully.")
            self.refresh_users()
        else:
            QMessageBox.critical(self, "SQL Error", f"Failed to delete user:\n{stderr}")
            
    def change_password(self, username, host):
        new_pass, ok = QInputDialog.getText(self, "Change Password", f"Enter new password for '{username}'@'{host}':", QLineEdit.Password)
        if not ok or not new_pass.strip():
            return
            
        new_pass = new_pass.strip()
        sql = f"ALTER USER '{username}'@'{host}' IDENTIFIED BY '{new_pass}'; FLUSH PRIVILEGES;"
        success, stdout, stderr = self.execute_sql(sql)
        if success:
            # Update local saved password
            self.saved_passwords[username] = new_pass
            self.save_passwords()
            
            QMessageBox.information(self, "Password Changed", f"Password for '{username}'@'{host}' updated successfully.")
            self.refresh_users()
        else:
            QMessageBox.critical(self, "SQL Error", f"Failed to change password:\n{stderr}")

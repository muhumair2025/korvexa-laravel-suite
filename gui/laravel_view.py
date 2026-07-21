import os
import logging
import shlex
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QTextEdit, 
    QProgressBar, QFrame, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QMenu, QTabWidget, QGridLayout
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta

logger = logging.getLogger(__name__)

class LaravelCreateWorker(QThread):
    progress_msg = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, project_name, parent_dir, env_root, starter_kit, db_name, db_user, db_pass):
        super().__init__()
        self.project_name = project_name
        self.parent_dir = parent_dir
        self.env_root = env_root
        self.starter_kit = starter_kit
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self.current_process = None

    def send_input(self, text):
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.stdin.write(text + "\n")
                self.current_process.stdin.flush()
                return True
            except Exception as e:
                logger.error(f"Failed to write to stdin: {e}")
        return False

    def run(self):
        import subprocess
        import sys
        
        php_active = os.path.join(self.env_root, "php", "active")
        composer_dir = os.path.join(self.env_root, "composer")
        node_dir = os.path.join(self.env_root, "nodejs")
        
        env = os.environ.copy()
        env_paths = [php_active, composer_dir, node_dir]
        env["PATH"] = ";".join(env_paths) + ";" + env.get("PATH", "")
        
        os.makedirs(self.parent_dir, exist_ok=True)
        
        def run_cmd(args, cwd):
            self.progress_msg.emit(f"> Running: {' '.join(args)}")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            p = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.current_process = p
            
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                self.progress_msg.emit(line.strip())
            p.wait()
            self.current_process = None
            return p.returncode

        def execute_sql(sql_query):
            from core.services import SERVICES
            port = SERVICES["mysql"]["port"]
            
            mysql_exe = os.path.join(self.env_root, "mariadb", "bin", "mysql.exe")
            if not os.path.exists(mysql_exe):
                mysql_exe = os.path.join(self.env_root, "mysql", "bin", "mysql.exe")
            if not os.path.exists(mysql_exe):
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
                return res.returncode == 0, res.stderr
            except Exception as e:
                return False, str(e)

        # 1. Create Laravel Project
        self.progress_msg.emit("Step 1/5: Scaffolding Laravel project via Composer...")
        cmd_laravel = ["cmd.exe", "/c", "composer", "create-project", "laravel/laravel", self.project_name, "--no-interaction"]
        code = run_cmd(cmd_laravel, self.parent_dir)
        if code != 0:
            self.finished.emit(False, "Composer create-project failed.")
            return

        project_path = os.path.join(self.parent_dir, self.project_name)
        
        # 2. Install Starter Kit
        if self.starter_kit != "none":
            self.progress_msg.emit("Step 2/5: Installing Laravel Breeze starter package...")
            cmd_req = ["cmd.exe", "/c", "composer", "require", "laravel/breeze", "--dev", "--no-interaction"]
            code = run_cmd(cmd_req, project_path)
            if code != 0:
                self.finished.emit(False, "Failed to require laravel/breeze package.")
                return

            self.progress_msg.emit("Running artisan breeze:install...")
            kit_type = "blade"
            if self.starter_kit == "breeze_vue":
                kit_type = "vue"
            elif self.starter_kit == "breeze_react":
                kit_type = "react"
                
            cmd_inst = ["cmd.exe", "/c", "php", "artisan", "breeze:install", kit_type, "--dark", "--no-interaction"]
            code = run_cmd(cmd_inst, project_path)
            if code != 0:
                self.finished.emit(False, "Failed to install Breeze starter layout.")
                return
        else:
            self.progress_msg.emit("Step 2/5: Skipping starter kit setup.")

        # Auto-Create Database and User if configured
        if self.db_name:
            self.progress_msg.emit("\nAuto-creating Database and User in MariaDB...")
            # 1. Database Creation
            sql_create_db = f"CREATE DATABASE IF NOT EXISTS `{self.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            success, err = execute_sql(sql_create_db)
            if success:
                self.progress_msg.emit(f"MariaDB database '{self.db_name}' auto-created successfully (or already exists).")
            else:
                self.progress_msg.emit(f"Warning: Failed to auto-create database '{self.db_name}': {err}")
                
            # 2. User Creation & Privileges
            if self.db_user and self.db_user != "root":
                sql_create_user = (
                    f"CREATE USER IF NOT EXISTS '{self.db_user}'@'localhost' IDENTIFIED BY '{self.db_pass}';"
                    f"ALTER USER '{self.db_user}'@'localhost' IDENTIFIED BY '{self.db_pass}';"
                    f"GRANT ALL PRIVILEGES ON `{self.db_name}`.* TO '{self.db_user}'@'localhost';"
                    f"FLUSH PRIVILEGES;"
                )
                success, err = execute_sql(sql_create_user)
                if success:
                    self.progress_msg.emit(f"MariaDB Database User '{self.db_user}'@'localhost' auto-created/updated successfully.")
                    # Register password in database manager credentials store
                    try:
                        from PySide6.QtCore import QSettings
                        import json
                        settings = QSettings("LaravelDevSuite", "Settings")
                        raw = settings.value("db_passwords", "{}")
                        passwords = json.loads(raw)
                        passwords[self.db_user] = self.db_pass
                        settings.setValue("db_passwords", json.dumps(passwords))
                    except Exception as e:
                        logger.warning(f"Failed to save auto-created database password: {e}")
                else:
                    self.progress_msg.emit(f"Warning: Failed to create database user '{self.db_user}': {err}")

        # 3. Configure Database connection in .env
        self.progress_msg.emit("Step 3/5: Setting database configurations in .env...")
        env_file = os.path.join(project_path, ".env")
        if os.path.exists(env_file):
            try:
                from core.services import SERVICES
                mysql_port = SERVICES["mysql"]["port"]
                
                with open(env_file, "r") as f:
                    lines = f.readlines()
                
                import re
                keys_to_set = {
                    "DB_CONNECTION": "mysql",
                    "DB_HOST": "127.0.0.1",
                    "DB_PORT": str(mysql_port),
                    "DB_DATABASE": self.db_name,
                    "DB_USERNAME": self.db_user,
                    "DB_PASSWORD": self.db_pass,
                    "SESSION_DRIVER": "file"
                }
                
                new_lines = []
                processed_keys = set()
                
                for line in lines:
                    stripped = line.strip()
                    matched = False
                    for key in keys_to_set:
                        # Match uncommented or commented database key patterns (e.g. '# DB_PORT=3306')
                        if re.match(rf'^#?\s*{key}\s*=', stripped):
                            new_lines.append(f"{key}={keys_to_set[key]}\n")
                            processed_keys.add(key)
                            matched = True
                            break
                    if not matched:
                        new_lines.append(line)
                        
                # Append missing keys at the bottom of the file
                for key, val in keys_to_set.items():
                    if key not in processed_keys:
                        new_lines.append(f"{key}={val}\n")
                
                with open(env_file, "w") as f:
                    f.writelines(new_lines)
                self.progress_msg.emit(f"Updated .env: db='{self.db_name}' port={mysql_port} session_driver='database' connection='mysql'.")
            except Exception as e:
                self.progress_msg.emit(f"Failed to auto-update .env settings: {e}")
        else:
            self.progress_msg.emit(".env file not found, skipping database configurations.")

        # 4. Install NPM Dependencies
        self.progress_msg.emit("Step 4/5: Running 'npm install'...")
        cmd_npm_i = ["cmd.exe", "/c", "npm", "install"]
        code = run_cmd(cmd_npm_i, project_path)

        # 5. Build Assets (NPM Run Build)
        self.progress_msg.emit("Step 5/5: Compiling assets via Vite (npm run build)...")
        cmd_npm_b = ["cmd.exe", "/c", "npm", "run", "build"]
        code = run_cmd(cmd_npm_b, project_path)

        self.completed.emit(True, f"Laravel project '{self.project_name}' created successfully!")


class ArtisanCommandWorker(QThread):
    progress_msg = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, project_path, env_root, command_args):
        super().__init__()
        self.project_path = project_path
        self.env_root = env_root
        self.command_args = command_args
        self.process = None

    def send_input(self, text):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
                return True
            except Exception as e:
                logger.error(f"Failed to write to stdin: {e}")
        return False

    def run(self):
        import subprocess
        php_active = os.path.join(self.env_root, "php", "active")
        
        env = os.environ.copy()
        env["PATH"] = php_active + ";" + env.get("PATH", "")
        
        cmd = ["cmd.exe", "/c", "php", "artisan"] + self.command_args
        self.progress_msg.emit(f"> Running: php artisan {' '.join(self.command_args)}")
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        p = subprocess.Popen(
            cmd,
            cwd=self.project_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.process = p
        
        while True:
            line = p.stdout.readline()
            if not line:
                break
            self.progress_msg.emit(line.strip())
        p.wait()
        self.process = None
        
        if p.returncode == 0:
            self.completed.emit(True, "Artisan command completed successfully.")
        else:
            self.completed.emit(False, f"Artisan command failed with code {p.returncode}.")


class ViteBuildWorker(QThread):
    progress_msg = Signal(str)
    completed = Signal(bool, str)
    
    def __init__(self, project_path, env_root):
        super().__init__()
        self.project_path = project_path
        self.env_root = env_root
        self.process = None
        
    def run(self):
        import subprocess
        import os
        php_active = os.path.join(self.env_root, "php", "active")
        composer_dir = os.path.join(self.env_root, "composer")
        node_dir = os.path.join(self.env_root, "nodejs")
        
        env = os.environ.copy()
        env["PATH"] = ";".join([php_active, composer_dir, node_dir]) + ";" + env.get("PATH", "")
        
        cmd = ["cmd.exe", "/c", "npm", "run", "build"]
        self.progress_msg.emit(f"> Running: npm run build")
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        p = subprocess.Popen(
            cmd,
            cwd=self.project_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.process = p
        
        while True:
            line = p.stdout.readline()
            if not line:
                break
            self.progress_msg.emit(line.strip())
        p.wait()
        self.process = None
        
        if p.returncode == 0:
            self.completed.emit(True, "NPM asset build completed successfully.")
        else:
            self.completed.emit(False, f"NPM asset build failed with code {p.returncode}.")


class LiveProcessWorker(QThread):
    line_read = Signal(str)
    finished = Signal(int)

    def __init__(self, cmd, cwd, env, log_path=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.log_path = log_path
        self.process = None

    def run(self):
        import subprocess
        import time
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        log_file = None
        if self.log_path:
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                log_file = open(self.log_path, "w", encoding="utf-8")
                log_file.write(f"--- Command execution started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"> Command: {' '.join(self.cmd)}\n\n")
                log_file.flush()
            except Exception as e:
                logger.error(f"Failed to open log file {self.log_path}: {e}")

        try:
            self.process = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self.env,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                stripped_line = line.strip()
                self.line_read.emit(stripped_line)
                if log_file:
                    log_file.write(line)
                    log_file.flush()
            
            self.process.wait()
            ret = self.process.returncode
            self.finished.emit(ret)
        except Exception as e:
            self.line_read.emit(f"Error executing command: {e}")
            if log_file:
                log_file.write(f"Error: {e}\n")
                log_file.flush()
            self.finished.emit(-1)
        finally:
            if log_file:
                try:
                    log_file.close()
                except Exception:
                    pass

    def terminate_process(self):
        if self.process and self.process.poll() is None:
            try:
                import subprocess
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.process.wait()
            except Exception:
                pass


class LaravelView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.create_worker = None
        self.artisan_worker = None
        self.build_worker = None
        self.dev_workers = {}
        self.queue_workers = {}
        self.scheduler_workers = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header Info Card
        header = QFrame()
        header.setObjectName("tool_card")
        header.setFrameShape(QFrame.StyledPanel)
        header_lay = QVBoxLayout(header)
        title = QLabel("Laravel Manager Suite")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;")
        desc = QLabel("Scaffold new Laravel projects, auto-link databases, and run Artisan console tasks with interactive terminal inputs.")
        desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        header_lay.addWidget(title)
        header_lay.addWidget(desc)
        layout.addWidget(header)

        # Content Split Layout
        body = QHBoxLayout()
        body.setSpacing(15)

        # Left Column: Tabbed Control Center
        left_panel = QFrame()
        left_panel.setObjectName("tool_card")
        left_panel.setFrameShape(QFrame.StyledPanel)
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(5, 5, 5, 5)

        self.control_tabs = QTabWidget()
        self.control_tabs.setStyleSheet("QTabBar::tab { font-size: 10px; font-weight: bold; padding: 6px 12px; }")
        left_lay.addWidget(self.control_tabs)

        # Tab 1: App Scaffolder
        scaffolder_widget = QWidget()
        scaffolder_lay = QVBoxLayout(scaffolder_widget)
        scaffolder_lay.setSpacing(10)
        
        create_title = QLabel("Create New Laravel App")
        create_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")
        scaffolder_lay.addWidget(create_title)

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. my-laravel-app")
        self.txt_name.setFixedHeight(26)

        loc_lay = QHBoxLayout()
        self.txt_location = QLineEdit()
        default_www = os.path.join(self.main_win.env_root, "www").replace("\\", "/")
        self.txt_location.setText(default_www)
        self.txt_location.setFixedHeight(26)
        btn_loc = QPushButton("...")
        btn_loc.setFixedWidth(30)
        btn_loc.setFixedHeight(26)
        btn_loc.clicked.connect(self.browse_location)
        loc_lay.addWidget(self.txt_location)
        loc_lay.addWidget(btn_loc)

        self.cmb_kit = QComboBox()
        self.cmb_kit.addItems([
            "None (Default Laravel)",
            "Laravel Breeze (Blade Template)",
            "Laravel Breeze (Vue.js / Vite)",
            "Laravel Breeze (React / Vite)"
        ])
        self.cmb_kit.setFixedHeight(26)

        self.db_group = QGroupBox("Database Autolink Settings")
        db_form = QFormLayout(self.db_group)
        db_form.setSpacing(6)
        
        self.txt_db_name = QLineEdit()
        self.txt_db_name.setPlaceholderText("e.g. my_laravel_db")
        self.txt_db_name.setFixedHeight(26)
        
        self.txt_db_user = QLineEdit("root")
        self.txt_db_user.setFixedHeight(26)
        
        self.txt_db_pass = QLineEdit()
        self.txt_db_pass.setEchoMode(QLineEdit.Password)
        self.txt_db_pass.setFixedHeight(26)
        
        db_form.addRow("DB Name:", self.txt_db_name)
        db_form.addRow("Username:", self.txt_db_user)
        db_form.addRow("Password:", self.txt_db_pass)

        form.addRow("Project Name:", self.txt_name)
        form.addRow("Install Folder:", loc_lay)
        form.addRow("Starter Kit:", self.cmb_kit)
        
        scaffolder_lay.addLayout(form)
        scaffolder_lay.addWidget(self.db_group)

        self.btn_create = QPushButton(" Scaffold Laravel App")
        self.btn_create.setIcon(qta.icon("fa5b.laravel", color="#ffffff"))
        self.btn_create.setFixedHeight(30)
        self.btn_create.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; font-size: 11px;")
        self.btn_create.clicked.connect(self.create_laravel_app)
        scaffolder_lay.addWidget(self.btn_create)
        scaffolder_lay.addStretch()
        
        self.control_tabs.addTab(scaffolder_widget, "App Scaffolder")

        # Tab 2: Artisan Console
        artisan_runner_widget = QWidget()
        artisan_runner_lay = QVBoxLayout(artisan_runner_widget)
        artisan_runner_lay.setSpacing(10)

        artisan_title = QLabel("Artisan Command Runner")
        artisan_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")
        artisan_runner_lay.addWidget(artisan_title)

        art_form = QFormLayout()
        art_form.setSpacing(8)
        
        project_selection_layout = QHBoxLayout()
        self.cmb_project = QComboBox()
        self.cmb_project.setFixedHeight(26)
        self.cmb_project.setPlaceholderText("Select Laravel project...")
        
        self.btn_import_project = QPushButton()
        self.btn_import_project.setIcon(qta.icon("fa5s.folder-plus", color="#ef4444"))
        self.btn_import_project.setFixedSize(26, 26)
        self.btn_import_project.setToolTip("Import Custom Laravel Project Folder")
        self.btn_import_project.clicked.connect(self.import_project)
        
        project_selection_layout.addWidget(self.cmb_project, 4)
        project_selection_layout.addWidget(self.btn_import_project, 1)
        
        art_form.addRow("Select Project:", project_selection_layout)
        artisan_runner_lay.addLayout(art_form)

        # Quick Actions Group
        quick_group = QGroupBox("Quick Commands")
        quick_group_lay = QVBoxLayout(quick_group)
        
        quick_grid = QGridLayout()
        quick_grid.setSpacing(6)
        btn_migrate = QPushButton("Migrate")
        btn_migrate.clicked.connect(lambda: self.run_artisan(["migrate"]))
        btn_seed = QPushButton("Seed")
        btn_seed.clicked.connect(lambda: self.run_artisan(["db:seed"]))
        btn_key = QPushButton("Key Gen")
        btn_key.clicked.connect(lambda: self.run_artisan(["key:generate"]))
        btn_clear = QPushButton("Clear Cache")
        btn_clear.clicked.connect(lambda: self.run_artisan(["optimize:clear"]))
        
        for btn in [btn_migrate, btn_seed, btn_key, btn_clear]:
            btn.setFixedHeight(26)
            btn.setStyleSheet("font-size: 10px;")
            
        quick_grid.addWidget(btn_migrate, 0, 0)
        quick_grid.addWidget(btn_seed, 0, 1)
        quick_grid.addWidget(btn_key, 1, 0)
        quick_grid.addWidget(btn_clear, 1, 1)
        quick_group_lay.addLayout(quick_grid)
        artisan_runner_lay.addWidget(quick_group)

        # Custom commands group
        custom_group = QGroupBox("Custom Artisan Command")
        custom_group_lay = QVBoxLayout(custom_group)
        custom_lay = QHBoxLayout()
        self.txt_custom_art = QLineEdit()
        self.txt_custom_art.setPlaceholderText("custom-command --option")
        self.txt_custom_art.setFixedHeight(26)
        btn_custom_run = QPushButton("Run")
        btn_custom_run.setFixedWidth(50)
        btn_custom_run.setFixedHeight(26)
        btn_custom_run.clicked.connect(self.run_custom_artisan)
        custom_lay.addWidget(self.txt_custom_art)
        custom_lay.addWidget(btn_custom_run)
        custom_group_lay.addLayout(custom_lay)
        artisan_runner_lay.addWidget(custom_group)
        artisan_runner_lay.addStretch()

        self.control_tabs.addTab(artisan_runner_widget, "Artisan Console")

        # Tab 3: Worker Controls
        workers_widget = QWidget()
        workers_lay = QVBoxLayout(workers_widget)
        workers_lay.setSpacing(12)

        workers_title = QLabel("Background Service Runners")
        workers_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444;")
        workers_lay.addWidget(workers_title)

        # Vite Dev Server Group
        vite_group = QGroupBox("Vite Assets Dev / Build")
        vite_group_lay = QVBoxLayout(vite_group)
        vite_group_lay.setSpacing(8)
        
        self.btn_vite_dev = QPushButton("Start Vite Server (npm run dev)")
        self.btn_vite_dev.setFixedHeight(28)
        self.btn_vite_dev.setStyleSheet("font-size: 10px; font-weight: bold;")
        self.btn_vite_dev.clicked.connect(self.toggle_vite_dev)
        
        self.btn_vite_build = QPushButton("Compile Production Assets (npm run build)")
        self.btn_vite_build.setFixedHeight(28)
        self.btn_vite_build.setStyleSheet("font-size: 10px;")
        self.btn_vite_build.clicked.connect(self.run_vite_build)
        
        vite_group_lay.addWidget(self.btn_vite_dev)
        vite_group_lay.addWidget(self.btn_vite_build)
        workers_lay.addWidget(vite_group)

        # Background Queue & Sched Group
        background_group = QGroupBox("Laravel Queues & Schedulers")
        background_group_lay = QVBoxLayout(background_group)
        background_group_lay.setSpacing(8)
        
        self.btn_queue_worker = QPushButton("Start Queue Worker (artisan queue:work)")
        self.btn_queue_worker.setFixedHeight(28)
        self.btn_queue_worker.setStyleSheet("font-size: 10px; font-weight: bold;")
        self.btn_queue_worker.clicked.connect(self.toggle_queue_worker)
        
        self.btn_scheduler_worker = QPushButton("Start Scheduler Loop (artisan schedule:work)")
        self.btn_scheduler_worker.setFixedHeight(28)
        self.btn_scheduler_worker.setStyleSheet("font-size: 10px; font-weight: bold;")
        self.btn_scheduler_worker.clicked.connect(self.toggle_scheduler_worker)
        
        background_group_lay.addWidget(self.btn_queue_worker)
        background_group_lay.addWidget(self.btn_scheduler_worker)
        workers_lay.addWidget(background_group)
        workers_lay.addStretch()

        self.control_tabs.addTab(workers_widget, "Worker Controls")

        self.cmb_project.currentTextChanged.connect(self.on_project_changed)

        body.addWidget(left_panel, 1)

        # Right Column: Tabbed Terminal Console Layout
        right_panel = QFrame()
        right_panel.setObjectName("tool_card")
        right_panel.setFrameShape(QFrame.StyledPanel)
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(5, 5, 5, 5)
        
        terminal_title = QLabel("Execution Terminals & Process Outputs")
        terminal_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ef4444; padding-left: 5px; padding-top: 5px;")
        right_lay.addWidget(terminal_title)

        self.terminal_tabs = QTabWidget()
        self.terminal_tabs.setStyleSheet("QTabBar::tab { font-size: 10px; font-weight: bold; padding: 6px 12px; }")
        right_lay.addWidget(self.terminal_tabs)

        # Tab 1: Artisan Terminal
        artisan_term = QWidget()
        artisan_term_lay = QVBoxLayout(artisan_term)
        artisan_term_lay.setContentsMargins(5, 5, 5, 5)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: #0f172a; "
            "color: #f1f5f9; "
            "font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 11px; "
            "border: 1px solid #1e293b; "
            "border-radius: 6px; "
            "padding: 8px; "
            "selection-background-color: #334155;"
        )
        artisan_term_lay.addWidget(self.console)

        # Interactive Stdin input block
        stdin_lay = QHBoxLayout()
        self.txt_stdin = QLineEdit()
        self.txt_stdin.setPlaceholderText("Type interactive terminal input (e.g. yes) and press Enter...")
        self.txt_stdin.setFixedHeight(26)
        self.txt_stdin.returnPressed.connect(self.send_stdin)
        self.txt_stdin.setStyleSheet("background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; border-radius: 4px; padding-left: 6px;")
        
        self.btn_send_stdin = QPushButton()
        self.btn_send_stdin.setIcon(qta.icon("fa5s.paper-plane", color="#ef4444"))
        self.btn_send_stdin.setFixedWidth(30)
        self.btn_send_stdin.setFixedHeight(26)
        self.btn_send_stdin.clicked.connect(self.send_stdin)
        self.btn_send_stdin.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 4px;")
        
        self.btn_clear_console = QPushButton()
        self.btn_clear_console.setIcon(qta.icon("fa5s.trash", color="#94a3b8"))
        self.btn_clear_console.setFixedWidth(30)
        self.btn_clear_console.setFixedHeight(26)
        self.btn_clear_console.clicked.connect(self.console.clear)
        self.btn_clear_console.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 4px;")
        
        stdin_lay.addWidget(self.txt_stdin)
        stdin_lay.addWidget(self.btn_send_stdin)
        stdin_lay.addWidget(self.btn_clear_console)
        artisan_term_lay.addLayout(stdin_lay)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        artisan_term_lay.addWidget(self.progress_bar)
        
        self.terminal_tabs.addTab(artisan_term, "Artisan & Setup")

        # helper function to create terminal tab layout
        def create_term_tab(clear_slot):
            tab = QWidget()
            tab_lay = QVBoxLayout(tab)
            tab_lay.setContentsMargins(5, 5, 5, 5)
            
            console = QTextEdit()
            console.setReadOnly(True)
            console.setStyleSheet(
                "background-color: #0f172a; "
                "color: #f1f5f9; "
                "font-family: 'Consolas', 'Courier New', monospace; "
                "font-size: 11px; "
                "border: 1px solid #1e293b; "
                "border-radius: 6px; "
                "padding: 8px; "
                "selection-background-color: #334155;"
            )
            tab_lay.addWidget(console)
            
            ctrl_row = QHBoxLayout()
            ctrl_row.addStretch()
            btn_clear = QPushButton("Clear Console")
            btn_clear.setFixedHeight(24)
            btn_clear.setStyleSheet("font-size: 10px;")
            btn_clear.clicked.connect(clear_slot)
            ctrl_row.addWidget(btn_clear)
            tab_lay.addLayout(ctrl_row)
            return tab, console

        # Tab 2: Vite Terminal
        vite_tab, self.vite_console = create_term_tab(self.clear_vite_console)
        self.terminal_tabs.addTab(vite_tab, "Vite Server")

        # Tab 3: Queue Terminal
        queue_tab, self.queue_console = create_term_tab(self.clear_queue_console)
        self.terminal_tabs.addTab(queue_tab, "Queue Worker")

        # Tab 4: Scheduler Terminal
        scheduler_tab, self.scheduler_console = create_term_tab(self.clear_scheduler_console)
        self.terminal_tabs.addTab(scheduler_tab, "Task Scheduler")

        body.addWidget(right_panel, 1.2) # Give terminal tabs slightly more space
        layout.addLayout(body)

        self.refresh_project_list()

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Installation Folder")
        if folder:
            self.txt_location.setText(folder.replace("\\", "/"))

    def refresh_project_list(self):
        current_active_path = self.cmb_project.currentData()
        self.cmb_project.clear()
        www_dir = self.txt_location.text().strip()
        projects_dict = {}
        
        # 1. Scan default www_dir
        if os.path.exists(www_dir):
            try:
                for name in os.listdir(www_dir):
                    full_path = os.path.join(www_dir, name).replace("\\", "/")
                    if os.path.isdir(full_path):
                        if os.path.exists(os.path.join(full_path, "artisan")):
                            projects_dict[os.path.abspath(full_path).lower()] = (name, os.path.abspath(full_path))
            except Exception:
                pass
                
        # 2. Scan virtual hosts from settings
        try:
            raw_vhosts = self.main_win.settings.value("virtual_hosts", "[]")
            import json
            vhosts = json.loads(str(raw_vhosts))
            for host in vhosts:
                doc_root = host.get("path", "").strip()
                if doc_root:
                    parent = os.path.dirname(doc_root)
                    if os.path.exists(os.path.join(parent, "artisan")):
                        name = f"{os.path.basename(parent)} (vhost)"
                        projects_dict[os.path.abspath(parent).lower()] = (name, os.path.abspath(parent))
                    elif os.path.exists(os.path.join(doc_root, "artisan")):
                        name = f"{os.path.basename(doc_root)} (vhost)"
                        projects_dict[os.path.abspath(doc_root).lower()] = (name, os.path.abspath(doc_root))
        except Exception as e:
            logger.warning(f"Failed to scan virtual hosts: {e}")
            
        # 3. Load manually imported project paths
        try:
            raw_imports = self.main_win.settings.value("imported_projects", "[]")
            import json
            imported_paths = json.loads(str(raw_imports))
            for p in imported_paths:
                p = p.strip()
                if p and os.path.exists(os.path.join(p, "artisan")):
                    name = f"{os.path.basename(p)} (imported)"
                    projects_dict[os.path.abspath(p).lower()] = (name, os.path.abspath(p))
        except Exception as e:
            logger.warning(f"Failed to load imported projects: {e}")

        # Add unique projects
        for name, path in sorted(projects_dict.values(), key=lambda x: x[0].lower()):
            self.cmb_project.addItem(name, path)
            
        if current_active_path:
            idx = self.cmb_project.findData(current_active_path)
            if idx >= 0:
                self.cmb_project.setCurrentIndex(idx)

    def log(self, text, console=None):
        if console is None:
            console = self.console
            
        # Semantic color syntax highlight parser
        cleaned = text.replace("<", "&lt;").replace(">", "&gt;")
        
        if any(w in cleaned.lower() for w in ["error", "exception", "failed", "emerg"]):
            html = f'<span style="color: #ef4444;">{cleaned}</span>'
        elif any(w in cleaned.lower() for w in ["success", "completed", "installed", "created successfully", "successful"]):
            html = f'<span style="color: #10b981;">{cleaned}</span>'
        elif cleaned.startswith("> Running") or cleaned.startswith("> Running:"):
            html = f'<span style="color: #818cf8; font-weight: bold;">{cleaned}</span>'
        elif cleaned.startswith("[stdin]"):
            html = f'<span style="color: #22d3ee; font-weight: bold;">{cleaned}</span>'
        elif cleaned.startswith("Step "):
            html = f'<span style="color: #f59e0b; font-weight: bold;">{cleaned}</span>'
        else:
            html = f'<span style="color: #e2e8f0;">{cleaned}</span>'
            
        console.append(html)
        console.moveCursor(console.textCursor().MoveOperation.End)

    def send_stdin(self):
        text = self.txt_stdin.text().strip()
        if not text:
            return
            
        sent = False
        # Send to active worker
        if self.create_worker and self.create_worker.isRunning():
            sent = self.create_worker.send_input(text)
        elif self.artisan_worker and self.artisan_worker.isRunning():
            sent = self.artisan_worker.send_input(text)
            
        if sent:
            self.log(f"[stdin] > {text}")
            self.txt_stdin.clear()
        else:
            self.log(f"[stdin] (Failed to send - no active interactive process): {text}")

    def set_ui_locked(self, locked):
        self.btn_create.setEnabled(not locked)
        self.txt_name.setEnabled(not locked)
        self.txt_location.setEnabled(not locked)
        self.cmb_kit.setEnabled(not locked)
        self.db_group.setEnabled(not locked)
        self.progress_bar.setVisible(locked)

    def create_laravel_app(self):
        name = self.txt_name.text().strip()
        location = self.txt_location.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Input Error", "Please provide a project name.")
            return

        kit_index = self.cmb_kit.currentIndex()
        kits = ["none", "breeze_blade", "breeze_vue", "breeze_react"]
        starter_kit = kits[kit_index]

        db_name = self.txt_db_name.text().strip()
        db_user = self.txt_db_user.text().strip()
        db_pass = self.txt_db_pass.text().strip()

        target_path = os.path.join(location, name)
        if os.path.exists(target_path):
            QMessageBox.warning(self, "Folder Exists", f"The directory '{target_path}' already exists.")
            return

        self.console.clear()
        self.terminal_tabs.setCurrentIndex(0)
        self.log(f"Starting Laravel project creation: '{name}' in '{location}'...")
        self.set_ui_locked(True)

        self.create_worker = LaravelCreateWorker(
            project_name=name,
            parent_dir=location,
            env_root=self.main_win.env_root,
            starter_kit=starter_kit,
            db_name=db_name,
            db_user=db_user,
            db_pass=db_pass
        )
        self.create_worker.progress_msg.connect(self.log)
        self.create_worker.completed.connect(self.on_creation_finished)
        self.create_worker.start()

    def on_creation_finished(self, success, msg):
        self.set_ui_locked(False)
        if success:
            QMessageBox.information(self, "Project Created", msg)
            self.refresh_project_list()
            domain_name = f"{self.txt_name.text().strip().lower()}.test"
            proj_pub = os.path.join(self.txt_location.text().strip(), self.txt_name.text().strip(), "public").replace("\\", "/")
            
            confirm = QMessageBox.question(
                self,
                "Map Local Domain?",
                f"Would you like to map this new project to a custom domain now?\n\nDomain: http://{domain_name}\nPath: {proj_pub}",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                if not self.main_win.vhost_view:
                    from gui.vhost_view import VHostView
                    self.main_win.vhost_view = VHostView(self.main_win)
                    self.main_win.tab_containers[3][1].addWidget(self.main_win.vhost_view)
                self.main_win.vhost_view.txt_domain.setText(domain_name)
                self.main_win.vhost_view.txt_path.setText(proj_pub)
                self.main_win.tabs.setCurrentIndex(3)
        else:
            QMessageBox.critical(self, "Creation Failed", f"Laravel scaffolding failed:\n{msg}")

    def run_artisan(self, args):
        project_name = self.cmb_project.currentText()
        if not project_name:
            QMessageBox.warning(self, "Selection Error", "Please select a Laravel project from the list first.")
            return

        project_path = self.cmb_project.currentData()
        if not project_path or not os.path.exists(project_path):
            QMessageBox.warning(self, "Path Error", "Could not resolve project path.")
            return
            
        self.console.clear()
        self.terminal_tabs.setCurrentIndex(0)
        self.progress_bar.setVisible(True)
        
        self.artisan_worker = ArtisanCommandWorker(
            project_path=project_path,
            env_root=self.main_win.env_root,
            command_args=args
        )
        self.artisan_worker.progress_msg.connect(self.log)
        self.artisan_worker.completed.connect(self.on_artisan_finished)
        self.artisan_worker.start()

    def on_artisan_finished(self, success, msg):
        self.progress_bar.setVisible(False)
        if not success:
            QMessageBox.critical(self, "Artisan Error", msg)
        else:
            self.log(f"\n> {msg}")

    def run_custom_artisan(self):
        cmd = self.txt_custom_art.text().strip()
        if not cmd:
            return
            
        args = shlex.split(cmd)
        self.run_artisan(args)
        self.txt_custom_art.clear()

    def clear_vite_console(self):
        self.vite_console.clear()

    def clear_queue_console(self):
        self.queue_console.clear()

    def clear_scheduler_console(self):
        self.scheduler_console.clear()

    def load_log_history(self, project_path):
        if not project_path:
            return
        project_name = os.path.basename(project_path)
        # Load Vite history
        vite_log = os.path.join(self.main_win.log_dir, f"vite_{project_name}.log")
        self.vite_console.clear()
        if os.path.exists(vite_log):
            try:
                with open(vite_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                self.log(f"--- Loaded log history for '{project_name}' (Vite) ---", self.vite_console)
                for line in lines[-100:]:
                    self.log(line.strip(), self.vite_console)
            except Exception:
                pass

        # Load Queue history
        queue_log = os.path.join(self.main_win.log_dir, f"queue_{project_name}.log")
        self.queue_console.clear()
        if os.path.exists(queue_log):
            try:
                with open(queue_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                self.log(f"--- Loaded log history for '{project_name}' (Queue) ---", self.queue_console)
                for line in lines[-100:]:
                    self.log(line.strip(), self.queue_console)
            except Exception:
                pass

        # Load Scheduler history
        sched_log = os.path.join(self.main_win.log_dir, f"scheduler_{project_name}.log")
        self.scheduler_console.clear()
        if os.path.exists(sched_log):
            try:
                with open(sched_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                self.log(f"--- Loaded log history for '{project_name}' (Scheduler) ---", self.scheduler_console)
                for line in lines[-100:]:
                    self.log(line.strip(), self.scheduler_console)
            except Exception:
                pass

    def on_project_changed(self, text):
        path = self.cmb_project.currentData()
        if not path:
            return
            
        self.load_log_history(path)
        
        if text in self.dev_workers and self.dev_workers[text].isRunning():
            self.btn_vite_dev.setText("Stop Vite Server")
            self.btn_vite_dev.setStyleSheet("font-size: 10px; background-color: #ef4444; color: white; font-weight: bold;")
        else:
            self.btn_vite_dev.setText("Start Vite Server (npm run dev)")
            self.btn_vite_dev.setStyleSheet("font-size: 10px;")
            
        if text in self.queue_workers and self.queue_workers[text].isRunning():
            self.btn_queue_worker.setText("Stop Queue Worker")
            self.btn_queue_worker.setStyleSheet("font-size: 10px; background-color: #ef4444; color: white; font-weight: bold;")
        else:
            self.btn_queue_worker.setText("Start Queue Worker (artisan queue:work)")
            self.btn_queue_worker.setStyleSheet("font-size: 10px;")
            
        if text in self.scheduler_workers and self.scheduler_workers[text].isRunning():
            self.btn_scheduler_worker.setText("Stop Scheduler Loop")
            self.btn_scheduler_worker.setStyleSheet("font-size: 10px; background-color: #ef4444; color: white; font-weight: bold;")
        else:
            self.btn_scheduler_worker.setText("Start Scheduler Loop (artisan schedule:work)")
            self.btn_scheduler_worker.setStyleSheet("font-size: 10px;")

    def import_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Laravel Project Root Directory")
        if not folder:
            return
            
        folder = folder.replace("\\", "/")
        artisan_file = os.path.join(folder, "artisan")
        if not os.path.exists(artisan_file):
            QMessageBox.warning(self, "Invalid Directory", "The selected folder does not contain a Laravel 'artisan' file.")
            return
            
        import json
        raw_imports = self.main_win.settings.value("imported_projects", "[]")
        try:
            imported_paths = json.loads(str(raw_imports))
        except Exception:
            imported_paths = []
            
        norm_path = os.path.abspath(folder)
        exists = False
        for p in imported_paths:
            if os.path.abspath(p).lower() == norm_path.lower():
                exists = True
                break
                
        if not exists:
            imported_paths.append(folder)
            self.main_win.settings.setValue("imported_projects", json.dumps(imported_paths))
            self.main_win.settings.sync()
            
        self.refresh_project_list()
        
        idx = self.cmb_project.findData(norm_path)
        if idx >= 0:
            self.cmb_project.setCurrentIndex(idx)
        else:
            for i in range(self.cmb_project.count()):
                if os.path.abspath(self.cmb_project.itemData(i)).lower() == norm_path.lower():
                    self.cmb_project.setCurrentIndex(i)
                    break
        
        self.log(f"> Imported custom Laravel project: {folder}")

    def toggle_vite_dev(self):
        project_name = self.cmb_project.currentText()
        if not project_name:
            QMessageBox.warning(self, "Selection Error", "Please select a Laravel project first.")
            return

        if project_name in self.dev_workers and self.dev_workers[project_name].isRunning():
            # Running -> Stop it!
            self.log(f"> Stopping Vite dev server for '{project_name}'...", self.vite_console)
            self.dev_workers[project_name].terminate_process()
            self.dev_workers[project_name].wait()
            del self.dev_workers[project_name]
            self.log(f"> Vite dev server for '{project_name}' stopped.", self.vite_console)
            self.on_project_changed(project_name)
        else:
            # Stopped -> Start it!
            project_path = self.cmb_project.currentData()
            if not project_path or not os.path.exists(project_path):
                QMessageBox.warning(self, "Path Error", "Could not resolve project path.")
                return
            
            pkg_json = os.path.join(project_path, "package.json")
            if not os.path.exists(pkg_json):
                QMessageBox.warning(self, "Missing package.json", "No package.json found. Ensure this is a node project and npm install has run.")
                return
                
            self.vite_console.clear()
            self.log(f"> Starting Vite dev server (npm run dev) in background for '{project_name}'...", self.vite_console)
            
            env = os.environ.copy()
            php_active = os.path.join(self.main_win.env_root, "php", "active")
            composer_dir = os.path.join(self.main_win.env_root, "composer")
            node_dir = os.path.join(self.main_win.env_root, "nodejs")
            env["PATH"] = ";".join([php_active, composer_dir, node_dir]) + ";" + env.get("PATH", "")
            
            cmd = ["cmd.exe", "/c", "npm", "run", "dev"]
            project_name_base = os.path.basename(project_path)
            log_path = os.path.join(self.main_win.log_dir, f"vite_{project_name_base}.log")
            
            worker = LiveProcessWorker(cmd, project_path, env, log_path)
            worker.line_read.connect(lambda line: self.log(line, self.vite_console))
            
            def on_finished(code):
                self.log(f"\n--- Vite Dev Server stopped with code {code} ---", self.vite_console)
                self.on_project_changed(self.cmb_project.currentText())
                
            worker.finished.connect(on_finished)
            self.dev_workers[project_name] = worker
            worker.start()
            
            # Switch to Vite Server terminal tab
            self.terminal_tabs.setCurrentIndex(1)
            self.on_project_changed(project_name)

    def run_vite_build(self):
        project_name = self.cmb_project.currentText()
        if not project_name:
            QMessageBox.warning(self, "Selection Error", "Please select a Laravel project from the list first.")
            return

        project_path = self.cmb_project.currentData()
        if not project_path or not os.path.exists(project_path):
            QMessageBox.warning(self, "Path Error", "Could not resolve project path.")
            return
            
        self.console.clear()
        self.progress_bar.setVisible(True)
        self.terminal_tabs.setCurrentIndex(0) # Switch to Artisan & Setup tab
        
        self.build_worker = ViteBuildWorker(
            project_path=project_path,
            env_root=self.main_win.env_root
        )
        self.build_worker.progress_msg.connect(self.log)
        self.build_worker.completed.connect(self.on_vite_build_finished)
        self.build_worker.start()

    def on_vite_build_finished(self, success, msg):
        self.progress_bar.setVisible(False)
        if not success:
            QMessageBox.critical(self, "Build Error", msg)
        else:
            self.log(f"\n> {msg}")

    def toggle_queue_worker(self):
        project_name = self.cmb_project.currentText()
        if not project_name:
            QMessageBox.warning(self, "Selection Error", "Please select a Laravel project first.")
            return

        if project_name in self.queue_workers and self.queue_workers[project_name].isRunning():
            # Running -> Stop it!
            self.log(f"> Stopping Queue worker for '{project_name}'...", self.queue_console)
            self.queue_workers[project_name].terminate_process()
            self.queue_workers[project_name].wait()
            del self.queue_workers[project_name]
            self.log(f"> Queue worker for '{project_name}' stopped.", self.queue_console)
            self.on_project_changed(project_name)
        else:
            # Stopped -> Start it!
            project_path = self.cmb_project.currentData()
            if not project_path or not os.path.exists(project_path):
                QMessageBox.warning(self, "Path Error", "Could not resolve project path.")
                return
            
            artisan_file = os.path.join(project_path, "artisan")
            if not os.path.exists(artisan_file):
                QMessageBox.warning(self, "Missing artisan", "No artisan file found in the project directory.")
                return
                
            self.queue_console.clear()
            self.log(f"> Starting Queue worker (php artisan queue:work) in background for '{project_name}'...", self.queue_console)
            
            env = os.environ.copy()
            php_active = os.path.join(self.main_win.env_root, "php", "active")
            composer_dir = os.path.join(self.main_win.env_root, "composer")
            node_dir = os.path.join(self.main_win.env_root, "nodejs")
            env["PATH"] = ";".join([php_active, composer_dir, node_dir]) + ";" + env.get("PATH", "")
            
            cmd = ["cmd.exe", "/c", "php", "artisan", "queue:work"]
            project_name_base = os.path.basename(project_path)
            log_path = os.path.join(self.main_win.log_dir, f"queue_{project_name_base}.log")
            
            worker = LiveProcessWorker(cmd, project_path, env, log_path)
            worker.line_read.connect(lambda line: self.log(line, self.queue_console))
            
            def on_finished(code):
                self.log(f"\n--- Queue Worker stopped with code {code} ---", self.queue_console)
                self.on_project_changed(self.cmb_project.currentText())
                
            worker.finished.connect(on_finished)
            self.queue_workers[project_name] = worker
            worker.start()
            
            # Switch to Queue tab
            self.terminal_tabs.setCurrentIndex(2)
            self.on_project_changed(project_name)

    def toggle_scheduler_worker(self):
        project_name = self.cmb_project.currentText()
        if not project_name:
            QMessageBox.warning(self, "Selection Error", "Please select a Laravel project first.")
            return

        if project_name in self.scheduler_workers and self.scheduler_workers[project_name].isRunning():
            # Running -> Stop it!
            self.log(f"> Stopping Scheduler for '{project_name}'...", self.scheduler_console)
            self.scheduler_workers[project_name].terminate_process()
            self.scheduler_workers[project_name].wait()
            del self.scheduler_workers[project_name]
            self.log(f"> Scheduler for '{project_name}' stopped.", self.scheduler_console)
            self.on_project_changed(project_name)
        else:
            # Stopped -> Start it!
            project_path = self.cmb_project.currentData()
            if not project_path or not os.path.exists(project_path):
                QMessageBox.warning(self, "Path Error", "Could not resolve project path.")
                return
            
            artisan_file = os.path.join(project_path, "artisan")
            if not os.path.exists(artisan_file):
                QMessageBox.warning(self, "Missing artisan", "No artisan file found in the project directory.")
                return
                
            self.scheduler_console.clear()
            self.log(f"> Starting Scheduler (php artisan schedule:work) in background for '{project_name}'...", self.scheduler_console)
            
            env = os.environ.copy()
            php_active = os.path.join(self.main_win.env_root, "php", "active")
            composer_dir = os.path.join(self.main_win.env_root, "composer")
            node_dir = os.path.join(self.main_win.env_root, "nodejs")
            env["PATH"] = ";".join([php_active, composer_dir, node_dir]) + ";" + env.get("PATH", "")
            
            cmd = ["cmd.exe", "/c", "php", "artisan", "schedule:work"]
            project_name_base = os.path.basename(project_path)
            log_path = os.path.join(self.main_win.log_dir, f"scheduler_{project_name_base}.log")
            
            worker = LiveProcessWorker(cmd, project_path, env, log_path)
            worker.line_read.connect(lambda line: self.log(line, self.scheduler_console))
            
            def on_finished(code):
                self.log(f"\n--- Scheduler stopped with code {code} ---", self.scheduler_console)
                self.on_project_changed(self.cmb_project.currentText())
                
            worker.finished.connect(on_finished)
            self.scheduler_workers[project_name] = worker
            worker.start()
            
            # Switch to Scheduler tab
            self.terminal_tabs.setCurrentIndex(3)
            self.on_project_changed(project_name)

    def cleanup_processes(self):
        # Clean Vite dev workers
        for name, worker in list(self.dev_workers.items()):
            if worker.isRunning():
                try:
                    worker.terminate_process()
                    worker.wait(1000)
                except Exception:
                    pass
        self.dev_workers.clear()

        # Clean Queue workers
        for name, worker in list(self.queue_workers.items()):
            if worker.isRunning():
                try:
                    worker.terminate_process()
                    worker.wait(1000)
                except Exception:
                    pass
        self.queue_workers.clear()

        # Clean Scheduler workers
        for name, worker in list(self.scheduler_workers.items()):
            if worker.isRunning():
                try:
                    worker.terminate_process()
                    worker.wait(1000)
                except Exception:
                    pass
        self.scheduler_workers.clear()

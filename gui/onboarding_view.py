import os
import logging
import time
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
import qtawesome as qta

from core.detector import scan_all, detect_tool
from core.path_manager import update_user_path
from core.installer import (
    DOWNLOAD_URLS, download_file, extract_and_lift, 
    configure_php, configure_nginx, configure_mysql, configure_apache, create_junction
)

logger = logging.getLogger(__name__)

class ScanWorker(QThread):
    finished = Signal(dict)
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        try:
            results = scan_all(self.env_root)
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Error in ScanWorker: {e}")
            self.finished.emit({})

class InstallWorker(QThread):
    # Signals for UI feedback
    progress = Signal(str, int)  # status message, progress percent
    finished = Signal(str, bool) # tool name, success status
    
    def __init__(self, tool_name, env_root):
        super().__init__()
        self.tool_name = tool_name
        self.env_root = env_root
        
    def run(self):
        try:
            self.progress.emit(f"Initializing setup for {self.tool_name}...", 0)
            
            url = DOWNLOAD_URLS.get(self.tool_name)
            if not url:
                self.progress.emit("Invalid tool URL configuration.", 100)
                self.finished.emit(self.tool_name, False)
                return
            
            temp_dir = os.path.join(self.env_root, "downloads")
            os.makedirs(temp_dir, exist_ok=True)
            
            filename = url.split("/")[-1]
            dest_file = os.path.join(temp_dir, filename)
            
            self.progress.emit(f"Downloading {filename}...", 5)
            
            def progress_hook(percent, downloaded, total):
                p = 5 + int(percent * 0.65)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.progress.emit(f"Downloading {filename} ({mb_downloaded:.1f} MB / {mb_total:.1f} MB)... {percent}%", p)
                
            if self.tool_name == "vcredist":
                dest_exe = os.path.join(temp_dir, filename)
                download_file(url, dest_exe, progress_hook)
                
                self.progress.emit("Launching Visual C++ Redistributable installer...", 70)
                os.startfile(dest_exe)
                
                self.progress.emit("Waiting for setup completion. Please approve the prompt and click install...", 80)
                installed = False
                for _ in range(180):  # Check for up to 3 minutes
                    if os.path.exists("C:\\Windows\\System32\\vcruntime140_1.dll"):
                        installed = True
                        break
                    time.sleep(1)
                    
                if installed:
                    self.progress.emit("Visual C++ Redistributable successfully installed!", 100)
                    self.finished.emit(self.tool_name, True)
                else:
                    self.progress.emit("Visual C++ Redistributable installation skipped or timed out.", 100)
                    self.finished.emit(self.tool_name, False)
                return
                
            if self.tool_name == "git":
                dest_exe = os.path.join(temp_dir, filename)
                download_file(url, dest_exe, progress_hook)
                
                self.progress.emit("Launching Git installer...", 70)
                os.startfile(dest_exe)
                
                self.progress.emit("Waiting for setup completion. Please follow the installer prompts...", 80)
                installed = False
                import shutil as sh_util
                for _ in range(180):  # Check for up to 3 minutes
                    if os.path.exists("C:\\Program Files\\Git\\cmd\\git.exe") or sh_util.which("git"):
                        installed = True
                        break
                    time.sleep(1)
                    
                if installed:
                    # Automatically add to PATH if installed globally but not in process env path yet
                    git_path = "C:\\Program Files\\Git\\cmd"
                    if os.path.exists(os.path.join(git_path, "git.exe")):
                        update_user_path([git_path])
                        
                    self.progress.emit("Git successfully installed!", 100)
                    self.finished.emit(self.tool_name, True)
                else:
                    self.progress.emit("Git installation skipped or timed out.", 100)
                    self.finished.emit(self.tool_name, False)
                return
                
            if self.tool_name == "composer":
                composer_dir = os.path.join(self.env_root, "composer")
                os.makedirs(composer_dir, exist_ok=True)
                dest_phar = os.path.join(composer_dir, "composer.phar")
                download_file(url, dest_phar, progress_hook)
                
                self.progress.emit("Creating composer global command wrapper...", 85)
                bat_path = os.path.join(composer_dir, "composer.bat")
                with open(bat_path, "w") as f:
                    f.write('@echo off\nphp "%~dp0composer.phar" %*\n')
                
                self.progress.emit("Adding Composer directory to PATH...", 95)
                update_user_path([composer_dir])
                self.progress.emit("Composer installation complete!", 100)
                self.finished.emit(self.tool_name, True)
                return
                
            if self.tool_name == "laravel":
                composer_bat = os.path.join(self.env_root, "composer", "composer.bat")
                if not os.path.exists(composer_bat):
                    self.progress.emit("Error: Composer must be installed before installing Laravel.", 100)
                    self.finished.emit(self.tool_name, False)
                    return
                    
                self.progress.emit("Running 'composer global require laravel/installer'...", 30)
                
                # Copy and update current environment with local php binary location so composer succeeds
                env = os.environ.copy()
                php_active = os.path.join(self.env_root, "php", "active")
                env["PATH"] = php_active + ";" + env.get("PATH", "")
                
                cmd = f'"{composer_bat}" global require laravel/installer --no-interaction'
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                import subprocess as sub_proc
                res = sub_proc.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    env=env,
                    startupinfo=startupinfo,
                    creationflags=sub_proc.CREATE_NO_WINDOW
                )
                
                if res.returncode == 0:
                    self.progress.emit("Laravel Installer successfully registered globally!", 80)
                    self.progress.emit("Adding Composer global bin folder to system PATH...", 90)
                    
                    appdata = os.environ.get("APPDATA", "")
                    composer_global_bin = os.path.join(appdata, "Composer", "vendor", "bin")
                    if os.path.exists(composer_global_bin):
                        update_user_path([composer_global_bin])
                        
                    self.progress.emit("Laravel installation complete!", 100)
                    self.finished.emit(self.tool_name, True)
                else:
                    self.progress.emit(f"Composer error: {res.stderr.strip() or res.stdout.strip()}", 100)
                    self.finished.emit(self.tool_name, False)
                return
                
            download_file(url, dest_file, progress_hook)
            self.progress.emit("Extracting package contents...", 75)
            
            target_dir = None
            if self.tool_name == "php":
                target_dir = os.path.join(self.env_root, "php", "php-8.2.20")
            elif self.tool_name == "php83":
                target_dir = os.path.join(self.env_root, "php", "php-8.3.8")
            elif self.tool_name == "nginx":
                target_dir = os.path.join(self.env_root, "nginx")
            elif self.tool_name == "mysql":
                target_dir = os.path.join(self.env_root, "mariadb")
            elif self.tool_name == "apache":
                target_dir = os.path.join(self.env_root, "apache")
            elif self.tool_name == "node":
                target_dir = os.path.join(self.env_root, "nodejs")
            elif self.tool_name == "phpmyadmin":
                target_dir = os.path.join(self.env_root, "phpmyadmin")
                
            extract_and_lift(dest_file, target_dir)
            self.progress.emit("Extraction complete.", 85)
            
            self.progress.emit("Applying post-install configuration scripts...", 90)
            paths_to_add = []
            
            if self.tool_name in ["php", "php83"]:
                configure_php(target_dir)
                if self.tool_name == "php":
                    active_junction = os.path.join(self.env_root, "php", "active")
                    create_junction(target_dir, active_junction)
                    paths_to_add.append(active_junction)
                
            elif self.tool_name == "nginx":
                html_root = os.path.join(self.env_root, "www")
                pma_root = os.path.join(self.env_root, "phpmyadmin")
                os.makedirs(html_root, exist_ok=True)
                index_php = os.path.join(html_root, "index.php")
                if not os.path.exists(index_php):
                    with open(index_php, "w") as f:
                        f.write("<?php phpinfo(); ?>")
                configure_nginx(target_dir, html_root, pma_root)
                paths_to_add.append(target_dir)
                
            elif self.tool_name == "mysql":
                success, msg = configure_mysql(target_dir)
                if not success:
                    logger.warning(f"MariaDB setup warning: {msg}")
                paths_to_add.append(os.path.join(target_dir, "bin"))
                
            elif self.tool_name == "apache":
                html_root = os.path.join(self.env_root, "www")
                php_active = os.path.join(self.env_root, "php", "active")
                configure_apache(target_dir, html_root, php_active)
                paths_to_add.append(os.path.join(target_dir, "bin"))
                
            elif self.tool_name == "node":
                paths_to_add.append(target_dir)
                
            elif self.tool_name == "phpmyadmin":
                pass
                
            if paths_to_add:
                update_user_path(paths_to_add)
                
            try:
                os.remove(dest_file)
            except Exception:
                pass
                
            self.progress.emit(f"Successfully configured {self.tool_name.upper()}.", 100)
            self.finished.emit(self.tool_name, True)
            
        except Exception as e:
            logger.error(f"Installation failed for {self.tool_name}: {e}")
            self.progress.emit(f"Error installing {self.tool_name}: {e}", 100)
            self.finished.emit(self.tool_name, False)


class OnboardingView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.worker = None
        self.scan_worker = None
        self.last_scan_results = None
        self.install_queue = []
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Header Info
        title_label = QLabel("Environment Setup Check")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        sub_label = QLabel("Verify what required development assets are active on your system. Run single or batch installation options.")
        sub_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(sub_label)
        
        self.priv_banner = QLabel()
        self.priv_banner.setWordWrap(True)
        self.update_privilege_banner()
        layout.addWidget(self.priv_banner)
        
        # Scroll area for native styled items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.StyledPanel)
        
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(8)
        
        self.tool_keys = ["vcredist", "git", "php", "composer", "laravel", "mysql", "nginx", "apache", "node", "phpmyadmin"]
        self.tool_display = {
            "vcredist": ("Visual C++ Redistributable 2015-2022", "Required system DLLs for PHP, Apache, and MySQL."),
            "git": ("Git Version Control", "Essential for Laravel package tracking and repository versioning."),
            "php": ("PHP Engine", "Essential for Laravel backend compilation."),
            "composer": ("Composer Package Manager", "PHP package dependency manager."),
            "laravel": ("Laravel Global Installer", "Official CLI tool for creating new Laravel applications globally."),
            "mysql": ("MySQL / MariaDB Database", "Relational database server for storage."),
            "nginx": ("Nginx Web Server", "Modern high-concurrency web server."),
            "apache": ("Apache Web Server", "Traditional HTTP web server."),
            "node": ("Node.js & NPM", "Compiles Laravel frontend assets via Vite."),
            "phpmyadmin": ("phpMyAdmin", "Web GUI for database administration.")
        }
        
        self.cards = {}
        for key in self.tool_keys:
            card = self.create_tool_card(key)
            self.scroll_layout.addWidget(card)
            self.cards[key] = card
            
        scroll.setWidget(self.scroll_widget)
        layout.addWidget(scroll)
        
        # Footer installation bar (Standard native layouts)
        self.footer_frame = QFrame()
        self.footer_frame.setFrameShape(QFrame.StyledPanel)
        self.footer_frame.setFrameShadow(QFrame.Raised)
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(10, 10, 10, 10)
        
        self.progress_layout = QVBoxLayout()
        self.progress_label = QLabel("Idle - All components verified.")
        self.progress_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setTextVisible(True)
        
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        footer_layout.addLayout(self.progress_layout, 4)
        
        self.btn_install_all = QPushButton("Install All Missing")
        self.btn_install_all.setFixedHeight(35)
        self.btn_install_all.clicked.connect(self.install_all_missing)
        footer_layout.addWidget(self.btn_install_all, 1)
        
        layout.addWidget(self.footer_frame)
        
    def create_tool_card(self, key):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setFrameShadow(QFrame.Raised)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        
        # Status Icon (using qtawesome but colored standard)
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        card_layout.addWidget(icon_label)
        card.setProperty("status_icon", icon_label)
        
        # Metadata
        text_layout = QVBoxLayout()
        name_label = QLabel(self.tool_display[key][0])
        name_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        desc_label = QLabel(self.tool_display[key][1])
        desc_label.setStyleSheet("font-size: 11px;")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(desc_label)
        card_layout.addLayout(text_layout, 3)
        
        # Version Tag
        ver_label = QLabel("Checking status...")
        ver_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        card_layout.addWidget(ver_label)
        card.setProperty("ver_label", ver_label)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        btn_path = QPushButton("Add to PATH")
        btn_path.setFixedSize(90, 24)
        btn_path.setStyleSheet("font-size: 11px; font-weight: bold;")
        btn_path.setVisible(False)
        btn_path.clicked.connect(lambda: self.add_tool_to_path(key))
        btn_layout.addWidget(btn_path)
        card.setProperty("btn_path", btn_path)
        
        btn_action = QPushButton("Install")
        btn_action.setFixedSize(85, 24)
        btn_action.setStyleSheet("font-weight: bold; font-size: 11px;")
        btn_action.clicked.connect(lambda: self.install_single_tool(key))
        btn_layout.addWidget(btn_action)
        card.setProperty("btn_action", btn_action)
        
        card_layout.addLayout(btn_layout, 1)
        return card
        
    def refresh_status(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
            
        self.progress_label.setText("Scanning system components...")
        self.scan_worker = ScanWorker(self.main_win.env_root)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.start()
        
    def on_scan_finished(self, results):
        self.last_scan_results = results
        if not results:
            self.progress_label.setText("Scan failed or returned empty.")
            return
            
        for key in self.tool_keys:
            res = results.get(key)
            if not res:
                continue
            card = self.cards[key]
            
            icon_lbl = card.property("status_icon")
            ver_lbl = card.property("ver_label")
            btn_action = card.property("btn_action")
            btn_path = card.property("btn_path")
            
            if not self.worker or not self.worker.isRunning():
                btn_action.setEnabled(True)
            
            if res["installed"]:
                if res["in_path"] or key == "phpmyadmin":
                    # Fully configured (Green Check)
                    icon_lbl.setPixmap(qta.icon("fa5s.check-circle", color="#008000").pixmap(QSize(20, 20)))
                    ver_lbl.setText(f"v{res['version']}")
                    ver_lbl.setStyleSheet("color: #008000; font-weight: bold; font-size: 12px;")
                    btn_action.setText("Reinstall")
                    btn_path.setVisible(False)
                else:
                    # Installed but not in PATH (Warning Orange)
                    icon_lbl.setPixmap(qta.icon("fa5s.exclamation-circle", color="#b25900").pixmap(QSize(20, 20)))
                    ver_lbl.setText(f"v{res['version']} (No PATH)")
                    ver_lbl.setStyleSheet("color: #b25900; font-weight: bold; font-size: 12px;")
                    btn_action.setText("Reinstall")
                    btn_path.setVisible(True)
            else:
                # Not installed (Red Cross)
                icon_lbl.setPixmap(qta.icon("fa5s.times-circle", color="#d13438").pixmap(QSize(20, 20)))
                ver_lbl.setText("Not Detected")
                ver_lbl.setStyleSheet("color: #64748b; font-weight: normal; font-size: 12px;")
                btn_action.setText("Install")
                btn_path.setVisible(False)
                
        if self.worker and self.worker.isRunning():
            self.lock_ui_running()
        else:
            self.progress_label.setText("System scan completed.")
            
    def lock_ui_running(self):
        for key in self.tool_keys:
            self.cards[key].property("btn_action").setEnabled(False)
            self.cards[key].property("btn_path").setEnabled(False)
        self.btn_install_all.setEnabled(False)
        
    def unlock_ui_idle(self):
        for key in self.tool_keys:
            self.cards[key].property("btn_action").setEnabled(True)
            self.cards[key].property("btn_path").setEnabled(True)
        self.btn_install_all.setEnabled(True)
        self.refresh_status()
        
    def add_tool_to_path(self, key):
        if not self.last_scan_results:
            return
        res = self.last_scan_results.get(key)
        if res and res["installed"] and res["path"]:
            directory = os.path.dirname(os.path.abspath(res["path"]))
            success, msg = update_user_path([directory])
            self.progress_label.setText(msg)
            self.refresh_status()
            
    def install_single_tool(self, key):
        self.lock_ui_running()
        self.start_worker_thread(key)
        
    def install_all_missing(self):
        self.progress_label.setText("Preparing installation scan...")
        self.lock_ui_running()
        
        self.scan_worker = ScanWorker(self.main_win.env_root)
        
        def handle_install_all_scan(results):
            try:
                self.scan_worker.finished.disconnect()
            except Exception:
                pass
            self.on_scan_finished(results)
            
            order = ["php", "composer", "mysql", "nginx", "apache", "node", "phpmyadmin"]
            self.install_queue = [t for t in order if not results.get(t, {}).get("installed", False)]
            
            if not self.install_queue:
                self.progress_label.setText("All components are already installed!")
                self.unlock_ui_idle()
                return
                
            self.process_install_queue()
            
        self.scan_worker.finished.connect(handle_install_all_scan)
        self.scan_worker.start()
        
    def process_install_queue(self):
        if not self.install_queue:
            self.progress_label.setText("Batch setup completed.")
            self.progress_bar.setValue(100)
            self.unlock_ui_idle()
            return
            
        next_tool = self.install_queue.pop(0)
        self.start_worker_thread(next_tool)
        
    def start_worker_thread(self, tool_name):
        self.worker = InstallWorker(tool_name, self.main_win.env_root)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()
        
    def on_worker_progress(self, message, percentage):
        self.progress_label.setText(message)
        self.progress_bar.setValue(percentage)
        
    def on_worker_finished(self, tool_name, success):
        if not success:
            self.progress_label.setText(f"Installation failed for {tool_name.upper()}. See settings logs.")
            self.unlock_ui_idle()
            self.install_queue.clear()
            return
            
        if self.install_queue:
            self.process_install_queue()
        else:
            self.unlock_ui_idle()

    def check_privileges(self):
        import ctypes
        import winreg
        
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
            
        dev_mode = False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock",
                0,
                winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, "AllowDevelopmentWithoutDevLicense")
            dev_mode = (val == 1)
            winreg.CloseKey(key)
        except Exception:
            pass
            
        return is_admin, dev_mode

    def update_privilege_banner(self):
        is_admin, dev_mode = self.check_privileges()
        
        if is_admin:
            self.priv_banner.setText("🛡️ Running as Administrator. Symbolic link creation is fully enabled.")
            self.priv_banner.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.15);"
                "color: #22c55e;"
                "border: 1px solid #22c55e;"
                "border-radius: 4px;"
                "padding: 8px;"
                "font-size: 11px;"
                "font-weight: bold;"
            )
        elif dev_mode:
            self.priv_banner.setText("💻 Windows Developer Mode is Active. Symbolic link creation is fully enabled.")
            self.priv_banner.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.15);"
                "color: #22c55e;"
                "border: 1px solid #22c55e;"
                "border-radius: 4px;"
                "padding: 8px;"
                "font-size: 11px;"
                "font-weight: bold;"
            )
        else:
            self.priv_banner.setText(
                "⚠️ Symbolic Link Warning: Switching PHP versions requires either administrative privileges "
                "or Windows Developer Mode to be enabled. Run this application as Administrator to avoid failures."
            )
            self.priv_banner.setStyleSheet(
                "background-color: rgba(249, 115, 22, 0.15);"
                "color: #f97316;"
                "border: 1px solid #f97316;"
                "border-radius: 4px;"
                "padding: 8px;"
                "font-size: 11px;"
                "font-weight: bold;"
            )

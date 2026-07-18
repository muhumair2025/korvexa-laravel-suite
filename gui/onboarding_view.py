import os
import logging
import time
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QScrollArea, QFrame, QMessageBox, QComboBox
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
    completed = Signal(dict)
    
    def __init__(self, env_root):
        super().__init__()
        self.env_root = env_root
        
    def run(self):
        try:
            results = scan_all(self.env_root)
            self.completed.emit(results)
        except Exception as e:
            logger.error(f"Error in ScanWorker: {e}")
            self.completed.emit({})

class InstallWorker(QThread):
    # Signals for UI feedback
    progress = Signal(str, int)  # status message, progress percent
    completed = Signal(str, str, str) # tool name, status ("success", "failed", "paused"), error_msg
    
    def __init__(self, tool_name, env_root):
        super().__init__()
        self.tool_name = tool_name
        self.env_root = env_root
        self._paused = False
        
    def pause(self):
        self._paused = True
        
    def is_paused_requested(self):
        return self._paused
        
    def run(self):
        try:
            self.progress.emit(f"Initializing setup for {self.tool_name}...", 0)
            
            url = DOWNLOAD_URLS.get(self.tool_name)
            if not url:
                self.progress.emit("Invalid tool URL configuration.", 100)
                self.finished.emit(self.tool_name, "failed")
                return
            
            temp_dir = os.path.join(self.env_root, "downloads")
            os.makedirs(temp_dir, exist_ok=True)
            
            filename = url.split("/")[-1]
            dest_file = os.path.join(temp_dir, filename)
            
            self.progress.emit(f"Downloading {filename}...", 5)
            
            def progress_hook(percent, downloaded, total):
                if self.is_paused_requested():
                    raise Exception("Download paused by user")
                p = 5 + int(percent * 0.65)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.progress.emit(f"Downloading {filename} ({mb_downloaded:.1f} MB / {mb_total:.1f} MB)... {percent}%", p)
                
            if self.tool_name == "vcredist":
                dest_exe = os.path.join(temp_dir, filename)
                download_file(url, dest_exe, progress_hook)
                
                if self.is_paused_requested():
                    raise Exception("Download paused by user")
                    
                self.progress.emit("Launching Visual C++ Redistributable installer...", 70)
                os.startfile(dest_exe)
                
                self.progress.emit("Waiting for setup completion. Please approve the prompt and click install...", 80)
                installed = False
                for _ in range(180):  # Check for up to 3 minutes
                    if self.is_paused_requested():
                        raise Exception("Download paused by user")
                    if os.path.exists("C:\\Windows\\System32\\vcruntime140_1.dll"):
                        installed = True
                        break
                    time.sleep(1)
                    
                if installed:
                    self.progress.emit("Visual C++ Redistributable successfully installed!", 100)
                    self.completed.emit(self.tool_name, "success", "")
                else:
                    self.progress.emit("Visual C++ Redistributable installation skipped or timed out.", 100)
                    self.completed.emit(self.tool_name, "failed", "Visual C++ Redistributable installation skipped or timed out.")
                return
                
            if self.tool_name == "git":
                dest_exe = os.path.join(temp_dir, filename)
                download_file(url, dest_exe, progress_hook)
                
                if self.is_paused_requested():
                    raise Exception("Download paused by user")
                    
                self.progress.emit("Launching Git installer...", 70)
                os.startfile(dest_exe)
                
                self.progress.emit("Waiting for setup completion. Please follow the installer prompts...", 80)
                installed = False
                import shutil as sh_util
                for _ in range(180):  # Check for up to 3 minutes
                    if self.is_paused_requested():
                        raise Exception("Download paused by user")
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
                    self.completed.emit(self.tool_name, "success", "")
                else:
                    self.progress.emit("Git installation skipped or timed out.", 100)
                    self.completed.emit(self.tool_name, "failed", "Git installation skipped or timed out.")
                return
                
            if self.tool_name == "composer":
                composer_dir = os.path.join(self.env_root, "composer")
                os.makedirs(composer_dir, exist_ok=True)
                dest_phar = os.path.join(composer_dir, "composer.phar")
                download_file(url, dest_phar, progress_hook)
                
                if self.is_paused_requested():
                    raise Exception("Download paused by user")
                    
                self.progress.emit("Creating composer global command wrapper...", 85)
                bat_path = os.path.join(composer_dir, "composer.bat")
                with open(bat_path, "w") as f:
                    f.write('@echo off\nphp "%~dp0composer.phar" %*\n')
                
                self.progress.emit("Adding Composer directory to PATH...", 95)
                update_user_path([composer_dir])
                self.progress.emit("Composer installation complete!", 100)
                self.completed.emit(self.tool_name, "success", "")
                return
                
            if self.tool_name == "laravel":
                composer_bat = os.path.join(self.env_root, "composer", "composer.bat")
                if not os.path.exists(composer_bat):
                    self.progress.emit("Error: Composer must be installed before installing Laravel.", 100)
                    self.completed.emit(self.tool_name, "failed", "Composer must be installed before installing Laravel.")
                    return
                    
                self.progress.emit("Running 'composer global require laravel/installer'...", 30)
                
                if self.is_paused_requested():
                    raise Exception("Download paused by user")
                    
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
                    self.completed.emit(self.tool_name, "success", "")
                else:
                    self.progress.emit(f"Composer error: {res.stderr.strip() or res.stdout.strip()}", 100)
                    err_msg = f"Composer global require failed with return code {res.returncode}.\n\nCommand: {cmd}\n\nStdout:\n{res.stdout.strip()}\n\nStderr:\n{res.stderr.strip()}"
                    self.completed.emit(self.tool_name, "failed", err_msg)
                return
                
            download_file(url, dest_file, progress_hook)
            
            if self.is_paused_requested():
                raise Exception("Download paused by user")
                
            self.progress.emit("Extracting package contents...", 75)
            
            target_dir = None
            if self.tool_name == "php":
                target_dir = os.path.join(self.env_root, "php", "php-8.2.20")
            elif self.tool_name == "php83":
                target_dir = os.path.join(self.env_root, "php", "php-8.3.8")
            elif self.tool_name == "php84":
                target_dir = os.path.join(self.env_root, "php", "php-8.4.3")
            elif self.tool_name == "php85":
                target_dir = os.path.join(self.env_root, "php", "php-8.5.1")
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
            elif self.tool_name == "mailpit":
                target_dir = os.path.join(self.env_root, "mailpit")
                
            extract_and_lift(dest_file, target_dir)
            
            if self.is_paused_requested():
                raise Exception("Download paused by user")
                
            self.progress.emit("Extraction complete.", 85)
            
            self.progress.emit("Applying post-install configuration scripts...", 90)
            paths_to_add = []
            
            if self.tool_name in ["php", "php83", "php84", "php85"]:
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
                
            elif self.tool_name == "mailpit":
                paths_to_add.append(target_dir)
                
            if paths_to_add:
                update_user_path(paths_to_add)
                
            try:
                os.remove(dest_file)
            except Exception:
                pass
                
            self.progress.emit(f"Successfully configured {self.tool_name.upper()}.", 100)
            self.completed.emit(self.tool_name, "success", "")
            
        except Exception as e:
            if "paused" in str(e).lower() or "download paused" in str(e).lower():
                logger.info(f"Installation paused for {self.tool_name}")
                self.progress.emit(f"Paused - {self.tool_name.upper()} download.", -1)
                self.completed.emit(self.tool_name, "paused", "")
            else:
                logger.error(f"Installation failed for {self.tool_name}: {e}")
                self.progress.emit(f"Error installing {self.tool_name}: {e}", 100)
                self.completed.emit(self.tool_name, "failed", str(e))


class OnboardingView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.worker = None
        self.scan_worker = None
        self.last_scan_results = None
        self.install_queue = []
        self.is_paused = False
        self.is_cancelling = False
        
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
        
        self.tool_keys = ["vcredist", "git", "php", "composer", "laravel", "mysql", "nginx", "apache", "node", "phpmyadmin", "mailpit"]
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
            "phpmyadmin": ("phpMyAdmin", "Web GUI for database administration."),
            "mailpit": ("Mailpit SMTP & Webmail", "Testing mail server that catches any sent emails for local web application debugging.")
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
        footer_layout.setContentsMargins(15, 10, 15, 10)
        footer_layout.setSpacing(20)
        
        self.progress_layout = QVBoxLayout()
        self.progress_layout.setSpacing(5)
        
        self.progress_label = QLabel("Idle - All components verified.")
        self.progress_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        footer_layout.addLayout(self.progress_layout, 3)
        
        # Buttons layout container
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(8)
        self.buttons_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Dynamic installation action button
        self.btn_install_all = QPushButton("Install All Missing")
        self.btn_install_all.setFixedHeight(30)
        self.btn_install_all.setMinimumWidth(140)
        self.btn_install_all.setMaximumWidth(165)
        self.btn_install_all.setIcon(qta.icon("fa5s.download"))
        self.btn_install_all.setIconSize(QSize(12, 12))
        self.btn_install_all.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.btn_install_all.clicked.connect(self.handle_install_button_click)
        self.buttons_layout.addWidget(self.btn_install_all)
        
        # Cancel button (hidden by default)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setMinimumWidth(90)
        self.btn_cancel.setMaximumWidth(110)
        self.btn_cancel.setIcon(qta.icon("fa5s.ban"))
        self.btn_cancel.setIconSize(QSize(11, 11))
        self.btn_cancel.setStyleSheet("font-size: 11px;")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_installation)
        self.buttons_layout.addWidget(self.btn_cancel)
        
        # Check Updates button
        self.btn_check_updates = QPushButton("Check Updates")
        self.btn_check_updates.setFixedHeight(30)
        self.btn_check_updates.setMinimumWidth(120)
        self.btn_check_updates.setMaximumWidth(140)
        self.btn_check_updates.setIcon(qta.icon("fa5s.sync-alt"))
        self.btn_check_updates.setIconSize(QSize(11, 11))
        self.btn_check_updates.setStyleSheet("font-size: 11px;")
        self.btn_check_updates.clicked.connect(self.check_updates)
        self.buttons_layout.addWidget(self.btn_check_updates)
        
        footer_layout.addLayout(self.buttons_layout, 2)
        
        layout.addWidget(self.footer_frame)
        self.refresh_icons()
        
    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_cancel.setIcon(qta.icon("fa5s.ban", color=color))
        self.btn_check_updates.setIcon(qta.icon("fa5s.sync-alt", color=color))
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.btn_install_all.setIcon(qta.icon("fa5s.pause", color=color))
        elif getattr(self, 'is_paused', False):
            self.btn_install_all.setIcon(qta.icon("fa5s.play", color=color))
        else:
            self.btn_install_all.setIcon(qta.icon("fa5s.download", color=color))
            
        # Dynamically style thin progress bar based on active theme to prevent Windows clipping bug
        if self.main_win.theme == "dark":
            self.progress_bar.setStyleSheet(
                "QProgressBar {"
                "  background-color: #1e293b;"
                "  border: 1px solid #334155;"
                "  border-radius: 4px;"
                "}"
                "QProgressBar::chunk {"
                "  background-color: #ef4444;"
                "  border-radius: 3px;"
                "}"
            )
        else:
            self.progress_bar.setStyleSheet(
                "QProgressBar {"
                "  background-color: #e2e8f0;"
                "  border: 1px solid #cbd5e1;"
                "  border-radius: 4px;"
                "}"
                "QProgressBar::chunk {"
                "  background-color: #ef4444;"
                "  border-radius: 3px;"
                "}"
            )

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
        
        if key == "node":
            combo_layout = QHBoxLayout()
            combo_label = QLabel("Select version:")
            combo_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
            self.node_combo = QComboBox()
            self.node_combo.setFixedHeight(22)
            self.node_combo.setStyleSheet("font-size: 11px;")
            
            # LTS Versions
            self.node_combo.addItems([
                "Node.js 22 LTS (Recommended)",
                "Node.js 20 LTS",
                "Node.js 18 LTS"
            ])
            self.node_combo.currentIndexChanged.connect(self.on_node_version_changed)
            combo_layout.addWidget(combo_label)
            combo_layout.addWidget(self.node_combo)
            combo_layout.addStretch()
            text_layout.addLayout(combo_layout)
            
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
        btn_action.clicked.connect(lambda checked=False, k=key: self.install_single_tool(k))
        btn_layout.addWidget(btn_action)
        card.setProperty("btn_action", btn_action)
        
        card_layout.addLayout(btn_layout, 1)
        return card

    def on_node_version_changed(self, index):
        from core.installer import DOWNLOAD_URLS
        urls = [
            "https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip",
            "https://nodejs.org/dist/v20.18.1/node-v20.18.1-win-x64.zip",
            "https://nodejs.org/dist/v18.20.5/node-v18.20.5-win-x64.zip"
        ]
        if index < len(urls):
            DOWNLOAD_URLS["node"] = urls[index]
            logger.info(f"Node.js download URL updated to: {urls[index]}")
        
    def refresh_status(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
            
        def get_onboarding_state():
            paths = [
                self.main_win.env_root,
                os.path.join(self.main_win.env_root, "php"),
                os.path.join(self.main_win.env_root, "php", "active"),
                os.path.join(self.main_win.env_root, "composer"),
                os.path.join(self.main_win.env_root, "nginx"),
                os.path.join(self.main_win.env_root, "mariadb"),
                os.path.join(self.main_win.env_root, "mysql"),
                os.path.join(self.main_win.env_root, "apache"),
                os.path.join(self.main_win.env_root, "nodejs"),
            ]
            state = []
            for p in paths:
                exists = os.path.exists(p)
                mtime = 0
                if exists:
                    try:
                        mtime = os.path.getmtime(p)
                    except Exception:
                        pass
                state.append((exists, mtime))
            return tuple(state)

        from core.cache import cache_manager
        cache_key = f"onboarding_status:{self.main_win.env_root}"
        cached = cache_manager.get(cache_key, validator_func=get_onboarding_state)
        
        if cached is not None:
            self.on_scan_finished(cached)
            return

        self.progress_label.setText("Scanning system components...")
        self.scan_worker = ScanWorker(self.main_win.env_root)
        self.scan_worker.completed.connect(lambda r: self.on_scan_finished_and_cache(r, get_onboarding_state))
        self.scan_worker.start()

    def on_scan_finished_and_cache(self, results, get_state_func):
        from core.cache import cache_manager
        cache_key = f"onboarding_status:{self.main_win.env_root}"
        cache_manager.set(cache_key, results, validator_state=get_state_func())
        self.on_scan_finished(results)
        
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
            
            try:
                btn_action.clicked.disconnect()
            except Exception:
                pass
            
            if res["installed"]:
                if res["in_path"] or key == "phpmyadmin":
                    # Fully configured (Green Check)
                    icon_lbl.setPixmap(qta.icon("fa5s.check-circle", color="#008000").pixmap(QSize(20, 20)))
                    ver_lbl.setText(f"v{res['version']}")
                    ver_lbl.setStyleSheet("color: #008000; font-weight: bold; font-size: 12px;")
                    btn_path.setVisible(False)
                else:
                    # Installed but not in PATH (Warning Orange)
                    icon_lbl.setPixmap(qta.icon("fa5s.exclamation-circle", color="#b25900").pixmap(QSize(20, 20)))
                    ver_lbl.setText(f"v{res['version']} (No PATH)")
                    ver_lbl.setStyleSheet("color: #b25900; font-weight: bold; font-size: 12px;")
                    btn_path.setVisible(True)
                
                btn_action.setText("Uninstall")
                btn_action.setStyleSheet("font-weight: bold; font-size: 11px; color: #ef4444;")
                btn_action.clicked.connect(lambda checked=False, k=key: self.uninstall_single_tool(k))
            else:
                # Not installed (Red Cross)
                icon_lbl.setPixmap(qta.icon("fa5s.times-circle", color="#d13438").pixmap(QSize(20, 20)))
                ver_lbl.setText("Not Detected")
                ver_lbl.setStyleSheet("color: #64748b; font-weight: normal; font-size: 12px;")
                btn_path.setVisible(False)
                
                btn_action.setText("Install")
                btn_action.setStyleSheet("font-weight: bold; font-size: 11px; color: #ffffff;" if self.main_win.theme == "dark" else "font-weight: bold; font-size: 11px;")
                btn_action.clicked.connect(lambda checked=False, k=key: self.install_single_tool(k))
                
        if self.worker and self.worker.isRunning():
            self.lock_ui_running()
        else:
            self.progress_label.setText("System scan completed.")
            
    def lock_ui_running(self):
        for key in self.tool_keys:
            self.cards[key].property("btn_action").setEnabled(False)
            self.cards[key].property("btn_path").setEnabled(False)
        self.btn_check_updates.setEnabled(False)
        self.btn_install_all.setEnabled(True)
        
    def unlock_ui_idle(self):
        for key in self.tool_keys:
            self.cards[key].property("btn_action").setEnabled(True)
            self.cards[key].property("btn_path").setEnabled(True)
        self.btn_check_updates.setEnabled(True)
        self.btn_install_all.setEnabled(True)
        self.btn_install_all.setText("Install All Missing")
        self.btn_install_all.setIcon(qta.icon("fa5s.download", color=self.main_win.get_icon_color()))
        self.btn_cancel.setVisible(False)
        self.is_paused = False
        self.is_cancelling = False
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
            
    def handle_install_button_click(self):
        if self.worker and self.worker.isRunning():
            # Currently downloading/configuring, so click means PAUSE
            self.pause_installation()
        elif self.is_paused:
            # Currently paused, so click means RESUME
            self.resume_installation()
        else:
            # Idle, so click means INSTALL ALL MISSING
            self.install_all_missing()
            
    def pause_installation(self):
        if self.worker and self.worker.isRunning():
            self.progress_label.setText("Pausing setup...")
            self.worker.pause()
            
    def resume_installation(self):
        if self.install_queue:
            self.is_paused = False
            self.lock_ui_running()
            self.btn_install_all.setText("Pause")
            self.btn_install_all.setIcon(qta.icon("fa5s.pause", color=self.main_win.get_icon_color()))
            self.btn_cancel.setVisible(True)
            self.process_install_queue()
            
    def cancel_installation(self):
        self.is_cancelling = True
        self.install_queue.clear()
        if self.worker and self.worker.isRunning():
            self.progress_label.setText("Cancelling current installation...")
            self.worker.pause()  # Signal thread to stop
        else:
            self.unlock_ui_idle()
            self.progress_label.setText("Installation cancelled.")
            
    def install_single_tool(self, key):
        self.is_paused = False
        self.is_cancelling = False
        self.lock_ui_running()
        self.btn_install_all.setText("Pause")
        self.btn_install_all.setIcon(qta.icon("fa5s.pause", color=self.main_win.get_icon_color()))
        self.btn_cancel.setVisible(True)
        self.start_worker_thread(key)

    def uninstall_single_tool(self, key):
        tool_name = self.tool_display[key][0]
        reply = QMessageBox.question(
            self,
            "Confirm Uninstall",
            f"Are you sure you want to uninstall {tool_name}? This will delete its installed files and downloaded packages.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.progress_label.setText(f"Uninstalling {tool_name}...")
        self.progress_bar.setValue(10)
        
        # 1. Stop associated service/process if running
        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        proc_map = {
            "php": ["php-cgi.exe", "php.exe"],
            "mysql": ["mysqld.exe"],
            "nginx": ["nginx.exe"],
            "apache": ["httpd.exe"],
            "node": ["node.exe"]
        }
        if key in proc_map:
            for proc in proc_map[key]:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc],
                        capture_output=True,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception:
                    pass
                    
        self.progress_bar.setValue(30)
        
        # 2. Delete installed folders
        import shutil
        paths_to_delete = []
        
        if key == "php":
            paths_to_delete = [
                os.path.join(self.main_win.env_root, "php", "php-8.2.20"),
                os.path.join(self.main_win.env_root, "php", "php-8.3.8"),
                os.path.join(self.main_win.env_root, "php", "php-8.4.3"),
                os.path.join(self.main_win.env_root, "php", "php-8.5.1"),
                os.path.join(self.main_win.env_root, "php", "active")
            ]
        elif key == "composer":
            paths_to_delete = [os.path.join(self.main_win.env_root, "composer")]
        elif key == "laravel":
            # Run composer global remove laravel/installer
            self.progress_label.setText("Removing Laravel Installer globally via Composer...")
            composer_bat = os.path.join(self.main_win.env_root, "composer", "composer.bat")
            if os.path.exists(composer_bat):
                try:
                    env = os.environ.copy()
                    php_active = os.path.join(self.main_win.env_root, "php", "active")
                    env["PATH"] = php_active + ";" + env.get("PATH", "")
                    subprocess.run(
                        f'"{composer_bat}" global remove laravel/installer --no-interaction',
                        shell=True,
                        capture_output=True,
                        env=env,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception:
                    pass
            # Delete bat file
            appdata = os.environ.get("APPDATA", "")
            laravel_bat = os.path.join(appdata, "Composer", "vendor", "bin", "laravel.bat")
            laravel_exe = os.path.join(appdata, "Composer", "vendor", "bin", "laravel")
            paths_to_delete = [laravel_bat, laravel_exe]
        elif key == "mysql":
            paths_to_delete = [
                os.path.join(self.main_win.env_root, "mariadb"),
                os.path.join(self.main_win.env_root, "mysql")
            ]
        elif key == "nginx":
            paths_to_delete = [os.path.join(self.main_win.env_root, "nginx")]
        elif key == "apache":
            paths_to_delete = [os.path.join(self.main_win.env_root, "apache")]
        elif key == "node":
            paths_to_delete = [os.path.join(self.main_win.env_root, "nodejs")]
        elif key == "phpmyadmin":
            paths_to_delete = [os.path.join(self.main_win.env_root, "phpmyadmin")]
        elif key == "mailpit":
            paths_to_delete = [os.path.join(self.main_win.env_root, "mailpit")]
            
        # Execute directory deletion with retry/delay to prevent Windows locking issues
        for path in paths_to_delete:
            if os.path.exists(path):
                for attempt in range(5):
                    try:
                        if os.path.isdir(path) and not os.path.islink(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        break
                    except Exception:
                        time.sleep(0.2)
                        
        self.progress_bar.setValue(70)
        
        # 3. Delete downloaded zips/exes
        downloads_dir = os.path.join(self.main_win.env_root, "downloads")
        if os.path.exists(downloads_dir):
            filenames_to_delete = []
            if key == "vcredist":
                filenames_to_delete.append("vc_redist.x64.exe")
            elif key == "git":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("git-") and f.lower().endswith(".exe"):
                        filenames_to_delete.append(f)
            elif key == "php":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("php-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "composer":
                filenames_to_delete.append("composer.phar")
            elif key == "mysql":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("mariadb-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "nginx":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("nginx-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "apache":
                for f in os.listdir(downloads_dir):
                    if (f.lower().startswith("httpd-") or f.lower().startswith("apache-")) and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "node":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("node-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "phpmyadmin":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("phpmyadmin-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
            elif key == "mailpit":
                for f in os.listdir(downloads_dir):
                    if f.lower().startswith("mailpit-") and f.lower().endswith(".zip"):
                        filenames_to_delete.append(f)
                        
            for f in filenames_to_delete:
                fpath = os.path.join(downloads_dir, f)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                        
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Successfully uninstalled {tool_name}.")
        self.refresh_status()
        
    def install_all_missing(self):
        self.progress_label.setText("Preparing installation scan...")
        self.lock_ui_running()
        self.btn_install_all.setText("Pause")
        self.btn_install_all.setIcon(qta.icon("fa5s.pause", color=self.main_win.get_icon_color()))
        self.btn_cancel.setVisible(True)
        self.is_paused = False
        self.is_cancelling = False
        
        self.scan_worker = ScanWorker(self.main_win.env_root)
        
        def handle_install_all_scan(results):
            try:
                self.scan_worker.completed.disconnect()
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
            
        self.scan_worker.completed.connect(handle_install_all_scan)
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
        self.worker.completed.connect(self.on_worker_finished)
        self.worker.start()
        
    def on_worker_progress(self, message, percentage):
        if message:
            self.progress_label.setText(message)
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
        
    def on_worker_finished(self, tool_name, status, error_msg=""):
        if self.is_cancelling:
            self.unlock_ui_idle()
            self.progress_label.setText("Installation cancelled.")
            return
            
        if status == "paused":
            # Re-insert tool at the front of queue to allow resume
            self.install_queue.insert(0, tool_name)
            self.is_paused = True
            self.btn_install_all.setText("Resume")
            self.btn_install_all.setIcon(qta.icon("fa5s.play", color=self.main_win.get_icon_color()))
            self.btn_cancel.setVisible(True)
            self.progress_label.setText(f"Paused - {tool_name.upper()} download.")
            return
            
        if status == "failed":
            self.progress_label.setText(f"Installation failed for {tool_name.upper()}.")
            QMessageBox.critical(
                self, 
                "Installation Failed", 
                f"Failed to install {self.tool_display.get(tool_name, (tool_name, ''))[0]}.\n\nError Details:\n{error_msg}"
            )
            # If the user selected to download all missing and something failed, continue to next tool.
            if self.install_queue:
                self.process_install_queue()
            else:
                self.unlock_ui_idle()
            return
            
        # Success state
        if self.install_queue:
            self.process_install_queue()
        else:
            self.unlock_ui_idle()
            
    def get_url_version(self, tool_key):
        url = DOWNLOAD_URLS.get(tool_key, "")
        if not url:
            return None
        import re
        if tool_key == "git":
            match = re.search(r"Git-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key in ["php", "php83", "php84", "php85"]:
            match = re.search(r"php-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "nginx":
            match = re.search(r"nginx-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "apache":
            match = re.search(r"httpd-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "mysql":
            match = re.search(r"mariadb-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "node":
            match = re.search(r"node-v([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "phpmyadmin":
            match = re.search(r"phpMyAdmin-([0-9.]+)", url)
            return match.group(1) if match else None
        elif tool_key == "mailpit":
            match = re.search(r"v([0-9.]+)", url)
            return match.group(1) if match else None
        return None

    def is_version_older(self, current_ver, target_ver):
        try:
            import re
            def parse_version(v_str):
                cleaned = re.sub(r"[^\d.]", "", v_str).strip(".")
                return tuple(int(x) for x in cleaned.split(".") if x.isdigit())
            return parse_version(current_ver) < parse_version(target_ver)
        except Exception:
            return False

    def check_updates(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
        self.progress_label.setText("Scanning system for updates...")
        self.scan_worker = ScanWorker(self.main_win.env_root)
        
        def on_scan_updates_done(results):
            try:
                self.scan_worker.completed.disconnect()
            except Exception:
                pass
            self.on_scan_finished(results)
            self.perform_update_check(results)
            
        self.scan_worker.completed.connect(on_scan_updates_done)
        self.scan_worker.start()

    def perform_update_check(self, results):
        updates = []
        for key in self.tool_keys:
            if key in ["vcredist", "composer", "laravel"]:
                continue
            res = results.get(key)
            if res and res["installed"]:
                curr_ver = res["version"]
                target_ver = self.get_url_version(key)
                if curr_ver and target_ver and self.is_version_older(curr_ver, target_ver):
                    updates.append((key, curr_ver, target_ver))
                    
        if not updates:
            QMessageBox.information(self, "Check Updates", "All installed components are up to date.")
            self.progress_label.setText("No updates available.")
            return
            
        msg = "Updates are available for the following components:\n\n"
        for key, curr, target in updates:
            msg += f"• {self.tool_display[key][0]}: v{curr} → v{target}\n"
        msg += "\nWould you like to download and install these updates now?"
        
        reply = QMessageBox.question(
            self,
            "Updates Available",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.install_queue = [item[0] for item in updates]
            self.is_paused = False
            self.is_cancelling = False
            self.lock_ui_running()
            self.btn_cancel.setVisible(True)
            self.btn_install_all.setText("Pause")
            self.btn_install_all.setIcon(qta.icon("fa5s.pause", color=self.main_win.get_icon_color()))
            self.process_install_queue()

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

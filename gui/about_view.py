import os
import logging
import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QSize
import qtawesome as qta

logger = logging.getLogger(__name__)

class AboutView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Scrollable container for instructions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 10, 0)
        content_layout.setSpacing(15)
        
        # Header Info Card
        header_card = QFrame()
        header_card.setObjectName("tool_card") # Styling matches cards
        header_card.setFrameShape(QFrame.StyledPanel)
        header_layout = QVBoxLayout(header_card)
        header_layout.setSpacing(8)
        
        title_label = QLabel("Laravel Development Suite")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ef4444;")
        
        version_label = QLabel("Product Version: 1.0.1 (Stable Release)")
        version_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        
        desc_label = QLabel("A lightweight, lightning-fast developer stack manager for local PHP & Laravel development on Windows. Run Nginx, Apache, MariaDB, and PHP in isolation without heavy virtualization.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 12px; line-height: 18px;")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(version_label)
        header_layout.addWidget(desc_label)
        content_layout.addWidget(header_card)
        
        # Developer Profile Card
        dev_card = QFrame()
        dev_card.setObjectName("tool_card")
        dev_card.setFrameShape(QFrame.StyledPanel)
        dev_layout = QVBoxLayout(dev_card)
        dev_layout.setSpacing(8)
        
        dev_title = QLabel("Developer Profile")
        dev_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
        
        dev_name = QLabel("Developed By: Muhammad Umair")
        dev_name.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        dev_role = QLabel("Role: App & Web Developer")
        dev_role.setStyleSheet("font-size: 11px; color: #94a3b8;")
        
        dev_email = QLabel("Email: muhumair2022@ggmail.com")
        dev_email.setStyleSheet("font-size: 11px; color: #94a3b8;")
        
        self.btn_email = QPushButton(" Contact Developer")
        self.btn_email.setIconSize(QSize(12, 12))
        self.btn_email.setFixedWidth(150)
        self.btn_email.clicked.connect(lambda: webbrowser.open("mailto:muhumair2022@ggmail.com"))
        
        dev_layout.addWidget(dev_title)
        dev_layout.addWidget(dev_name)
        dev_layout.addWidget(dev_role)
        dev_layout.addWidget(dev_email)
        dev_layout.addWidget(self.btn_email)
        content_layout.addWidget(dev_card)
        
        # Instructions List Card
        inst_card = QFrame()
        inst_card.setObjectName("tool_card")
        inst_card.setFrameShape(QFrame.StyledPanel)
        inst_layout = QVBoxLayout(inst_card)
        inst_layout.setSpacing(10)
        
        inst_title = QLabel("How to Use Instructions")
        inst_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
        inst_layout.addWidget(inst_title)
        
        instructions = [
            ("1. Install Environment Stack", "Go to the 'Setup & Onboarding' tab and click 'Install All' or set up individual components (PHP, Composer, MySQL, Nginx, Node.js). Follow the installer prompts for Git and VC++ runtimes."),
            ("2. Configure System PATH", "If any component displays a warning icon showing 'No PATH', click the 'Add to PATH' button. Restart open command terminals or editor shells to inherit these changes globally."),
            ("3. Launch Services Dashboard", "Navigate to 'Services Control'. Click 'Start All' to boot the background servers. Standard local ports used: Nginx (8080), Apache (8081), MariaDB (3306), PHP-CGI (9000)."),
            ("4. Access PHPMyAdmin", "Once MariaDB and Nginx/Apache are active, click the 'Admin' button adjacent to MariaDB to open phpMyAdmin in your default browser."),
            ("5. Dynamic PHP Version Switcher", "On the 'PHP Version Control' tab, select an alternative runtime (like PHP 8.3) and click 'Apply Switch'. The stack automatically handles symlinks, configurations, and restarts active web servers for you."),
            ("6. Visual Theme Preference", "In the 'Logs & Settings' tab, customize your system base folders, check active log outputs in real-time, or toggle between Light Mode and Dark Mode.")
        ]
        
        for step, desc in instructions:
            step_lbl = QLabel(step)
            step_lbl.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 4px;")
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-left: 10px; padding-bottom: 4px;")
            inst_layout.addWidget(step_lbl)
            inst_layout.addWidget(desc_lbl)
            
        content_layout.addWidget(inst_card)
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        self.refresh_icons()
        
    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_email.setIcon(qta.icon("fa5s.envelope", color=color))

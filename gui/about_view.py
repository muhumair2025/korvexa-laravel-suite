import os
import logging
import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, QSize
import qtawesome as qta

logger = logging.getLogger(__name__)

from core.version import APP_VERSION

class AboutView(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_win = main_window
        self.init_ui()
        
    def init_ui(self):
        # Base Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 10, 0)
        content_layout.setSpacing(20)
        
        # Left Side Container
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)
        
        # Right Side Container
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # LEFT COLUMN 1: App Header Card
        header_card = QFrame()
        header_card.setObjectName("tool_card")
        header_card.setFrameShape(QFrame.StyledPanel)
        header_layout = QVBoxLayout(header_card)
        header_layout.setSpacing(10)
        header_layout.setContentsMargins(15, 15, 15, 15)
        
        # Brand Layout (Logo + Title)
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)
        
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(48, 48)
        # Load app logo png if exists, otherwise fallback to red laravel icon
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "app_logo.png")
        if os.path.exists(logo_path):
            from PySide6.QtGui import QPixmap
            self.logo_label.setPixmap(QPixmap(logo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_label.setPixmap(qta.icon("fa5b.laravel", color="#ef4444").pixmap(QSize(48, 48)))
        brand_layout.addWidget(self.logo_label)
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_label = QLabel("Laravel Development Suite")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ef4444;")
        version_label = QLabel(f"Product Version: {APP_VERSION} (Stable Release)")
        version_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(version_label)
        brand_layout.addLayout(title_vbox)
        brand_layout.addStretch()
        
        header_layout.addLayout(brand_layout)
        
        desc_label = QLabel(
            "A lightweight, lightning-fast developer stack manager for local PHP & Laravel development on Windows. "
            "Run Nginx, Apache, MariaDB, and PHP in isolation without heavy virtualization or Docker overhead."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 12px; line-height: 18px;")
        header_layout.addWidget(desc_label)
        
        left_layout.addWidget(header_card)
        
        # LEFT COLUMN 2: GitHub Support & Star Card
        support_card = QFrame()
        support_card.setObjectName("tool_card")
        support_card.setFrameShape(QFrame.StyledPanel)
        support_layout = QVBoxLayout(support_card)
        support_layout.setSpacing(12)
        support_layout.setContentsMargins(15, 15, 15, 15)
        
        support_title = QLabel("Support the Project")
        support_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
        
        support_desc = QLabel(
            "Laravel Development Suite is open-source. If you find this software useful, "
            "please star the repository on GitHub to show your love and support! ⭐"
        )
        support_desc.setWordWrap(True)
        support_desc.setStyleSheet("font-size: 12px; line-height: 16px;")
        
        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        
        self.btn_star = QPushButton(" Star on GitHub")
        self.btn_star.setFixedHeight(32)
        self.btn_star.setIconSize(QSize(14, 14))
        self.btn_star.clicked.connect(lambda: webbrowser.open("https://github.com/muhumair2025/korvexa-laravel-suite"))
        
        self.btn_github = QPushButton(" View Repository")
        self.btn_github.setFixedHeight(32)
        self.btn_github.setIconSize(QSize(14, 14))
        self.btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/muhumair2025/korvexa-laravel-suite"))
        
        btn_row.addWidget(self.btn_star, 1)
        btn_row.addWidget(self.btn_github, 1)
        
        support_layout.addWidget(support_title)
        support_layout.addWidget(support_desc)
        support_layout.addLayout(btn_row)
        
        left_layout.addWidget(support_card)
        
        # LEFT COLUMN 3: Developer Profile Card
        dev_card = QFrame()
        dev_card.setObjectName("tool_card")
        dev_card.setFrameShape(QFrame.StyledPanel)
        dev_layout = QVBoxLayout(dev_card)
        dev_layout.setSpacing(10)
        dev_layout.setContentsMargins(15, 15, 15, 15)
        
        dev_title = QLabel("Developer Profile")
        dev_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
        
        # Details grid
        dev_info_layout = QGridLayout()
        dev_info_layout.setSpacing(6)
        
        lbl_name_title = QLabel("Developed By:")
        lbl_name_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #94a3b8;")
        lbl_name_val = QLabel("Muhammad Umair")
        lbl_name_val.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        lbl_role_title = QLabel("Role:")
        lbl_role_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #94a3b8;")
        lbl_role_val = QLabel("App & Web Developer (Korvexa)")
        lbl_role_val.setStyleSheet("font-size: 11px;")
        
        lbl_email_title = QLabel("Email:")
        lbl_email_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #94a3b8;")
        lbl_email_val = QLabel("muhumair2022@ggmail.com")
        lbl_email_val.setStyleSheet("font-size: 11px; color: #3b82f6;") # Elegant link color
        
        dev_info_layout.addWidget(lbl_name_title, 0, 0)
        dev_info_layout.addWidget(lbl_name_val, 0, 1)
        dev_info_layout.addWidget(lbl_role_title, 1, 0)
        dev_info_layout.addWidget(lbl_role_val, 1, 1)
        dev_info_layout.addWidget(lbl_email_title, 2, 0)
        dev_info_layout.addWidget(lbl_email_val, 2, 1)
        
        self.btn_email = QPushButton(" Contact Developer")
        self.btn_email.setFixedHeight(32)
        self.btn_email.setIconSize(QSize(14, 14))
        self.btn_email.clicked.connect(lambda: webbrowser.open("mailto:muhumair2022@ggmail.com"))
        
        dev_layout.addWidget(dev_title)
        dev_layout.addLayout(dev_info_layout)
        dev_layout.addWidget(self.btn_email)
        
        left_layout.addWidget(dev_card)
        left_layout.addStretch()
        
        # RIGHT COLUMN: Instructions Card (How to Use)
        self.inst_card = QFrame()
        self.inst_card.setObjectName("tool_card")
        self.inst_card.setFrameShape(QFrame.StyledPanel)
        self.inst_layout = QVBoxLayout(self.inst_card)
        self.inst_layout.setSpacing(12)
        self.inst_layout.setContentsMargins(15, 15, 15, 15)
        
        inst_title = QLabel("Getting Started & How to Use")
        inst_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ef4444; border-bottom: 1px solid #ef4444; padding-bottom: 6px; margin-bottom: 4px;")
        self.inst_layout.addWidget(inst_title)
        
        self.instructions = [
            ("1. Install Environment Stack", "Go to the 'Setup & Onboarding' tab and click 'Install All' or set up individual components (PHP, Composer, MySQL, Nginx, Node.js). Follow the installer prompts for Git and VC++ runtimes."),
            ("2. Configure System PATH", "If any component displays a warning icon showing 'No PATH', click the 'Add to PATH' button. Restart open command terminals or editor shells to inherit these changes globally."),
            ("3. Launch Services Dashboard", "Navigate to 'Services Control'. Click 'Start All' to boot the background servers. Standard local ports used: Nginx (8080), Apache (8081), MariaDB (3306), PHP-CGI (9000)."),
            ("4. Access PHPMyAdmin", "Once MariaDB and Nginx/Apache are active, click the 'Admin' button adjacent to MariaDB to open phpMyAdmin in your default browser."),
            ("5. Dynamic PHP Version Switcher", "On the 'PHP Version Control' tab, select an alternative runtime (like PHP 8.3) and click 'Apply Switch'. The stack automatically handles symlinks, configurations, and restarts active web servers for you."),
            ("6. Visual Theme Preference", "In the 'Logs & Settings' tab, customize your system base folders, check active log outputs in real-time, or toggle between Light Mode and Dark Mode.")
        ]
        
        self.step_containers = []
        for step, desc in self.instructions:
            step_container = QFrame()
            step_container_layout = QVBoxLayout(step_container)
            step_container_layout.setContentsMargins(8, 8, 8, 8)
            step_container_layout.setSpacing(3)
            
            step_lbl = QLabel(step)
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            
            step_container_layout.addWidget(step_lbl)
            step_container_layout.addWidget(desc_lbl)
            self.inst_layout.addWidget(step_container)
            self.step_containers.append((step_container, step_lbl, desc_lbl))
            
        right_layout.addWidget(self.inst_card)
        right_layout.addStretch()
        
        # Add columns to content layout
        content_layout.addWidget(left_widget, 4)
        content_layout.addWidget(right_widget, 5)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        self.refresh_icons()
        
    def apply_button_styles(self):
        is_dark = getattr(self.main_win, 'theme', 'dark') == "dark"
        
        # Star Button Style (Laravel Red/Accent Primary color)
        self.btn_star.setStyleSheet(
            "QPushButton {"
            "  background-color: #ef4444;"
            "  color: white;"
            "  font-weight: bold;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 6px 12px;"
            "  font-size: 11px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #dc2626;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #b91c1c;"
            "}"
        )
        
        # GitHub Button Style (Slate secondary)
        github_bg = "#334155" if is_dark else "#e2e8f0"
        github_hover = "#475569" if is_dark else "#cbd5e1"
        github_pressed = "#1e293b" if is_dark else "#94a3b8"
        github_text = "white" if is_dark else "#1e293b"
        self.btn_github.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {github_bg};"
            f"  color: {github_text};"
            f"  font-weight: bold;"
            f"  border: none;"
            f"  border-radius: 4px;"
            f"  padding: 6px 12px;"
            f"  font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {github_hover};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {github_pressed};"
            f"}}"
        )
        
        # Email Button Style (Outline Red)
        email_hover_bg = "rgba(239, 68, 68, 0.15)"
        email_pressed_bg = "rgba(239, 68, 68, 0.25)"
        self.btn_email.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  color: #ef4444;"
            "  border: 1px solid #ef4444;"
            "  font-weight: bold;"
            "  border-radius: 4px;"
            "  padding: 6px 12px;"
            "  font-size: 11px;"
            "}"
            f"QPushButton:hover {{"
            f"  background-color: {email_hover_bg};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {email_pressed_bg};"
            f"}}"
        )
        
        # Update instruction steps styling
        step_bg = "rgba(30, 41, 59, 0.45)" if is_dark else "rgba(226, 232, 240, 0.55)"
        step_border = "1px solid #334155" if is_dark else "1px solid #cbd5e1"
        step_text_color = "#f1f5f9" if is_dark else "#1e293b"
        desc_text_color = "#94a3b8" if is_dark else "#475569"
        
        for container, title_lbl, desc_lbl in self.step_containers:
            container.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {step_bg};"
                f"  border-left: 4px solid #ef4444;"
                f"  border-top: {step_border};"
                f"  border-right: {step_border};"
                f"  border-bottom: {step_border};"
                f"  border-radius: 4px;"
                f"}}"
            )
            title_lbl.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {step_text_color}; background: transparent; border: none;")
            desc_lbl.setStyleSheet(f"color: {desc_text_color}; font-size: 11px; background: transparent; border: none;")

    def refresh_icons(self):
        color = self.main_win.get_icon_color()
        self.btn_star.setIcon(qta.icon("fa5s.star", color="#eab308"))
        self.btn_github.setIcon(qta.icon("fa5b.github", color=color))
        self.btn_email.setIcon(qta.icon("fa5s.envelope", color=color))
        self.apply_button_styles()

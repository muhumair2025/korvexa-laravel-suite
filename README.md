# 🚀 Laravel Suite

[![License](https://img.shields.io/badge/license-Custom-red.svg)](LICENSE.txt)
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](#)
[![PySide6](https://img.shields.io/badge/framework-PySide6-green.svg)](#)

A lightweight, lightning-fast developer stack manager for local **PHP & Laravel** development on Windows. Run Nginx, Apache, MariaDB, and PHP in isolation without the overhead of heavy virtualization tools like Docker or WSL2.

---

## 📥 Download Installer

You can download the compiled standalone installer for Windows directly from this repository:

* **[Download Laravel Suite Installer v1.0.0 (Recommended)](Installer/LaravelSuite-Setup-v1.0.0.exe)**
  *(Clicking this link will navigate to the file page on GitHub, where you can click the **Download raw file** button)*

> [!TIP]
> After launching your GitHub repository, you can configure a direct, raw-content download link:
> `https://github.com/<username>/<repo-name>/raw/main/Installer/LaravelSuite-Setup-v1.0.0.exe`

---

## ✨ Core Features

* **📦 One-Click Setup & Onboarding**: Automatically download, extract, and configure the entire environment stack (PHP, Composer, Git, Nginx, Apache, MariaDB/MySQL, and Node.js) with standard configuration patterns.
* **⚡ Services Dashboard**: Start, stop, and restart background servers (Nginx on port `8080`, Apache on `8081`, MariaDB/MySQL on `3306`, and PHP-CGI on `9000`). It features automatic port conflict detection and process self-healing.
* **🔄 PHP Version Switcher**: Seamlessly switch between active PHP runtimes (e.g., PHP 8.2 and PHP 8.3). The suite automatically updates local symlinks and restarts the active web server.
* **🌐 Sites & Domains (VHosts)**: Easily map custom local domains (e.g., `http://my-project.test`) to specific folders on your system without manually editing system hosts or configuration files.
* **🛠️ Laravel Projects Manager**: Initialize new Laravel projects or import existing ones, with quick shortcuts to trigger common `artisan` commands natively.
* **🗄️ Database Manager**: View and manage MySQL databases (create, delete, import, export, and manage users) with quick access to open **phpMyAdmin** in your default web browser.
* **🎨 UI Theme & Settings**: Customize paths, read background logs in real-time, and toggle between clean Light Mode and a modern Dark Mode theme (utilizing Slate/Modern design palette).

---

## 🛠️ Installation & Getting Started

### 1. Prerequisites (For Users)
- **OS**: Windows 10 / 11 (64-bit)
- **Administrator privileges** (Required for configuring Windows services, environment variables, hosts records, and directory junctions).

### 2. Run the Installer
1. Download **[LaravelSuite-Setup-v1.0.0.exe](Installer/LaravelSuite-Setup-v1.0.0.exe)**.
2. Run the installer (requires Windows UAC admin permission).
3. Follow the wizard steps to complete the installation.
4. Launch **Laravel Suite** from the Desktop or Start Menu.

---

## 💻 Developer Guide (Compiling & Building)

If you want to run or modify the application locally, follow these steps:

### 1. Requirements & Setup
Ensure you have Python 3.10+ installed on Windows. Then, install the project dependencies:

```bash
pip install -r requirements.txt
```

*Note: Dependencies are lightweight, primarily containing `PySide6-Essentials` and `qtawesome`.*

### 2. Running Locally
Run the main script to launch the application:

```bash
python main.py
```

### 3. Packaging/Compiling to Executable
We use **PyInstaller** to build the application into a standalone folder:

```bash
# Install PyInstaller if not already installed
pip install pyinstaller

# Build the executable using the provided spec file
pyinstaller LaravelSuite.spec
```

The output will be generated inside the `dist/LaravelSuite/` directory.

### 4. Creating the Setup Installer
The installation wizard is built using **Inno Setup**.
1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php).
2. Open the `installer.iss` script in Inno Setup compiler.
3. Click **Build** -> **Compile** (or run `ISCC installer.iss` from cmd).
4. The output setup file will be saved in the `Installer/` folder as `LaravelSuite-Setup-v1.0.0.exe`.

---

## 📁 Directory Structure

```text
├── assets/            # App icons, splash screens, logo assets
├── core/              # Business logic (detectors, path manager, installer, services control)
│   ├── detector.py
│   ├── installer.py
│   ├── path_manager.py
│   └── services.py
├── gui/               # PySide6 layout files, tabs, views
│   ├── main_window.py
│   ├── about_view.py
│   ├── database_view.py
│   ├── laravel_view.py
│   ├── onboarding_view.py
│   ├── services_view.py
│   ├── settings_view.py
│   ├── switcher_view.py
│   └── vhost_view.py
├── Installer/         # Holds the compiled Setup executable
│   └── LaravelSuite-Setup-v1.0.0.exe
├── main.py            # Main application entry point (manages UAC elevation & mutexes)
├── requirements.txt   # Python application dependencies
├── LaravelSuite.spec  # PyInstaller packaging configuration
├── installer.iss      # Inno Setup installation compiler script
└── LICENSE.txt        # License agreement
```

---

## 📄 License

This project is open source and distributed under the custom **Laravel Suite License**. See the [LICENSE.txt](LICENSE.txt) file for details.

Developed with ❤️ by **Muhammad Umair** (Korvexa).
- **Email**: [muhumair2022@ggmail.com](mailto:muhumair2022@ggmail.com)
- **Website**: [https://korvexa.app](https://korvexa.app)

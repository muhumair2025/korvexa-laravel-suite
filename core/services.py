import os
import socket
import subprocess
import ctypes
from ctypes import wintypes
import logging
import time

logger = logging.getLogger(__name__)

def get_pid_by_port(port):
    """Finds the PID of the process listening on a given local port using netstat."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                proto = parts[0].upper()
                local_addr = parts[1]
                state = parts[3].upper()
                
                # Check for TCP and LISTENING state
                if proto == 'TCP' and 'LISTENING' in state:
                    if local_addr.endswith(f":{port}") or local_addr.endswith(f".{port}"):
                        pid = parts[-1]
                        if pid.isdigit():
                            return int(pid)
    except Exception as e:
        logger.error(f"Error finding PID for port {port}: {e}")
    return None

# Windows Toolhelp structures for ctypes
TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_void_p),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_wchar * 260)
    ]

# Details for managing each service process
SERVICES = {
    "nginx": {
        "exe": "nginx.exe",
        "port": 8080,
        "process_name": "nginx.exe",
        "start_args": [],
        "stop_cmd": ["nginx.exe", "-s", "stop"],
        "sub_dir": "nginx"
    },
    "apache": {
        "exe": "bin/httpd.exe",
        "port": 8081,
        "process_name": "httpd.exe",
        "start_args": [],
        "stop_cmd": None,  # Taskkill is used directly
        "sub_dir": "apache"
    },
    "mysql": {
        "exe": "bin/mysqld.exe",
        "port": 3306,
        "process_name": "mysqld.exe",
        "start_args": [],
        "stop_cmd": ["bin/mysqladmin.exe", "-u", "root", "shutdown"],
        "sub_dir": "mariadb"
    },
    "php-cgi": {
        "exe": "php-cgi.exe",
        "port": 9000,
        "process_name": "php-cgi.exe",
        "start_args": ["-b", "127.0.0.1:9000"],
        "stop_cmd": None,  # Taskkill is used directly
        "sub_dir": "php/active"
    }
}

def load_custom_ports():
    from PySide6.QtCore import QSettings
    settings = QSettings("LaravelDevSuite", "Settings")
    
    nginx_port = int(settings.value("port_nginx", 8080))
    apache_port = int(settings.value("port_apache", 8081))
    mysql_port = int(settings.value("port_mysql", 3306))
    php_port = int(settings.value("port_php-cgi", 9000))
    
    SERVICES["nginx"]["port"] = nginx_port
    SERVICES["apache"]["port"] = apache_port
    SERVICES["mysql"]["port"] = mysql_port
    SERVICES["php-cgi"]["port"] = php_port
    SERVICES["php-cgi"]["start_args"] = ["-b", f"127.0.0.1:{php_port}"]

load_custom_ports()

def is_port_in_use(port):
    """Checks if a TCP port is bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', port)) == 0

def get_running_processes_ctypes():
    """Returns a set of lowercase running process executable names using Windows API."""
    process_names = set()
    kernel32 = ctypes.windll.kernel32
    hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnapshot == -1:
        return process_names
        
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        
        retval = kernel32.Process32FirstW(hSnapshot, ctypes.byref(pe))
        while retval:
            process_names.add(pe.szExeFile.lower())
            retval = kernel32.Process32NextW(hSnapshot, ctypes.byref(pe))
    except Exception as e:
        logger.error(f"Error in Toolhelp32 process snapshot: {e}")
    finally:
        kernel32.CloseHandle(hSnapshot)
        
    return process_names

def is_process_running(process_name):
    """Checks if a process name is active using native Windows snapshot API (no subprocesses)."""
    return process_name.lower() in get_running_processes_ctypes()

def get_service_status(name, env_root, running_processes=None):
    if name not in SERVICES:
        return "Unknown"
        
    srv = SERVICES[name]
    port_active = is_port_in_use(srv["port"])
    
    if running_processes is not None:
        proc_active = srv["process_name"].lower() in running_processes
    else:
        proc_active = is_process_running(srv["process_name"])
    
    if port_active or proc_active:
        return "Running"
    return "Stopped"

def start_service(name, env_root, log_dir):
    if name not in SERVICES:
        return False, "Unknown service"
        
    status = get_service_status(name, env_root)
    if status == "Running":
        return True, f"{name} is already running."
        
    srv = SERVICES[name]
    srv_dir = os.path.join(env_root, srv["sub_dir"])
    
    # Fallback pathing for mysql/mariadb directory names
    if name == "mysql" and not os.path.exists(srv_dir):
        srv_dir = os.path.join(env_root, "mysql")
        
    exe_path = os.path.join(srv_dir, srv["exe"])
    if not os.path.exists(exe_path):
        return False, f"Executable not found for {name} at {exe_path}."
        
    # Self-heal configurations on start to handle path movements or space issues
    try:
        if name == "apache":
            from core.installer import configure_apache
            php_active = os.path.join(env_root, "php", "active")
            configure_apache(srv_dir, os.path.join(env_root, "www"), php_active, port=SERVICES["apache"]["port"])
        elif name == "nginx":
            from core.installer import configure_nginx
            configure_nginx(
                srv_dir, 
                os.path.join(env_root, "www"), 
                os.path.join(env_root, "phpmyadmin"),
                port=SERVICES["nginx"]["port"],
                php_port=SERVICES["php-cgi"]["port"]
            )
        elif name == "mysql":
            from core.installer import configure_mysql
            configure_mysql(srv_dir, port=SERVICES["mysql"]["port"])
    except Exception as e:
        logger.warning(f"Self-heal configuration failed for {name}: {e}")
        
    # Check port conflicts and auto-resolve if possible
    if is_port_in_use(srv["port"]):
        pid = get_pid_by_port(srv["port"])
        if pid:
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(0.5)
            except Exception:
                pass
                
        if is_port_in_use(srv["port"]):
            return False, f"Port {srv['port']} is already in use by another application."
        
    # Prepare logs
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name}.log")
    
    try:
        f_log = open(log_file, "a")
        f_log.write(f"\n--- Starting {name} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        f_log.flush()
        
        # Configure subprocess startup flags to keep the command window hidden
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        cmd = [exe_path] + srv["start_args"]
        
        subprocess.Popen(
            cmd, 
            cwd=srv_dir,
            stdout=f_log,
            stderr=f_log,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Wait slightly for the thread binding to occur
        time.sleep(1.0)
        
        if get_service_status(name, env_root) == "Running":
            return True, f"{name} started successfully."
        else:
            # Try to test and auto-heal configuration errors
            healed, heal_msg = test_and_heal_config(name, srv_dir)
            if healed:
                logger.info(f"Auto-healed configuration: {heal_msg}. Retrying startup...")
                f_log.write(f"\n--- [Auto-Heal] {heal_msg}. Retrying startup... ---\n")
                f_log.flush()
                
                # Retry Popen
                subprocess.Popen(
                    cmd, 
                    cwd=srv_dir,
                    stdout=f_log,
                    stderr=f_log,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(1.0)
                if get_service_status(name, env_root) == "Running":
                    return True, f"{name} started successfully after auto-healing: {heal_msg}"
                    
            return False, f"Failed to start {name}. Please inspect logs in {log_file}."
            
    except Exception as e:
        logger.error(f"Error starting service {name}: {e}")
        return False, f"Error starting {name}: {e}"

def stop_service(name, env_root):
    if name not in SERVICES:
        return False, "Unknown service"
        
    status = get_service_status(name, env_root)
    if status == "Stopped":
        return True, f"{name} is already stopped."
        
    srv = SERVICES[name]
    srv_dir = os.path.join(env_root, srv["sub_dir"])
    if name == "mysql" and not os.path.exists(srv_dir):
        srv_dir = os.path.join(env_root, "mysql")
        
    # Try graceful shutdown script first
    if srv["stop_cmd"]:
        exe_name = srv["stop_cmd"][0]
        exe_path = os.path.join(srv_dir, exe_name)
        if os.path.exists(exe_path):
            cmd = [exe_path] + srv["stop_cmd"][1:]
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            try:
                subprocess.run(
                    cmd, 
                    cwd=srv_dir, 
                    startupinfo=startupinfo, 
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Graceful shutdown of {name} failed: {e}. Terminating process instead.")
                
    # 1. Direct PID taskkill based on port occupancy (highest reliability)
    try:
        pid = get_pid_by_port(srv["port"])
        if pid:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)], 
                capture_output=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(0.2)
    except Exception as e:
        logger.warning(f"Failed to stop {name} via port PID: {e}")

    # 2. Image name fallback taskkill
    if get_service_status(name, env_root) == "Running":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.run(
            ['taskkill', '/F', '/IM', srv["process_name"]], 
            capture_output=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
    # Poll for cleanup (up to 3s)
    for _ in range(6):
        time.sleep(0.5)
        port_free = not is_port_in_use(srv["port"])
        proc_gone = not is_process_running(srv["process_name"])
        if port_free and proc_gone:
            return True, f"{name} stopped successfully."
        if proc_gone:
            return True, f"{name} stopped successfully."
            
    # Final fallback check
    port_free = not is_port_in_use(srv["port"])
    proc_gone = not is_process_running(srv["process_name"])
    if port_free or proc_gone:
        return True, f"{name} stopped successfully."
    return False, f"Failed to stop {name}."

def test_and_heal_config(name, srv_dir):
    import re
    if name == "nginx":
        test_exe = os.path.join(srv_dir, "nginx.exe")
        if not os.path.exists(test_exe):
            return False, "Nginx executable not found"
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            [test_exe, "-t"],
            cwd=srv_dir,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = res.stderr or ""
        if "emerg" in output or "failed" in output:
            match = re.search(r'([A-Za-z]:[^"\'\s:\n]+\.conf)', output)
            if match:
                conf_file = match.group(1)
                if os.path.exists(conf_file) and "vhosts" in conf_file:
                    bak_file = conf_file + ".bak"
                    try:
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.rename(conf_file, bak_file)
                        return True, f"Disabled broken Nginx vhost: {os.path.basename(conf_file)}"
                    except Exception as e:
                        return False, f"Failed to rename configuration: {e}"
    elif name == "apache":
        test_exe = os.path.join(srv_dir, "bin", "httpd.exe")
        if not os.path.exists(test_exe):
            return False, "Apache httpd.exe not found"
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            [test_exe, "-t"],
            cwd=srv_dir,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = res.stdout + res.stderr
        if "Syntax error" in output or "AH" in output:
            match = re.search(r'([A-Za-z]:[^"\'\s:\n]+\.conf)', output)
            if match:
                conf_file = match.group(1)
                if os.path.exists(conf_file) and "vhosts" in conf_file:
                    bak_file = conf_file + ".bak"
                    try:
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.rename(conf_file, bak_file)
                        return True, f"Disabled broken Apache vhost: {os.path.basename(conf_file)}"
                    except Exception as e:
                        return False, f"Failed to rename configuration: {e}"
    return False, "No config issue detected or resolved."

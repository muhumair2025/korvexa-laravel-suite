import os
import shutil
import subprocess
import re
import logging

logger = logging.getLogger(__name__)

def run_command(cmd, shell=True):
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            timeout=3,
            shell=shell,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)

def get_php_version(exe_path=None):
    cmd = [exe_path, "-v"] if exe_path else ["php", "-v"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"PHP\s+([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_composer_version(exe_path=None):
    cmd = [exe_path, "--version"] if exe_path else ["composer", "--version"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"Composer\s+version\s+([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_mysql_version(exe_path=None):
    cmd = [exe_path, "--version"] if exe_path else ["mysql", "--version"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"Distrib\s+([0-9.]+)-MariaDB", output) or re.search(r"([0-9.]+)-MariaDB", output) or re.search(r"Ver\s+([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_nginx_version(exe_path=None):
    cmd = [exe_path, "-v"] if exe_path else ["nginx", "-v"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"nginx/([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_apache_version(exe_path=None):
    cmd = [exe_path, "-v"] if exe_path else ["httpd", "-v"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"Apache/([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_node_version(exe_path=None):
    cmd = [exe_path, "-v"] if exe_path else ["node", "-v"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"v([0-9.]+)", output)
    if match:
        return match.group(1)
    return None

def get_laravel_version(exe_path=None):
    cmd = [exe_path, "-V"] if exe_path else ["laravel", "-V"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"Installer\s+([0-9.]+)", output) or re.search(r"Laravel\s+Installer\s+([0-9.]+)", output)
    if match:
        return match.group(1)
    return "Detected"

def get_git_version(exe_path=None):
    cmd = [exe_path, "--version"] if exe_path else ["git", "--version"]
    code, stdout, stderr = run_command(cmd, shell=False if exe_path else True)
    output = stdout + stderr
    match = re.search(r"git\s+version\s+([0-9a-zA-Z.]+)", output)
    if match:
        return match.group(1)
    return "Detected"

def detect_tool(name, env_root=None):
    """Detects if a tool is installed globally (in PATH) or locally under env_root.
    
    Returns a dict with detection results:
        {
            "installed": bool,
            "global": bool,
            "in_path": bool,
            "path": str or None,
            "version": str
        }
    """
    if name == "vcredist":
        path = "C:\\Windows\\System32\\vcruntime140_1.dll"
        installed = os.path.exists(path)
        return {
            "installed": installed,
            "global": True,
            "in_path": True,
            "path": path if installed else None,
            "version": "14.29+" if installed else "Unknown"
        }

    # 1. Check globally in PATH (Apache executable name is httpd)
    global_name = "httpd" if name == "apache" else name
    global_path = shutil.which(global_name)
    is_global = global_path is not None
    
    # 2. Check local path based on environment root
    local_path = None
    local_version = None
    
    if env_root and os.path.exists(env_root):
        if name == "php":
            # PHP active junction link
            php_active = os.path.join(env_root, "php", "active", "php.exe")
            if os.path.exists(php_active):
                local_path = php_active
            else:
                # search for any php folder like env_root/php/php-8.x.x/php.exe
                php_dir = os.path.join(env_root, "php")
                if os.path.exists(php_dir):
                    for d in os.listdir(php_dir):
                        p = os.path.join(php_dir, d, "php.exe")
                        if os.path.exists(p) and d != "active":
                            local_path = p
                            break
        elif name == "composer":
            composer_bat = os.path.join(env_root, "composer", "composer.bat")
            composer_phar = os.path.join(env_root, "composer", "composer.phar")
            if os.path.exists(composer_bat) and os.path.exists(composer_phar):
                local_path = composer_bat
        elif name == "git":
            global_path = shutil.which("git")
            local_git = "C:\\Program Files\\Git\\cmd\\git.exe"
            path_found = global_path or (local_git if os.path.exists(local_git) else None)
            is_global = global_path is not None
        elif name == "laravel":
            global_path = shutil.which("laravel")
            appdata = os.environ.get("APPDATA", "")
            local_composer_laravel = os.path.join(appdata, "Composer", "vendor", "bin", "laravel.bat")
            path_found = global_path or (local_composer_laravel if os.path.exists(local_composer_laravel) else None)
            is_global = global_path is not None
        elif name == "mysql":
            mysql_exe = os.path.join(env_root, "mariadb", "bin", "mysql.exe")
            if os.path.exists(mysql_exe):
                local_path = mysql_exe
            else:
                mysql_exe = os.path.join(env_root, "mysql", "bin", "mysql.exe")
                if os.path.exists(mysql_exe):
                    local_path = mysql_exe
        elif name == "nginx":
            nginx_exe = os.path.join(env_root, "nginx", "nginx.exe")
            if os.path.exists(nginx_exe):
                local_path = nginx_exe
        elif name == "apache":
            apache_exe = os.path.join(env_root, "apache", "bin", "httpd.exe")
            nested_exe = os.path.join(env_root, "apache", "Apache24", "bin", "httpd.exe")
            if not os.path.exists(apache_exe) and os.path.exists(nested_exe):
                # Self-heal existing installations by lifting contents of Apache24 folder up
                try:
                    apache_dir = os.path.join(env_root, "apache")
                    nested_dir = os.path.join(apache_dir, "Apache24")
                    for item in os.listdir(nested_dir):
                        dest_item = os.path.join(apache_dir, item)
                        if os.path.exists(dest_item):
                            if os.path.isdir(dest_item):
                                shutil.rmtree(dest_item)
                            else:
                                os.remove(dest_item)
                        shutil.move(os.path.join(nested_dir, item), dest_item)
                    os.rmdir(nested_dir)
                except Exception:
                    pass
            if os.path.exists(apache_exe):
                local_path = apache_exe
            else:
                apache_exe = os.path.join(env_root, "httpd", "bin", "httpd.exe")
                if os.path.exists(apache_exe):
                    local_path = apache_exe
        elif name == "node":
            node_exe = os.path.join(env_root, "nodejs", "node.exe")
            if os.path.exists(node_exe):
                local_path = node_exe
        elif name == "phpmyadmin":
            pma_index = os.path.join(env_root, "phpmyadmin", "index.php")
            if os.path.exists(pma_index):
                local_path = pma_index
                local_version = "5.2.1"
    
    path_found = global_path or local_path
    version = None
    
    if path_found:
        if name == "php":
            version = get_php_version(path_found)
        elif name == "composer":
            version = get_composer_version(path_found)
        elif name == "git":
            version = get_git_version(path_found)
        elif name == "laravel":
            version = get_laravel_version(path_found)
        elif name == "mysql":
            version = get_mysql_version(path_found)
        elif name == "nginx":
            version = get_nginx_version(path_found)
        elif name == "apache":
            version = get_apache_version(path_found)
        elif name == "node":
            version = get_node_version(path_found)
        elif name == "phpmyadmin":
            version = local_version or "Detected"
            
    # Check if this tool is configured in system environment PATH
    in_path = False
    if path_found:
        user_path_env = os.environ.get("PATH", "")
        norm_found_dir = os.path.dirname(os.path.abspath(path_found))
        norm_paths = [os.path.abspath(p.strip()) for p in user_path_env.split(";") if p.strip()]
        if norm_found_dir in norm_paths:
            in_path = True
        elif is_global:
            in_path = True

    return {
        "installed": path_found is not None,
        "global": is_global,
        "in_path": in_path,
        "path": path_found,
        "version": version or "Unknown"
    }

def scan_all(env_root=None):
    try:
        from core.path_manager import reload_path_in_memory
        reload_path_in_memory()
    except Exception:
        pass
    tools = ["vcredist", "git", "php", "composer", "laravel", "mysql", "nginx", "apache", "node", "phpmyadmin"]
    results = {}
    for tool in tools:
        results[tool] = detect_tool(tool, env_root)
    return results

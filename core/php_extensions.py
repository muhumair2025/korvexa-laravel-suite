import os
import re
import logging

logger = logging.getLogger(__name__)

POPULAR_EXTENSIONS = {
    "curl": {"name": "cURL", "desc": "Client URL Library for secure HTTP requests.", "type": "extension"},
    "fileinfo": {"name": "Fileinfo", "desc": "Read file mime-types and details dynamically.", "type": "extension"},
    "gd": {"name": "GD Graphics", "desc": "Image processing, resizing, and manipulation library.", "type": "extension"},
    "intl": {"name": "Intl", "desc": "Internationalization support (highly recommended for Laravel).", "type": "extension"},
    "mbstring": {"name": "MBString", "desc": "Multi-byte string functions for non-ASCII charsets.", "type": "extension"},
    "openssl": {"name": "OpenSSL", "desc": "Secure cryptographic and SSL/TLS connections.", "type": "extension"},
    "pdo_mysql": {"name": "PDO MySQL", "desc": "MySQL/MariaDB storage database driver for PDO.", "type": "extension"},
    "sqlite3": {"name": "SQLite3", "desc": "Standalone SQLite database engine support.", "type": "extension"},
    "pdo_sqlite": {"name": "PDO SQLite", "desc": "SQLite database driver for PDO (great for unit tests).", "type": "extension"},
    "sodium": {"name": "Sodium", "desc": "Modern cryptographic operations and encryption.", "type": "extension"},
    "zip": {"name": "Zip", "desc": "Compress and extract zip archive files.", "type": "extension"},
    "xdebug": {"name": "Xdebug", "desc": "Advanced PHP code debugging and profiling tool.", "type": "zend_extension"},
    "redis": {"name": "Redis", "desc": "High-performance Redis cache and session storage client.", "type": "extension"},
    "imagick": {"name": "ImageMagick", "desc": "Advanced image conversion and parsing library.", "type": "extension"},
    "pgsql": {"name": "PostgreSQL", "desc": "PostgreSQL database core client driver.", "type": "extension"},
    "pdo_pgsql": {"name": "PDO PostgreSQL", "desc": "PostgreSQL database driver for PDO.", "type": "extension"},
    "opcache": {"name": "OPcache", "desc": "Zend OPcache byte-code caching for fast execution speeds.", "type": "zend_extension"},
    "bcmath": {"name": "BCMath", "desc": "Arbitrary precision mathematics calculator library.", "type": "extension"},
    "mongodb": {"name": "MongoDB", "desc": "MongoDB database client driver support.", "type": "extension"},
    "sqlsrv": {"name": "SQL Server", "desc": "Microsoft SQL Server database client driver.", "type": "extension"},
    "pdo_sqlsrv": {"name": "PDO SQL Server", "desc": "Microsoft SQL Server database driver for PDO.", "type": "extension"},
    "exif": {"name": "Exif", "desc": "Read and parse image header metadata tags.", "type": "extension"},
}

PHP_CONFIG_VARIABLES = {
    "memory_limit": {"name": "Memory Limit", "desc": "Maximum memory a script may consume (e.g. 128M, 256M, 512M).", "default": "128M"},
    "max_execution_time": {"name": "Execution Timeout", "desc": "Maximum execution time of a script in seconds (e.g. 30, 60, 120).", "default": "30"},
    "upload_max_filesize": {"name": "Max Upload Size", "desc": "Maximum allowed size for uploaded files (e.g. 2M, 10M, 100M).", "default": "2M"},
    "post_max_size": {"name": "Max Post Size", "desc": "Maximum size of POST data PHP will accept (should be >= Max Upload Size).", "default": "8M"},
    "session.gc_maxlifetime": {"name": "Session Timeout", "desc": "Seconds after which session data will be seen as garbage.", "default": "1440"},
}

def get_ext_dll_name(key):
    if key in ["xdebug", "opcache"]:
        return key
    return f"php_{key}.dll"

def is_extension_available(env_root, key):
    """
    Check if the extension DLL is present in the active PHP ext folder.
    """
    php_dir = os.path.join(env_root, "php", "active")
    ext_dir = os.path.join(php_dir, "ext")
    if not os.path.exists(ext_dir):
        return False
        
    if key in ["xdebug", "opcache"]:
        for item in os.listdir(ext_dir):
            if key in item.lower() and item.lower().endswith(".dll"):
                return True
        return False
        
    dll_name = get_ext_dll_name(key)
    return os.path.exists(os.path.join(ext_dir, dll_name))

def get_extension_states(php_ini_path):
    """
    Parses php.ini to find out which extensions are enabled or disabled.
    Returns: {extension_key: {"enabled": bool, "found": bool, "line_num": int, "type": str}}
    """
    states = {}
    for key in POPULAR_EXTENSIONS:
        states[key] = {"enabled": False, "found": False, "line_num": -1, "type": POPULAR_EXTENSIONS[key]["type"]}
        
    if not os.path.exists(php_ini_path):
        return states
        
    try:
        with open(php_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        pattern = r"^\s*(;)?\s*(extension|zend_extension)\s*=\s*[\"']?(php_)?([a-zA-Z0-9_-]+)(\.dll)?[\"']?\s*(;.*)?$"
        for idx, line in enumerate(lines):
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                is_commented = match.group(1) is not None
                ext_type = match.group(2).lower()
                key = match.group(4).lower()
                
                states[key] = {
                    "enabled": not is_commented,
                    "found": True,
                    "line_num": idx,
                    "type": ext_type
                }
    except Exception as e:
        logger.error(f"Error parsing php.ini extensions: {e}")
        
    return states

def set_extension_state(php_ini_path, key, enable):
    """
    Modifies php.ini to enable/disable an extension.
    Returns (success, message).
    """
    if not os.path.exists(php_ini_path):
        return False, "php.ini file not found."
        
    try:
        with open(php_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        states = get_extension_states(php_ini_path)
        state = states.get(key)
        meta = POPULAR_EXTENSIONS.get(key)
        
        ext_type = meta["type"] if meta else (state["type"] if state else "extension")
        
        if state and state["found"] and state["line_num"] >= 0:
            idx = state["line_num"]
            line = lines[idx]
            if enable:
                new_line = re.sub(r"^\s*;\s*", "", line)
                lines[idx] = new_line
            else:
                if not line.strip().startswith(";"):
                    lines[idx] = ";" + line
        else:
            directive = f"{ext_type}={key}\n"
            lines.append(f"\n; Added automatically by Laravel Dev Suite\n{directive}")
            
        with open(php_ini_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        action = "enabled" if enable else "disabled"
        return True, f"Extension '{key}' successfully {action}."
    except Exception as e:
        logger.error(f"Failed to update extension '{key}' state in php.ini: {e}")
        return False, str(e)

def get_config_variables(php_ini_path):
    """
    Parses php.ini to find the active values for PHP_CONFIG_VARIABLES.
    Returns: {config_key: str_value}
    """
    values = {key: meta["default"] for key, meta in PHP_CONFIG_VARIABLES.items()}
    if not os.path.exists(php_ini_path):
        return values
        
    try:
        with open(php_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        for line in lines:
            line_strip = line.strip()
            if not line_strip or line_strip.startswith(";"):
                continue
            for key in PHP_CONFIG_VARIABLES:
                pattern = r"^" + re.escape(key) + r"\s*=\s*(.*?)\s*(;.*)?$"
                match = re.match(pattern, line_strip, re.IGNORECASE)
                if match:
                    val = match.group(1).strip().strip('"').strip("'")
                    values[key] = val
    except Exception as e:
        logger.error(f"Error parsing php.ini config variables: {e}")
        
    return values

def set_config_variable(php_ini_path, key, value):
    """
    Modifies php.ini to set a configuration variable.
    Returns (success, message).
    """
    if not os.path.exists(php_ini_path):
        return False, "php.ini file not found."
        
    if key not in PHP_CONFIG_VARIABLES:
        return False, "Unsupported configuration key."
        
    try:
        with open(php_ini_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        found = False
        pattern = r"^\s*(;)?\s*(" + re.escape(key) + r")\s*=\s*(.*?)\s*(;.*)?$"
        
        for idx, line in enumerate(lines):
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                comment = match.group(4) or ""
                comment_str = f" {comment}" if comment else ""
                lines[idx] = f"{key} = {value}{comment_str}\n"
                found = True
                break
                
        if not found:
            lines.append(f"\n{key} = {value}\n")
            
        with open(php_ini_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        return True, f"Configuration '{key}' updated to '{value}' successfully."
    except Exception as e:
        logger.error(f"Failed to update config '{key}' in php.ini: {e}")
        return False, str(e)

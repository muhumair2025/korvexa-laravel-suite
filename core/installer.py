import os
import urllib.request
import zipfile
import shutil
import re
import subprocess
import logging
import time
import ssl

logger = logging.getLogger(__name__)

# Constants and official download links
DOWNLOAD_URLS = {
    "vcredist": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    "git": "https://github.com/git-for-windows/git/releases/download/v2.45.1.windows.1/Git-2.45.1-64-bit.exe",
    "php": "https://windows.php.net/downloads/releases/archives/php-8.2.20-Win32-vs16-x64.zip",
    "php83": "https://windows.php.net/downloads/releases/archives/php-8.3.8-Win32-vs16-x64.zip",
    "php84": "https://windows.php.net/downloads/releases/archives/php-8.4.3-Win32-vs17-x64.zip",
    "php85": "https://windows.php.net/downloads/releases/archives/php-8.5.1-Win32-vs17-x64.zip",
    "composer": "https://getcomposer.org/composer.phar",
    "laravel": "https://github.com/laravel/installer",
    "nginx": "https://nginx.org/download/nginx-1.24.0.zip",
    "apache": "https://www.apachelounge.com/download/VS17/binaries/httpd-2.4.66-251206-win64-VS17.zip",
    "mysql": "https://archive.mariadb.org/mariadb-11.2.2/winx64-packages/mariadb-11.2.2-winx64.zip",
    "node": "https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip",
    "phpmyadmin": "https://files.phpmyadmin.net/phpMyAdmin/5.2.1/phpMyAdmin-5.2.1-all-languages.zip",
    "mailpit": "https://github.com/axllent/mailpit/releases/download/v1.20.1/mailpit-windows-amd64.zip"
}

def download_file(url, dest_path, progress_callback=None):
    """Downloads a file with support for resuming (HTTP Range) and retries."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # Try using default system SSL context first, fall back to unverified if verification fails
    try:
        context = ssl.create_default_context()
    except Exception:
        context = ssl._create_unverified_context()
        
    initial_bytes = 0
    if os.path.exists(dest_path):
        initial_bytes = os.path.getsize(dest_path)
        
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            if initial_bytes > 0:
                req.add_header('Range', f'bytes={initial_bytes}-')
                
            try:
                response = urllib.request.urlopen(req, timeout=30, context=context)
            except urllib.error.URLError as ue:
                # Fall back to unverified context if certificate verification failed
                if isinstance(ue.reason, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(ue.reason):
                    logger.warning("SSL verification failed. Retrying download with unverified SSL context...")
                    unverified_context = ssl._create_unverified_context()
                    response = urllib.request.urlopen(req, timeout=30, context=unverified_context)
                else:
                    raise ue
            except urllib.error.HTTPError as he:
                if he.code in [416, 400]:
                    initial_bytes = 0
                    req = urllib.request.Request(
                        url, 
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    )
                    try:
                        response = urllib.request.urlopen(req, timeout=30, context=context)
                    except urllib.error.URLError as ue:
                        if isinstance(ue.reason, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(ue.reason):
                            unverified_context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(req, timeout=30, context=unverified_context)
                        else:
                            raise ue
                else:
                    raise he
                    
            with response:
                status = response.status if hasattr(response, 'status') else response.code
                
                if status == 206:
                    mode = 'ab'
                    content_range = response.headers.get('Content-Range', '')
                    total_size = initial_bytes
                    if content_range:
                        match = re.search(r'/(\d+)', content_range)
                        if match:
                            total_size = int(match.group(1))
                    if not total_size or total_size <= initial_bytes:
                        cl = response.headers.get('content-length')
                        total_size = initial_bytes + (int(cl) if cl else 0)
                else:
                    mode = 'wb'
                    initial_bytes = 0
                    cl = response.headers.get('content-length')
                    total_size = int(cl) if cl else 0
                    
                downloaded = initial_bytes
                block_size = 1024 * 32  # 32KB chunks
                
                with open(dest_path, mode) as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            # The callback can raise an exception (like Pause) which we let propagate
                            progress_callback(percent, downloaded, total_size)
            return True
        except Exception as e:
            # If the exception is a pause request, do not retry, just propagate it
            if 'paused' in str(e).lower() or 'download paused' in str(e).lower():
                raise e
            if attempt == max_retries:
                raise e
            logger.warning(f"Download attempt {attempt} failed: {e}. Retrying in 2 seconds...")
            time.sleep(2)

def extract_and_lift(zip_path, target_dir):
    """Extracts zip to target_dir. If the zip contains a single parent folder,
    lifts its contents up to target_dir directly to avoid nested directories.
    """
    temp_extract = target_dir + "_temp"
    if os.path.exists(temp_extract):
        shutil.rmtree(temp_extract)
        
    os.makedirs(temp_extract, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    items = os.listdir(temp_extract)
    os.makedirs(target_dir, exist_ok=True)
    
    # Check if this zip has a parent "Apache24" directory alongside readmes (Apache Lounge pattern)
    apache24_path = os.path.join(temp_extract, "Apache24")
    has_apache24 = os.path.exists(apache24_path) and os.path.isdir(apache24_path)
    
    if has_apache24 or (len(items) == 1 and os.path.isdir(os.path.join(temp_extract, items[0]))):
        sub_dir = apache24_path if has_apache24 else os.path.join(temp_extract, items[0])
        for item in os.listdir(sub_dir):
            dest = os.path.join(target_dir, item)
            if os.path.exists(dest):
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                else:
                    os.remove(dest)
            shutil.move(os.path.join(sub_dir, item), dest)
    else:
        for item in items:
            dest = os.path.join(target_dir, item)
            if os.path.exists(dest):
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                else:
                    os.remove(dest)
            shutil.move(os.path.join(temp_extract, item), dest)
            
    shutil.rmtree(temp_extract)
    return True

def configure_php(php_dir):
    """Generates php.ini from php.ini-development with standard extensions for Laravel."""
    ini_dev = os.path.join(php_dir, "php.ini-development")
    ini_prod = os.path.join(php_dir, "php.ini-production")
    ini_path = os.path.join(php_dir, "php.ini")
    
    src = ini_dev if os.path.exists(ini_dev) else ini_prod
    if not os.path.exists(src):
        return False, "Template php.ini not found"
        
    with open(src, "r") as f:
        content = f.read()
        
    # 1. Enable extension_dir
    content = re.sub(r';\s*extension_dir\s*=\s*"ext"', 'extension_dir = "ext"', content)
    
    # 2. Enable common extensions
    extensions = [
        "curl", "fileinfo", "gd", "mbstring", "mysqli", 
        "openssl", "pdo_mysql", "zip"
    ]
    for ext in extensions:
        # Match both ';' prefix and check if already uncommented
        content = re.sub(r';\s*extension\s*=\s*' + ext + r'\b', 'extension=' + ext, content)
        
    # 3. Increase limits for development convenience
    content = re.sub(r'upload_max_filesize\s*=\s*\w+', 'upload_max_filesize = 100M', content)
    content = re.sub(r'post_max_size\s*=\s*\w+', 'post_max_size = 100M', content)
    content = re.sub(r'memory_limit\s*=\s*\w+', 'memory_limit = 512M', content)
    
    # 4. CGI fix pathinfo for Nginx FastCGI
    content = re.sub(r';\s*cgi\.fix_pathinfo\s*=\s*1', 'cgi.fix_pathinfo=1', content)
    
    with open(ini_path, "w") as f:
        f.write(content)
        
    return True, "php.ini configured successfully."

def configure_nginx(nginx_dir, html_root, pma_root, port=8080, php_port=9000):
    """Configures nginx.conf to support PHP FastCGI and phpMyAdmin on custom ports."""
    conf_path = os.path.join(nginx_dir, "conf", "nginx.conf")
    
    # Normalize paths to use forward slashes for Nginx compatibility
    html_root_fwd = os.path.abspath(html_root).replace("\\", "/")
    pma_root_fwd = os.path.abspath(pma_root).replace("\\", "/")
    vhosts_dir_fwd = os.path.join(nginx_dir, "conf", "vhosts").replace("\\", "/")
    
    nginx_conf_content = f"""
worker_processes  1;

events {{
    worker_connections  1024;
}}

http {{
    include       mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;

    # PHP FastCGI Server pooling
    upstream php-handler {{
        server 127.0.0.1:{php_port};
    }}

    server {{
        listen       {port};
        server_name  localhost;
        root         "{html_root_fwd}";
        index        index.php index.html index.htm;

        # Disable access logs for faster local execution
        access_log off;

        # Laravel routing fallback
        location / {{
            try_files $uri $uri/ /index.php?$query_string;
        }}

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {{
            root   html;
        }}

        # Process PHP requests
        location ~ \\.php$ {{
            fastcgi_pass   php-handler;
            fastcgi_index  index.php;
            fastcgi_param  SCRIPT_FILENAME  $document_root$fastcgi_script_name;
            include        fastcgi_params;
        }}

        # phpMyAdmin subfolder mapping
        location /phpmyadmin {{
            alias "{pma_root_fwd}/";
            index index.php index.html index.htm;
            
            location ~ \\.php$ {{
                fastcgi_pass   php-handler;
                fastcgi_index  index.php;
                fastcgi_param  SCRIPT_FILENAME  $request_filename;
                include        fastcgi_params;
            }}
        }}
    }}
    
    # Include custom virtual hosts config files
    include "{vhosts_dir_fwd}/*.conf";
}}
"""
    os.makedirs(os.path.dirname(conf_path), exist_ok=True)
    with open(conf_path, "w") as f:
        f.write(nginx_conf_content)
    return True, "nginx.conf configured successfully."

def configure_mysql(mariadb_dir, port=3306):
    """Configures my.ini and initializes MariaDB databases with custom port."""
    conf_path = os.path.join(mariadb_dir, "my.ini")
    db_dir = os.path.join(mariadb_dir, "data")
    mariadb_root_fwd = os.path.abspath(mariadb_dir).replace("\\", "/")
    
    my_ini_content = f"""
[mysqld]
port = {port}
socket = mysql
basedir = "{mariadb_root_fwd}"
datadir = "{mariadb_root_fwd}/data"
bind-address = 127.0.0.1
max_connections = 100
character-set-server = utf8mb4
collation-server = utf8mb4_general_ci
default-storage-engine = InnoDB
innodb_file_per_table = 1

[mysql]
default-character-set = utf8mb4
"""
    with open(conf_path, "w") as f:
        f.write(my_ini_content)
        
    # Check if database is already initialized
    if not os.path.exists(os.path.join(db_dir, "mysql")):
        # We need to run mariadb-install-db.exe
        install_db_exe = os.path.join(mariadb_dir, "bin", "mariadb-install-db.exe")
        if not os.path.exists(install_db_exe):
            install_db_exe = os.path.join(mariadb_dir, "bin", "mysql_install_db.exe")
            
        if os.path.exists(install_db_exe):
            cmd = [install_db_exe, f"--datadir={db_dir}", "--service="]
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    cmd, 
                    shell=False, 
                    capture_output=True, 
                    text=True, 
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                return True, "MariaDB database initialized successfully."
            except Exception as e:
                return False, f"Failed to initialize MariaDB: {e}"
        return False, "MariaDB installation files database installer not found."
    return True, "MariaDB database already initialized."

def configure_apache(apache_dir, html_root, php_active_dir, port=8081):
    """Configures Apache httpd.conf to run on custom port and execute PHP via CGI."""
    conf_path = os.path.join(apache_dir, "conf", "httpd.conf")
    if not os.path.exists(conf_path):
        return False, "Apache httpd.conf not found."
        
    with open(conf_path, "r") as f:
        content = f.read()
        
    # 1. Update ServerRoot (Define SRVROOT "/Apache24" or ServerRoot "/Apache24")
    apache_dir_fwd = os.path.abspath(apache_dir).replace("\\", "/")
    content = re.sub(r'Define\s+SRVROOT\s+"[^"]+"', f'Define SRVROOT "{apache_dir_fwd}"', content)
    content = re.sub(r'ServerRoot\s+"[^"]+"', f'ServerRoot "{apache_dir_fwd}"', content)
    
    # 2. Change Port to custom port
    content = re.sub(r'Listen\s+\d+', f'Listen {port}', content)
    
    # 3. Change ServerName
    content = re.sub(r'#?ServerName\s+localhost:\d+', f'ServerName localhost:{port}', content)
    content = re.sub(r'#ServerName\s+www\.example\.com:80', f'ServerName localhost:{port}', content)
    
    # 4. Update DocumentRoot
    html_root_fwd = os.path.abspath(html_root).replace("\\", "/")
    content = re.sub(r'DocumentRoot\s+"[^"]+"', f'DocumentRoot "{html_root_fwd}"', content)
    content = content.replace('<Directory "${SRVROOT}/htdocs">', f'<Directory "{html_root_fwd}">')
    
    # 5. Enable Actions and rewrite modules
    content = re.sub(r'#\s*LoadModule\s+actions_module\b', 'LoadModule actions_module', content)
    content = re.sub(r'#\s*LoadModule\s+rewrite_module\b', 'LoadModule rewrite_module', content)
    
    # 6. Append PHP CGI configurations
    php_active_fwd = os.path.abspath(php_active_dir).replace("\\", "/")
    php_conf = f"""
# PHP Configuration by Laravel Env Tool
ScriptAlias /php/ "{php_active_fwd}/"
Action application/x-httpd-php "/php/php-cgi.exe"
AddHandler application/x-httpd-php .php

<Directory "{php_active_fwd}">
    AllowOverride None
    Options None
    Require all granted
</Directory>
"""
    if "application/x-httpd-php" not in content:
        content += php_conf
        
    # Append custom virtual hosts configuration loader
    if "conf/vhosts/*.conf" not in content:
        content += "\n# Include custom virtual hosts\nInclude conf/vhosts/*.conf\n"
        
    with open(conf_path, "w") as f:
        f.write(content)
        
    return True, "Apache configured successfully."

def create_junction(src_dir, junction_path):
    """Creates a Windows directory junction from junction_path to src_dir."""
    if os.path.exists(junction_path) or os.path.islink(junction_path):
        try:
            # os.rmdir works for directory junctions on Windows
            os.rmdir(junction_path)
        except OSError:
            try:
                os.remove(junction_path)
            except OSError:
                # Fallback to rmdir command
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    ["cmd.exe", "/c", "rmdir", junction_path], 
                    shell=False,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
    # Create the folder container if needed
    os.makedirs(os.path.dirname(junction_path), exist_ok=True)
    
    # Execute mklink /j
    cmd = ["cmd.exe", "/c", "mklink", "/j", junction_path, src_dir]
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    res = subprocess.run(
        cmd, 
        shell=False, 
        capture_output=True, 
        text=True,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    return res.returncode == 0

import os
import shutil
import urllib.request
import subprocess
import logging

logger = logging.getLogger(__name__)

MKCERT_URL = "https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe"

def find_openssl(env_root):
    locations = [
        os.path.join(env_root, "apache", "bin", "openssl.exe"),
        os.path.join(env_root, "mysql", "bin", "openssl.exe"),
        os.path.join(env_root, "mariadb", "bin", "openssl.exe"),
        shutil.which("openssl")
    ]
    for loc in locations:
        if loc and os.path.exists(loc):
            return loc
    return None

def download_mkcert(bin_dir):
    os.makedirs(bin_dir, exist_ok=True)
    mkcert_path = os.path.join(bin_dir, "mkcert.exe")
    if os.path.exists(mkcert_path):
        return mkcert_path
        
    logger.info(f"Downloading mkcert from {MKCERT_URL}...")
    try:
        req = urllib.request.Request(
            MKCERT_URL,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(mkcert_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        logger.info("mkcert downloaded successfully.")
        return mkcert_path
    except Exception as e:
        logger.error(f"Failed to download mkcert: {e}")
        return None

def run_cmd_hidden(cmd):
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        return False, "", str(e)

def provision_certificate(domain, env_root):
    """
    Creates local SSL certificate for domain.
    Returns (cert_path, key_path, method_used)
    """
    certs_dir = os.path.join(env_root, "certs")
    os.makedirs(certs_dir, exist_ok=True)
    
    cert_path = os.path.join(certs_dir, f"{domain}.pem").replace("\\", "/")
    key_path = os.path.join(certs_dir, f"{domain}-key.pem").replace("\\", "/")
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path, "cache"
        
    mkcert_exe = shutil.which("mkcert")
    if not mkcert_exe:
        bin_dir = os.path.join(env_root, "bin")
        mkcert_exe = os.path.join(bin_dir, "mkcert.exe")
        if not os.path.exists(mkcert_exe):
            downloaded = download_mkcert(bin_dir)
            if not downloaded:
                mkcert_exe = None
                
    if mkcert_exe:
        # First ensure Root CA install
        run_cmd_hidden([mkcert_exe, "-install"])
        
        cmd = [
            mkcert_exe,
            "-cert-file", cert_path,
            "-key-file", key_path,
            domain
        ]
        success, stdout, stderr = run_cmd_hidden(cmd)
        if success and os.path.exists(cert_path):
            return cert_path, key_path, "mkcert"
            
    openssl_exe = find_openssl(env_root)
    if openssl_exe:
        cmd = [
            openssl_exe, "req", "-x509", "-nodes", "-days", "3650",
            "-newkey", "rsa:2048",
            "-keyout", key_path,
            "-out", cert_path,
            "-subj", f"/CN={domain}"
        ]
        success, stdout, stderr = run_cmd_hidden(cmd)
        if success and os.path.exists(cert_path):
            return cert_path, key_path, "openssl"
            
    raise Exception("Failed to generate SSL certificate: neither mkcert nor openssl could be executed.")

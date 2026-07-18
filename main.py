import sys
import logging
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

global_app_mutex = None

def get_other_script_pids():
    import subprocess
    import os
    pids = []
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        res = subprocess.run(
            ['wmic', 'process', 'where', "name='python.exe' or name='pythonw.exe'", 'get', 'CommandLine,ProcessId'],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        my_pid = os.getpid()
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("commandline"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    pid = int(parts[-1])
                    cmdline = " ".join(parts[:-1])
                    if pid != my_pid and "main.py" in cmdline:
                        pids.append(pid)
                except ValueError:
                    pass
    except Exception:
        pass
    return pids

def get_other_compiled_pids():
    import ctypes
    from ctypes import wintypes
    import os
    
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
        
    pids = []
    my_pid = os.getpid()
    kernel32 = ctypes.windll.kernel32
    hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnapshot == -1:
        return pids
        
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        retval = kernel32.Process32FirstW(hSnapshot, ctypes.byref(pe))
        while retval:
            exe_name = pe.szExeFile.lower()
            if exe_name == "laravelsuite.exe" and pe.th32ProcessID != my_pid:
                pids.append(pe.th32ProcessID)
            retval = kernel32.Process32NextW(hSnapshot, ctypes.byref(pe))
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(hSnapshot)
    return pids

def kill_other_instances():
    import sys
    import subprocess
    
    is_compiled = hasattr(sys, 'frozen')
    pids = get_other_compiled_pids() if is_compiled else get_other_script_pids()
    
    if not pids:
        return False
        
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    
    # Kill the other application processes
    for pid in pids:
        try:
            subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
            
    # Forcefully stop running servers to start completely fresh
    for proc in ["nginx.exe", "httpd.exe", "mysqld.exe", "php-cgi.exe"]:
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', proc],
                capture_output=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
            
    return True

def main():
    import ctypes
    import sys
    global global_app_mutex
    
    # Enforce Single Instance Application Check on Windows
    try:
        ERROR_ALREADY_EXISTS = 183
        ERROR_ACCESS_DENIED = 5
        mutex_name = "Local\\LaravelDevSuiteSingleInstanceMutex"
        global_app_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        
        if last_error in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED) or (global_app_mutex == 0 and last_error != 0):
            # Release current handle if any
            if global_app_mutex:
                ctypes.windll.kernel32.CloseHandle(global_app_mutex)
                global_app_mutex = None
                
            # Attempt to kill other hung instances and their services
            killed_any = kill_other_instances()
            if killed_any:
                import time
                time.sleep(0.5)
                
                # Re-try acquiring mutex
                global_app_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
                last_error = ctypes.windll.kernel32.GetLastError()
                
                # If successfully acquired mutex now, we can continue to launch fresh
                if last_error == 0 and global_app_mutex != 0:
                    pass
                else:
                    # Still cannot acquire, restore window of whatever is left and exit
                    hwnd = ctypes.windll.user32.FindWindowW(None, "Laravel Development Suite")
                    if hwnd:
                        ctypes.windll.user32.ShowWindow(hwnd, 5)
                        ctypes.windll.user32.ShowWindow(hwnd, 9)
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                    sys.exit(0)
            else:
                # No other instances found or couldn't kill, restore existing window and exit
                hwnd = ctypes.windll.user32.FindWindowW(None, "Laravel Development Suite")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 5)
                    ctypes.windll.user32.ShowWindow(hwnd, 9)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                sys.exit(0)
    except Exception:
        pass
    
    # Check if running as administrator on Windows
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False
        
    if not is_admin:
        # Request Windows UAC elevation
        try:
            is_compiled = hasattr(sys, 'frozen')
            if is_compiled:
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, 
                    "runas", 
                    sys.executable, 
                    " ".join([f'"{arg}"' for arg in sys.argv[1:]]), 
                    None, 
                    1
                )
            else:
                script = sys.argv[0]
                args = f'"{script}" ' + " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, 
                    "runas", 
                    sys.executable, 
                    args, 
                    None, 
                    1
                )
            if ret > 32:
                sys.exit(0)
            else:
                # User cancelled UAC prompt
                sys.exit(1)
        except Exception as e:
            print(f"UAC Elevation request failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Setup standard logger mapping stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Force Windows Taskbar to show the custom window icon instead of default Python logo
    try:
        import ctypes
        myappid = 'muhammadumair.laraveldevsuite.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    # Initialize Application
    app = QApplication(sys.argv)
    
    # Create Main Application Window
    window = MainWindow()
    window.show()
    
    # Run the Qt Event Loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

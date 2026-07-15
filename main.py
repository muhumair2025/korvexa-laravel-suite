import sys
import logging
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

global_app_mutex = None

def main():
    import ctypes
    import sys
    global global_app_mutex
    
    # Enforce Single Instance Application Check on Windows
    try:
        ERROR_ALREADY_EXISTS = 183
        mutex_name = "Local\\LaravelDevSuiteSingleInstanceMutex"
        global_app_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(global_app_mutex)
            global_app_mutex = None
            
            # Find and restore the existing window
            hwnd = ctypes.windll.user32.FindWindowW(None, "Laravel Development Suite")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW = 5
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
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

import os
import winreg
import ctypes
import logging

logger = logging.getLogger(__name__)

def get_user_path():
    """Reads the User PATH from the Windows registry (HKCU\\Environment)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, 'Path')
            return val
        except FileNotFoundError:
            return ""
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Error reading user PATH from registry: {e}")
        return ""

def reload_path_in_memory():
    """Reloads User and System PATH values from Registry directly into os.environ['PATH']."""
    user_path = ""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ)
        try:
            user_path, _ = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass
        
    system_path = ""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 0, winreg.KEY_READ)
        try:
            system_path, _ = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass
        
    combined_paths = []
    if system_path:
        combined_paths.extend(p.strip() for p in system_path.split(';') if p.strip())
    if user_path:
        combined_paths.extend(p.strip() for p in user_path.split(';') if p.strip())
        
    os.environ["PATH"] = ';'.join(combined_paths)

def update_user_path(paths_to_add):
    """Appends unique paths to the User PATH in HKCU\\Environment and broadcasts the change.
    
    Returns:
        (bool, str): A tuple of (changed_status, message)
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_ALL_ACCESS)
    except Exception as e:
        logger.error(f"Error opening user registry key: {e}")
        return False, f"Registry access failed: {e}"
        
    try:
        try:
            current_path, _ = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            current_path = ""
            
        path_list = [p.strip() for p in current_path.split(';') if p.strip()]
        
        changed = False
        added_paths = []
        for path in paths_to_add:
            norm_path = os.path.abspath(path)
            if norm_path not in path_list:
                path_list.append(norm_path)
                added_paths.append(norm_path)
                changed = True
                
        if changed:
            new_path = ';'.join(path_list)
            winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
            
            # Broadcast WM_SETTINGCHANGE
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(
                HWND_BROADCAST, 
                WM_SETTINGCHANGE, 
                0, 
                "Environment"
            )
            reload_path_in_memory()
            msg = f"Added to PATH: {', '.join(added_paths)}. Please restart terminals or IDEs to apply changes."
            logger.info(msg)
            return True, msg
        else:
            return False, "Paths are already configured in PATH."
    except Exception as e:
        logger.error(f"Error updating User PATH in registry: {e}")
        return False, f"Failed to update PATH: {e}"
    finally:
        winreg.CloseKey(key)

def remove_from_user_path(paths_to_remove):
    """Removes specified paths from the User PATH in HKCU\\Environment."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_ALL_ACCESS)
    except Exception as e:
        return False, f"Registry access failed: {e}"
        
    try:
        try:
            current_path, _ = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            return False, "PATH is empty."
            
        path_list = [p.strip() for p in current_path.split(';') if p.strip()]
        
        changed = False
        removed_paths = []
        for path in paths_to_remove:
            norm_path = os.path.abspath(path)
            if norm_path in path_list:
                path_list.remove(norm_path)
                removed_paths.append(norm_path)
                changed = True
                
        if changed:
            new_path = ';'.join(path_list)
            winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
            
            # Broadcast change
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
            reload_path_in_memory()
            return True, f"Removed from PATH: {', '.join(removed_paths)}."
        return False, "Paths were not present in PATH."
    except Exception as e:
        return False, f"Failed to update PATH: {e}"
    finally:
        winreg.CloseKey(key)

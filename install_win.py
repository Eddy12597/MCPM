import subprocess
import shutil
from pathlib import Path
import winreg
import os
import ctypes

subprocess.run(["pyinstaller", "--onefile", "main.py"])


key = winreg.OpenKey(
    winreg.HKEY_CURRENT_USER, 
    "Environment", 
    0, 
    winreg.KEY_ALL_ACCESS
)

try:
    current_path, _ = winreg.QueryValueEx(key, "PATH")
except WindowsError:
    current_path = ""
    
directory = Path(__name__).parent / "dist"
if directory not in current_path.split(os.pathsep):
    new_path = current_path + os.pathsep + str(directory) if current_path else str(directory)
    winreg.SetValueEx(key, "PATH", False, winreg.REG_EXPAND_SZ, str(new_path))
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, 0)
    

winreg.CloseKey(key)

shutil.move(Path(__name__).parent / "dist" / "main.exe", Path(__name__).parent / "dist" / "mcpm.exe")
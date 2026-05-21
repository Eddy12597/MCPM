import subprocess
import shutil
from pathlib import Path

subprocess.run(["pyinstaller", "--onefile", "main.py"])
shutil.move(Path(__name__).parent / "dist" / "main.exe", Path(__name__).parent / "dist" / "mcpm.exe")
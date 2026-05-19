import subprocess
import shutil
subprocess.run(["pyinstaller", "--onefile", "main.py"])
shutil.move("./dist/main.exe", "./dist/mcpm.exe")
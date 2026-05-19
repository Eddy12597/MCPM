import os
from pathlib import Path
from dataclasses import dataclass
import shutil
import time

@dataclass
class _MoveAction:
    _from: Path | str
    _to: Path | str
    
    def __iter__(self):
        yield self
class FileMover:
    def __init__(self, home_dir: Path | str | None):
        if home_dir is None:
            raise RuntimeError("home_dir not properly configed!")
        self.home_dir = Path(home_dir)
        self.move_list: list[_MoveAction] = []
        os.makedirs(self.home_dir, exist_ok=True)
        os.makedirs(self.home_dir / ".mcpm-all-mods", exist_ok=True)
        
    def move_files(self, includes: str, excludes: str, destination: Path | str):
        """
        Move files from home_dir to destination (relative to home_dir).
        """
        try:
            files = os.listdir(self.home_dir)
        except FileNotFoundError:
            os.makedirs(self.home_dir, exist_ok=True)
            files = []
            print(f"[Warning] Folder created and is empty")
        
        dest_path = self.home_dir / destination
        os.makedirs(dest_path, exist_ok=True)
        
        self.move_list = []  # Reset move list
        for f in files:
            full_path = self.home_dir / f
            if (full_path.is_file() and 
                includes in f and 
                (not excludes or excludes not in f)):
                self.move_list.append(_MoveAction(full_path, dest_path / f))
        
        self._execute(self.move_list, debug=False)
    
    def _execute(self, move_list: list[_MoveAction] | None, debug=False):
        move_list = self.move_list if move_list is None else move_list
        for m in move_list:
            if debug:
                print(f"Moving: {m._from} -> {m._to}")
                time.sleep(0.5)
            shutil.move(str(m._from), str(m._to))
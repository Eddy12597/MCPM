import subprocess
from pathlib import Path
import os
import sys
import stat

def add_to_path_macos():
    """Add the dist directory to PATH on macOS by modifying shell config files"""
    
    # Get the directory where the executable will be
    dist_dir = Path(__file__).parent / "dist"
    binary_path = dist_dir / "main"  # No .exe on Mac
    final_binary = dist_dir / "mcpm"
    
    # Ensure the binary is executable
    if final_binary.exists():
        final_binary.chmod(final_binary.st_mode | stat.S_IEXEC)
    
    # Determine user's shell config file
    home = Path.home()
    shell = os.environ.get('SHELL', '/bin/zsh')  # macOS default is now zsh
    
    if 'zsh' in shell:
        config_file = home / '.zshrc'
    elif 'bash' in shell:
        config_file = home / '.bash_profile'  # or .bashrc
    else:
        config_file = home / '.profile'
    
    # Path line to add
    path_line = f'\nexport PATH="{dist_dir}:$PATH"\n'
    
    # Check if already in PATH
    current_path = os.environ.get('PATH', '')
    if str(dist_dir) not in current_path:
        # Append to config file if not already there
        if config_file.exists():
            with open(config_file, 'r') as f:
                content = f.read()
            if str(dist_dir) not in content:
                with open(config_file, 'a') as f:
                    f.write(f'# Added by mcpm installer\n{path_line}')
        else:
            with open(config_file, 'w') as f:
                f.write(f'# Added by mcpm installer\n{path_line}')
        
        print(f"Added {dist_dir} to PATH in {config_file}")
        print("Please restart your terminal or run: source", config_file)
    else:
        print(f"{dist_dir} is already in PATH")

def compile_macos_binary():
    """Compile the Python script to a macOS binary"""
    try:
        # Run PyInstaller
        subprocess.run(["pyinstaller", "--onefile", "main.py"], check=True)
        print("✅ Binary compiled successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)

def rename_binary():
    """Rename the compiled binary"""
    dist_dir = Path(__file__).parent / "dist"
    source = dist_dir / "main"
    destination = dist_dir / "mcpm"
    
    if source.exists():
        shutil.move(str(source), str(destination))
        # Make sure it's executable
        destination.chmod(destination.st_mode | stat.S_IEXEC)
        print(f"✅ Renamed binary to {destination}")
    else:
        print(f"❌ Could not find {source}")

if __name__ == "__main__":
    # Compile first
    compile_macos_binary()
    
    # Rename the binary
    rename_binary()
    
    # Add to PATH
    add_to_path_macos()
    
    print("\n✨ Installation complete!")
    print("To use mcpm, either:")
    print("  1. Restart your terminal, or")
    print("  2. Run: source ~/.zshrc (or your shell config file)")
    print("\nThen run: mcpm")
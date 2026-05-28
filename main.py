from dataclasses import dataclass

from filemover import FileMover
from argparse import ArgumentParser, Action
import os
import platform
from pathlib import Path
import json
import re
import shutil

def get_config_file():
    system = platform.system()
    if system == "Windows":
        config_dir = Path(os.environ.get('APPDATA', Path.home()/"AppData"/"Roaming"))
    elif system in ["Linux", "Darwin"]:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))
    else:
        config_dir = Path.home() / '.mcpm-config'
    
    config_dir = config_dir / ".mcpm"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "config.json"
    # Initialize with empty JSON object if file doesn't exist or is empty
    if not config_file.exists() or config_file.stat().st_size == 0:
        config_file.write_text("{}")
    
    return config_file

def config_store_kv(k, v, file=get_config_file()):
    cfg = {}
    try:
        with open(file, "r", encoding="utf-8") as fp:
            content = fp.read()
            if content.strip():  # Only parse if there's actual content
                cfg = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}  # Start fresh if any error occurs
    
    cfg[k] = v
    with open(file, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, indent=2)

def config_get(k, fallback, file=get_config_file(), debug=False):
    try:
        with open(file, "r", encoding="utf-8") as fp:
            content = fp.read()
            if content.strip():
                cfg = json.loads(content)
                return cfg.get(k, fallback)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if debug:
            print(f"Got error: {e} when loading config: k={k}, file={file}")
        pass
    return fallback

def handle_config(args):
    config_store_kv("HOME_DIR", args.home_dir)
    if args.debug:
        print(f"set HOME_DIR to {args.home_dir}")
        

"""
Problem: non-standard naming

1. typical one version:
appleskin-fabric-mc1.21.11-3.0.8.jar
do_a_barrel_roll-fabric-3.8.3+1.21.11.jar
dynamic-fps-3.11.6+minecraft-1.21.11-fabric.jar
Essential_1-3-10-8_fabric_1-21-11.jar
fabric-api-0.141.3+1.21.11.jar
ImmediatelyFast-Fabric-1.14.2+1.21.11.jar

2. all versions:
architectury-19.0.1-fabric.jar
elytra-infinite-1.4.0.jar
krypton-0.2.10.jar


3. range of versions:
CrashAssistant-fabric-1.21.5-1.21.11-1.11.8.jar (ambiguous - 1.11.8 is mod version or minecraft version? likely the former)
cicada-lib-0.14.3+1.21.9-1.21.10.jar

"""

def is_valid_mc_version(v: str) -> bool:
    """Check if a version string looks like a real Minecraft version."""
    parts = v.split('.')
    if len(parts) < 2:
        return False
    major = int(parts[0])
    if major == 1:
        # 1.x or 1.x.y, minor >= 14 (Fabric era)
        if len(parts) in (2, 3) and int(parts[1]) >= 14:
            return True
    elif major >= 26:   # Year‑based, only from 26 onwards
        if len(parts) == 3:
            minor = int(parts[1])
            patch = int(parts[2])
            if minor <= 12 and patch <= 50:   # month‑like, reasonable build
                return True
    return False

def expand_version_range(versions_set: set[str], context: str) -> set[str]:
    """If two versions appear as a range (e.g. 1.21.5-1.21.11), add all intermediate patch versions."""
    expanded = set(versions_set)
    sorted_vers = sorted(versions_set, key=lambda v: tuple(int(x) for x in v.split('.')))
    for i in range(len(sorted_vers)):
        for j in range(i+1, len(sorted_vers)):
            v1, v2 = sorted_vers[i], sorted_vers[j]
            p1, p2 = v1.split('.'), v2.split('.')
            # Must be 3-part, same major.minor, increasing patch
            if (len(p1) == 3 and len(p2) == 3 and
                p1[0] == p2[0] and p1[1] == p2[1] and int(p1[2]) < int(p2[2])):
                # Check if original string contains v1-v2 explicitly
                if f"{v1}-{v2}" in context:
                    for patch in range(int(p1[2]), int(p2[2]) + 1):
                        expanded.add(f"{p1[0]}.{p1[1]}.{patch}")
    return expanded

def get_minecraft_versions(mod_name: str) -> set[str]:
    """
    Return a set of Minecraft versions the mod is compatible with.
    An empty set means universal (compatible with any version).
    """
    name = mod_name.rsplit('.', 1)[0] if '.' in mod_name else mod_name
    override_match = re.search(r'mcpm-override-(\d+\.\d+(?:\.\d+)?)', name, re.IGNORECASE)
    if override_match:
        ver = override_match.group(1)
        if is_valid_mc_version(ver):
            return {ver}
        
    # 1. Explicit "mc" or "minecraft" marker
    mc_pattern = re.compile(r'(?:mc|minecraft)[-_]?(\d+\.\d+(?:\.\d+)?)', re.IGNORECASE)
    explicit = mc_pattern.findall(name)
    if explicit:
        return set(explicit)

    # 2. Loader keyword + underscore/hyphen version (Essential style)
    loader_ver = re.search(r'(?:fabric|forge|neoforge|quilt)[_-](\d+[_-]\d+(?:[_-]\d+)?)', name, re.IGNORECASE)
    if loader_ver:
        dot_ver = loader_ver.group(1).replace('-', '.').replace('_', '.')
        if is_valid_mc_version(dot_ver):
            return {dot_ver}

    # 3. Plus separator: only if after-plus starts with digit or mc/minecraft
    if '+' in name:
        after_plus = name.rsplit('+', 1)[-1]
        if re.match(r'^(?:\d|mc|minecraft)', after_plus, re.IGNORECASE):
            versions = re.findall(r'(?:mc|minecraft[-_])?(\d+\.\d+(?:\.\d+)?)', after_plus, re.IGNORECASE)
            mc_candidates = {v for v in versions if is_valid_mc_version(v)}
            if mc_candidates:
                return expand_version_range(mc_candidates, name)

    # 4. General dot‑version extraction
    all_versions = re.findall(r'\d+\.\d+(?:\.\d+)?', name)
    mc_candidates = set()
    for v in all_versions:
        if is_valid_mc_version(v):
            mc_candidates.add(v)

    if mc_candidates:
        return expand_version_range(mc_candidates, name)
    
    return set()

def get_mod_version(mod_name: str) -> str | None:
    """
    Extract the Minecraft version from a mod filename.
    """
    # Match versions like 1.20.1, 1.19.2, etc.
    version_pattern = r'(\d+\.\d+(?:\.\d+)?)'
    match = re.search(version_pattern, mod_name)
    return match.group(1) if match else None

def main(vers, debug):
    fm = FileMover(home_dir=config_get("HOME_DIR", None))
    
    # Step 1: Move all current mods back to .mcpm-all-mods
    if debug:
        print("Saving current mods to .mcpm-all-mods...")
    fm.move_files(".jar", "", ".mcpm-all-mods")
    
    # Step 2: Pull mods for the requested version
    all_mods_dir = fm.home_dir / ".mcpm-all-mods"
    
    if not all_mods_dir.exists():
        if debug:
            print(".mcpm-all-mods directory doesn't exist yet")
        return
    
    try:
        all_mods = os.listdir(all_mods_dir)
        mods_to_activate = []
        skipped_universal = []
        
        for mod in all_mods:
            if not mod.endswith('.jar'):
                continue
            
            versions = get_minecraft_versions(mod)
            
            # If versions is empty, treat as universal (compatible with any version)
            if not versions:
                mods_to_activate.append(mod)
                if debug:
                    print(f"  🌐 Universal: {mod}")
            elif vers in versions:
                mods_to_activate.append(mod)
                if debug:
                    # Show which versions this mod supports
                    versions_str = ', '.join(sorted(versions))
                    print(f"  ✅ Compatible: {mod} (supports: {versions_str})")
            else:
                if debug:
                    versions_str = ', '.join(sorted(versions))
                    print(f"  ⏭️  Skipping: {mod} (supports: {versions_str}, not {vers})")
        
        if debug:
            print(f"\nActivating {len(mods_to_activate)} mods for version {vers}...")
        
        # Copy matching mods to main directory
        for mod in mods_to_activate:
            src = all_mods_dir / mod
            dst = fm.home_dir / mod
            try:
                shutil.copy2(str(src), str(dst))
                if debug:
                    print(f"  📋 Activated: {mod}")
            except Exception as e:
                print(f"  ❌ Error copying {mod}: {e}")
        
        # Summary
        active_mods = [f for f in os.listdir(fm.home_dir) 
                      if f.endswith('.jar') and os.path.isfile(fm.home_dir / f)]
        
        print(f"\n✅ Successfully switched to Minecraft version {vers}")
        print(f"📦 Active mods: {len(active_mods)}")
        
        if debug:
            print("\nActive mods list:")
            for mod in sorted(active_mods):
                versions = get_minecraft_versions(mod)
                if versions:
                    versions_str = ', '.join(sorted(versions))
                    print(f"  - {mod} ({versions_str})")
                else:
                    print(f"  - {mod} (universal)")
        
    except Exception as e:
        print(f"❌ Error during checkout: {e}")

def import_mods(mod_path, debug):
    """Import mod files to .mcpm-all-mods"""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    all_mods_dir = Path(home_dir) / ".mcpm-all-mods"
    os.makedirs(all_mods_dir, exist_ok=True)
    
    mod_path = Path(mod_path)
    if mod_path.is_file() and mod_path.suffix == '.jar':
        # Import single mod
        dst = all_mods_dir / mod_path.name
        shutil.copy2(str(mod_path), str(dst))
        if debug:
            print(f"Imported: {mod_path.name}")
    elif mod_path.is_dir():
        # Import all mods from directory
        imported = 0
        for mod_file in mod_path.glob("*.jar"):
            dst = all_mods_dir / mod_file.name
            shutil.copy2(str(mod_file), str(dst))
            imported += 1
            if debug:
                print(f"Imported: {mod_file.name}")
        print(f"Imported {imported} mods")
    else:
        print(f"Invalid mod path: {mod_path}")

# Update the main block to include the detail flag
def clear_mods(debug):
    """Clear all .jar files from the home directory, keeping .mcpm-all-mods intact."""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    home_path = Path(home_dir)
    if not home_path.exists():
        print(f"Error: Home directory does not exist: {home_dir}")
        return
    
    # Find all .jar files in the home directory (not in subdirectories)
    jar_files = [f for f in os.listdir(home_path) 
                 if f.endswith('.jar') and os.path.isfile(home_path / f)]
    
    if not jar_files:
        print("No .jar files found in home directory.")
        return
    
    print(f"Found {len(jar_files)} .jar files to remove.")
    if debug:
        for f in jar_files:
            print(f)
    
    # Confirm deletion
    response = input("Are you sure you want to delete all .jar files from the home directory? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("Operation cancelled.")
        return
    
    deleted = 0
    errors = 0
    
    for jar_file in jar_files:
        try:
            file_path = home_path / jar_file
            os.remove(file_path)
            if debug:
                print(f"  🗑️  Deleted: {jar_file}")
            deleted += 1
        except Exception as e:
            print(f"  ❌ Error deleting {jar_file}: {e}")
            errors += 1
    
    # Summary
    print(f"\n✅ Successfully deleted {deleted} .jar files")
    if errors > 0:
        print(f"❌ Failed to delete {errors} files")
    
    # Show remaining files
    remaining = [f for f in os.listdir(home_path) 
                if f.endswith('.jar') and os.path.isfile(home_path / f)]
    if remaining:
        print(f"⚠️  {len(remaining)} .jar files remain in home directory")



def search_mods(query, debug):
    """Search for mods in .mcpm-all-mods by name."""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    all_mods_dir = Path(home_dir) / ".mcpm-all-mods"
    if not all_mods_dir.exists():
        print("No mods directory found. Import some mods first!")
        return
    
    if not query:
        print("Please provide a search query.")
        return
    
    matches = []
    for mod in os.listdir(all_mods_dir):
        if mod.endswith('.jar') and query.lower() in mod.lower():
            matches.append(mod)
    
    if not matches:
        print(f"No mods found matching '{query}'")
        return
    
    print(f"\n🔍 Found {len(matches)} mods matching '{query}':")
    print("="*70)
    
    for i, mod in enumerate(sorted(matches), 1):
        versions = get_minecraft_versions(mod)
        version_str = ', '.join(sorted(versions)) if versions else 'universal'
        print(f"{i:3}. {mod}")
        print(f"     Versions: {version_str}")
        
        # Check if the mod is currently active in home directory
        mod_path = Path(home_dir) / mod
        disabled_path = Path(home_dir) / (mod + '.disabled')
        
        if mod_path.exists():
            print(f"     Status: ✅ Active")
        elif disabled_path.exists():
            print(f"     Status: 🚫 Disabled")
        else:
            print(f"     Status: 📦 In repository only")
        
        if debug:
            file_path = all_mods_dir / mod
            size = file_path.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / (1024*1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"     Size: {size_str}")
        print()


def toggle_mod(mod_name, enable=True, debug=False):
    """Enable or disable a mod by adding/removing .disabled suffix.
    Works on mods in both home directory and .mcpm-all-mods repository."""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    home_path = Path(home_dir)
    all_mods_dir = home_path / ".mcpm-all-mods"
    
    if enable:
        # Enable: remove .disabled suffix
        if not mod_name.endswith('.disabled'):
            print(f"Error: '{mod_name}' doesn't have .disabled suffix.")
            print("To enable a mod, specify the full filename including '.disabled'")
            return
        
        # Check in home directory first
        disabled_path = home_path / mod_name
        if disabled_path.exists():
            target_dir = home_path
            is_repo = False
        # Then check in repository
        elif all_mods_dir.exists():
            disabled_path = all_mods_dir / mod_name
            if disabled_path.exists():
                target_dir = all_mods_dir
                is_repo = True
            else:
                print(f"Error: '{mod_name}' not found in home directory or .mcpm-all-mods.")
                return
        else:
            print(f"Error: '{mod_name}' not found.")
            return
        
        # Remove .disabled suffix
        enabled_name = mod_name[:-9]  # Remove '.disabled'
        enabled_path = target_dir / enabled_name
        
        try:
            shutil.move(str(disabled_path), str(enabled_path))
            location = "repository" if is_repo else "home directory"
            print(f"✅ Enabled: {enabled_name} (in {location})")
            if debug:
                print(f"   Moved: {mod_name} -> {enabled_name}")
        except Exception as e:
            print(f"❌ Error enabling mod: {e}")
    else:
        # Disable: add .disabled suffix
        # Handle both cases: user might specify with or without .jar
        if not mod_name.endswith('.jar'):
            mod_name += '.jar'
        
        mod_path = home_path / mod_name
        all_mods_path = all_mods_dir / mod_name if all_mods_dir.exists() else None
        
        if mod_path.exists():
            target_path = mod_path
            target_dir = home_path
            is_repo = False
        elif all_mods_path and all_mods_path.exists():
            target_path = all_mods_path
            target_dir = all_mods_dir
            is_repo = True
        else:
            print(f"Error: '{mod_name}' not found in home directory or .mcpm-all-mods.")
            return
        
        if mod_name.endswith('.disabled'):
            print(f"Error: '{mod_name}' is already disabled.")
            return
        
        disabled_path = target_dir / (mod_name + '.disabled')
        
        try:
            shutil.move(str(target_path), str(disabled_path))
            location = "repository" if is_repo else "home directory"
            print(f"🚫 Disabled: {mod_name} (in {location})")
            if debug:
                print(f"   Moved: {mod_name} -> {mod_name}.disabled")
        except Exception as e:
            print(f"❌ Error disabling mod: {e}")

def list_mods(debug, show_mods=False):
    """List mods based on detail level.
    Without detail: simple list of .jar files in home directory (like ls | grep .jar)
    With detail: formatted list of mods in home directory and .mcpm-all-mods"""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    home_path = Path(home_dir)
    all_mods_dir = home_path / ".mcpm-all-mods"
    
    if not show_mods:
        # Simple mode: just list .jar files in home directory
        if not home_path.exists():
            print("Home directory does not exist.")
            return
        
        # Get all files ending with .jar or .jar.disabled
        jar_files = []
        try:
            for f in os.listdir(home_path):
                if os.path.isfile(home_path / f) and (f.endswith('.jar') or f.endswith('.jar.disabled')):
                    jar_files.append(f)
        except Exception as e:
            print(f"Error reading home directory: {e}")
            return
        
        if not jar_files:
            print("No mods found in home directory.")
            return
        
        # Simple listing, one per line
        for f in sorted(jar_files):
            print(f)
    
    else:
        # Detail mode: show both home directory and repository
        print("\n" + "="*70)
        print("MODS IN HOME DIRECTORY")
        print("="*70)
        
        if not home_path.exists():
            print("Home directory does not exist.")
        else:
            active_mods = []
            disabled_mods = []
            
            try:
                for f in os.listdir(home_path):
                    if not os.path.isfile(home_path / f):
                        continue
                    if f.endswith('.jar.disabled'):
                        disabled_mods.append(f)
                    elif f.endswith('.jar'):
                        active_mods.append(f)
            except Exception as e:
                print(f"Error reading home directory: {e}")
                active_mods = disabled_mods = []
            
            if active_mods:
                print(f"\n✅ Active mods ({len(active_mods)}):")
                for mod in sorted(active_mods):
                    versions = get_minecraft_versions(mod)
                    version_str = ', '.join(sorted(versions)) if versions else 'universal'
                    
                    file_path = home_path / mod
                    size = file_path.stat().st_size
                    if size > 1024 * 1024:
                        size_str = f"{size / (1024*1024):.1f} MB"
                    elif size > 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size} B"
                    
                    print(f"   - {mod}")
                    print(f"     Versions: {version_str} | Size: {size_str}")
            
            if disabled_mods:
                print(f"\n🚫 Disabled mods ({len(disabled_mods)}):")
                for mod in sorted(disabled_mods):
                    # Remove .disabled for version detection
                    clean_name = mod[:-9]  # Remove '.disabled'
                    versions = get_minecraft_versions(clean_name)
                    version_str = ', '.join(sorted(versions)) if versions else 'universal'
                    
                    file_path = home_path / mod
                    size = file_path.stat().st_size
                    if size > 1024 * 1024:
                        size_str = f"{size / (1024*1024):.1f} MB"
                    elif size > 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size} B"
                    
                    print(f"   - {mod}")
                    print(f"     Versions: {version_str} | Size: {size_str}")
            
            if not active_mods and not disabled_mods:
                print("\nNo mods found in home directory.")
        
        # Repository section
        if all_mods_dir.exists():
            print("\n" + "="*70)
            print("MODS IN REPOSITORY (.mcpm-all-mods)")
            print("="*70)
            
            repo_mods = []
            try:
                for f in os.listdir(all_mods_dir):
                    if os.path.isfile(all_mods_dir / f) and (f.endswith('.jar') or f.endswith('.jar.disabled')):
                        repo_mods.append(f)
            except Exception as e:
                print(f"Error reading repository: {e}")
                repo_mods = []
            
            if repo_mods:
                active_repo = [m for m in repo_mods if not m.endswith('.disabled')]
                disabled_repo = [m for m in repo_mods if m.endswith('.disabled')]
                
                if active_repo:
                    print(f"\n📦 Active in repository ({len(active_repo)}):")
                    for mod in sorted(active_repo):
                        versions = get_minecraft_versions(mod)
                        version_str = ', '.join(sorted(versions)) if versions else 'universal'
                        
                        file_path = all_mods_dir / mod
                        size = file_path.stat().st_size
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024*1024):.1f} MB"
                        elif size > 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                        
                        print(f"   - {mod}")
                        print(f"     Versions: {version_str} | Size: {size_str}")
                
                if disabled_repo:
                    print(f"\n🚫 Disabled in repository ({len(disabled_repo)}):")
                    for mod in sorted(disabled_repo):
                        clean_name = mod[:-9]
                        versions = get_minecraft_versions(clean_name)
                        version_str = ', '.join(sorted(versions)) if versions else 'universal'
                        
                        file_path = all_mods_dir / mod
                        size = file_path.stat().st_size
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024*1024):.1f} MB"
                        elif size > 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                        
                        print(f"   - {mod}")
                        print(f"     Versions: {version_str} | Size: {size_str}")
                
                # Summary
                total = len(active_repo) + len(disabled_repo)
                print(f"\n📊 Repository summary: {total} total ({len(active_repo)} active, {len(disabled_repo)} disabled)")
            else:
                print("\nNo mods found in repository.")
        else:
            print("\n📁 No repository found. Import some mods first!")
        
        print("\n" + "="*70)

# Update the list_versions function to use the new list_mods function
def list_versions(debug, show_mods=False):
    """List all available Minecraft versions found in .mcpm-all-mods"""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return
    
    all_mods_dir = Path(home_dir) / ".mcpm-all-mods"
    if not all_mods_dir.exists():
        print("No mods directory found. Import some mods first!")
        return
    
    versions = {}
    universal = []
    
    try:
        for mod in os.listdir(all_mods_dir):
            if not mod.endswith('.jar'):
                continue
            mc_versions = get_minecraft_versions(mod)
            if not mc_versions:
                universal.append(mod)
            else:
                for v in mc_versions:
                    versions.setdefault(v, []).append(mod)
    except Exception as e:
        print(f"Error reading mods directory: {e}")
        return
    
    if not versions and not universal:
        print("No mods found in .mcpm-all-mods")
        return
    
    print("\n" + "="*70)
    print("AVAILABLE MINECRAFT VERSIONS")
    print("="*70)
    
    # Sort versions naturally
    def version_sort_key(v):
        parts = v.split('.')
        return tuple(int(p) for p in parts)
    
    for version in sorted(versions.keys(), key=version_sort_key):
        mod_count = len(versions[version])
        print(f"\n📦 Version {version} ({mod_count} mods)")
        
        if show_mods or debug:
            for mod in sorted(versions[version]):
                print(f"   - {mod}")
    
    if universal:
        print(f"\n🌐 Universal mods ({len(universal)}):")
        if show_mods or debug:
            for mod in sorted(universal):
                print(f"   - {mod}")
        else:
            print(f"   (use -d or --detail to show mod names)")
    
    # Summary
    total_versioned = sum(len(mods) for mods in versions.values())
    print(f"\n📊 Summary: {total_versioned} versioned mods across {len(versions)} versions")
    print(f"🌐 {len(universal)} universal mods")
    print(f"📁 Total: {total_versioned + len(universal)} mods in .mcpm-all-mods")

def change_mod_version(mod_name, target_version, debug=False, force=False):
    """Rename a mod in .mcpm-all-mods to set/change a version override."""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return

    if not is_valid_mc_version(target_version):
        print(f"Error: '{target_version}' is not a valid Minecraft version.")
        return

    all_mods_dir = Path(home_dir) / ".mcpm-all-mods"
    if not all_mods_dir.exists():
        print("No .mcpm-all-mods directory found. Import mods first.")
        return

    original_path = all_mods_dir / mod_name
    if not original_path.exists():
        print(f"Error: '{mod_name}' not found in .mcpm-all-mods.")
        return
    if not original_path.suffix == '.jar':
        print(f"Error: '{mod_name}' is not a .jar file.")
        return

    # Strip any existing mcpm-override-* suffix from the stem
    stem = original_path.stem
    new_stem = re.sub(r'-mcpm-override-\d+\.\d+(\.\d+)?$', '', stem, flags=re.IGNORECASE)

    # Build new name with the target version
    new_name = f"{new_stem}-mcpm-override-{target_version}.jar"
    new_path = all_mods_dir / new_name

    if original_path.resolve() == new_path.resolve():
        print(f"Mod already set to version {target_version}. No changes made.")
        return

    if new_path.exists() and not force:
        print(f"Warning: '{new_name}' already exists. Use --force to overwrite.")
        return

    if not force:
        confirm = input(f"Rename '{mod_name}' to '{new_name}'? (y/N): ")
        if confirm.lower() not in ('y', 'yes'):
            print("Operation cancelled.")
            return

    try:
        shutil.move(str(original_path), str(new_path))
        print(f"✅ Mod version changed to {target_version}")
        if debug:
            print(f"   Renamed: {mod_name} -> {new_name}")
    except Exception as e:
        print(f"❌ Error renaming file: {e}")

def reset_mod_version(mod_name, debug=False, force=False):
    """Remove any mcpm-override from a mod's filename, restoring original version detection."""
    home_dir = config_get("HOME_DIR", None)
    if not home_dir:
        print("Error: HOME_DIR not configured. Run 'config --home_dir <path>' first.")
        return

    all_mods_dir = Path(home_dir) / ".mcpm-all-mods"
    if not all_mods_dir.exists():
        print("No .mcpm-all-mods directory found.")
        return

    original_path = all_mods_dir / mod_name
    if not original_path.exists():
        print(f"Error: '{mod_name}' not found in .mcpm-all-mods.")
        return

    # Check if it actually has an override
    stem = original_path.stem
    if not re.search(r'-mcpm-override-\d+\.\d+(\.\d+)?$', stem, re.IGNORECASE):
        print(f"'{mod_name}' has no version override to remove.")
        return

    # Remove the override suffix
    new_stem = re.sub(r'-mcpm-override-\d+\.\d+(\.\d+)?$', '', stem, flags=re.IGNORECASE)
    new_name = f"{new_stem}.jar"
    new_path = all_mods_dir / new_name

    if new_path.exists() and not force:
        print(f"Warning: '{new_name}' already exists. Use --force to overwrite.")
        return

    if not force:
        # Show what versions the mod would be detected as
        original_versions = get_minecraft_versions(mod_name)
        override_versions = get_minecraft_versions(new_name)
        
        print(f"Current override: {', '.join(original_versions) if original_versions else 'none'}")
        print(f"Would detect as: {', '.join(override_versions) if override_versions else 'universal'}")
        
        confirm = input(f"Rename '{mod_name}' to '{new_name}'? (y/N): ")
        if confirm.lower() not in ('y', 'yes'):
            print("Operation cancelled.")
            return

    try:
        shutil.move(str(original_path), str(new_path))
        print(f"✅ Version override removed from '{mod_name}'")
        if debug:
            print(f"   Renamed: {mod_name} -> {new_name}")
            
            # Show what versions it's now compatible with
            new_versions = get_minecraft_versions(new_name)
            if new_versions:
                print(f"   Now compatible with: {', '.join(sorted(new_versions))}")
            else:
                print(f"   Now treated as: universal")
    except Exception as e:
        print(f"❌ Error renaming file: {e}")


__version__ = "0.2.4"

class VersionAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print(f"MCPM v{__version__}")
        parser.exit()

if __name__=="__main__":
    cfg_file_str = str(get_config_file())
    arg = ArgumentParser(description="Minecraft Package Manager [MCPM].")
    
    arg.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    arg.add_argument(
        "-v", "--version",
        action=VersionAction,
        nargs=0,
        help="Show version and exit"
    )
    subparsers = arg.add_subparsers(dest="command", help="Subcommands")
    
    # Config command
    config_parser = subparsers.add_parser("config", aliases=["C"], help="Config Management")
    config_parser.add_argument("--home_dir", "-H", "--homedir", "--home-dir", type=str, required=True, help="Path to home directory for /mods")
    
    # Checkout command
    checkout_parser = subparsers.add_parser("checkout", aliases=["c"], help="Switch to a version")
    checkout_parser.add_argument("version", type=str, help="Version to switch to")
    
    # List command with detail flag
    list_parser = subparsers.add_parser("list", aliases=["l"], help="List available versions")
    list_parser.add_argument("-d", "--detail", action="store_true", 
                            help="Show individual mod names for each version")
    
    # Import command
    import_parser = subparsers.add_parser("import", aliases=["i"], help="Import mods to .mcpm-all-mods")
    import_parser.add_argument("mod_path", type=str, help="Path to mod file or directory")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", aliases=["cl", "clr", "cls"], help="Clear all .jar files from home directory")
    clear_parser.add_argument("--force", "-f", action="store_true", 
                             help="Skip confirmation prompt")
    
    # Search command
    search_parser = subparsers.add_parser("search", aliases=["s"], help="Search for mods by name")
    search_parser.add_argument("query", type=str, help="Search query (case-insensitive)")
    
    # Enable command
    enable_parser = subparsers.add_parser("enable", aliases=["e"], help="Enable a disabled mod")
    enable_parser.add_argument("mod_name", type=str, help="Mod filename with .disabled suffix")
    
    # Disable command
    disable_parser = subparsers.add_parser("disable", aliases=["d"], help="Disable a mod")
    disable_parser.add_argument("mod_name", type=str, help="Mod filename to disable")
    
    # change mod version
    change_mod_version_parser = subparsers.add_parser("chv", aliases=["cv"], help="Change mod version")
    change_mod_version_parser.add_argument("mod_name", type=str, help="Mod filename in .mcpm-all-mods")
    change_mod_version_parser.add_argument("target_version", type=str, help="Target Minecraft version")
    change_mod_version_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")
    
    # Reset/deoverride command
    reset_parser = subparsers.add_parser("reset", aliases=["deoverride", "ro", "rs"], 
                                        help="Remove version override from a mod")
    reset_parser.add_argument("mod_name", type=str, 
                            help="Mod filename in .mcpm-all-mods (with override)")
    reset_parser.add_argument("--force", "-f", action="store_true", 
                            help="Skip confirmation prompt")
    
    args = arg.parse_args()
    debug = args.debug
    
    if args.command == "config":
        handle_config(args)
    elif args.command == "checkout":
        main(args.version, debug)
    elif args.command == "list":
        list_mods(debug, show_mods=getattr(args, 'detail', False))
    elif args.command == "import":
        import_mods(args.mod_path, debug)
    elif args.command == "clear":
        if getattr(args, 'force', False):
            home_dir = config_get("HOME_DIR", None)
            if home_dir:
                home_path = Path(home_dir)
                jar_files = [f for f in os.listdir(home_path) 
                           if f.endswith('.jar') and os.path.isfile(home_path / f)]
                deleted = 0
                for jar_file in jar_files:
                    try:
                        os.remove(home_path / jar_file)
                        if debug:
                            print(f"  🗑️  Deleted: {jar_file}")
                        deleted += 1
                    except Exception as e:
                        print(f"  ❌ Error deleting {jar_file}: {e}")
                print(f"✅ Force deleted {deleted} .jar files")
        else:
            clear_mods(debug)
    elif args.command == "search":
        search_mods(args.query, debug)
    elif args.command == "enable":
        toggle_mod(args.mod_name, enable=True, debug=debug)
    elif args.command == "disable":
        toggle_mod(args.mod_name, enable=False, debug=debug)
    elif args.command == "chv":
        force = getattr(args, 'force', False)
        change_mod_version(args.mod_name, args.target_version, debug=debug, force=force)
    elif args.command == "reset":
        force = getattr(args, 'force', False)
        reset_mod_version(args.mod_name, debug=debug, force=force)
    else:
        arg.print_help()
        
    if debug:
        print(f"\nConfig file directory: {cfg_file_str}")
        print(f"Home Directory: {config_get('HOME_DIR', None)}")
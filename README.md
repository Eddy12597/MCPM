# MCPM

Minecraft Package Manager CLI

## Notes

Used for launchers without version manager (e.g. TLauncher) where mods are stored in one folder.

## Features

```
usage: mcpm [-h] [--debug]
               {config,checkout,list,import,clear,search,enable,disable} ...

Minecraft Package Manager [MCPM].

positional arguments:
  {config,checkout,list,import,clear,search,enable,disable}
                        Subcommands
    config              Config Management
    checkout            Switch to a version
    list                List available versions
    import              Import mods to .mcpm-all-mods
    clear               Clear all .jar files from home directory
    search              Search for mods by name
    enable              Enable a disabled mod
    disable             Disable a mod

options:
  -h, --help            show this help message and exit
  --debug               Enable debug mode
```

- Enable/Disable mods
- Version checekout
- List mods

## Install and run

```
git clone https://github.com/Eddy12597/MCPM
pip install -r requirements.txt
```

### Windows

```
python install_win.py
```

Then add `/path/to/dist/` to PATH

## After Installation

Find your mods path for your launcher. For TLauncher, it can be found in the Folder icon at the bottom right, and click into it and go to the mods/ folder.

Set it as your mod home directory by running

```
mcpm config --home_dir /path/to/mods
```
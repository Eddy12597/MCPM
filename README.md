# MCPM

Minecraft Package Manager CLI

## Notes

Used for launchers without version manager (e.g. TLauncher) where mods are stored in one folder.

## Features

```
usage: mcpm.exe [-h] [--debug] [-v]
                {config,C,checkout,c,list,l,import,i,clear,cl,clr,cls,search,s,enable,e,disable,d} ...

Minecraft Package Manager [MCPM].

positional arguments:
  {config,C,checkout,c,list,l,import,i,clear,cl,clr,cls,search,s,enable,e,disable,d}
                        Subcommands
    config (C)          Config Management
    checkout (c)        Switch to a version
    list (l)            List available versions
    import (i)          Import mods to .mcpm-all-mods
    clear (cl, clr, cls)
                        Clear all .jar files from home directory
    search (s)          Search for mods by name
    enable (e)          Enable a disabled mod
    disable (d)         Disable a mod

options:
  -h, --help            show this help message and exit
  --debug               Enable debug mode
  -v, --version         Show version and exit
```

- Enable/Disable mods
- Version checkout (that is, switching between versions without manually moving mod files)
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

`/path/to/MCPM/dist/` *should* be automatically added to PATH. If it doesn't work, try adding to PATH manually. 

## After Installation

Find your mods path for your launcher. For TLauncher, it can be found in the Folder icon at the bottom right, and click into it and go to the mods/ folder.

Set it as your mod home directory by running

```
mcpm config --home_dir /path/to/mods
```
# DiskSpy

Storage Analyzer for Windows (CLI / TUI)

## What it does

DiskSpy scans a folder and shows:
- **Tree** view (folders by size)
- **Top** list (biggest folders/files)
- **Types** view (space by file extension)

It’s safe-by-default:
- Permission errors are **skipped** and reported
- Re-run with **`--elevate`** to include protected paths on Windows
## Install

Install guide (src): **[docs/INSTALL.md](docs/INSTALL.md)**
CLI docs: **[docs/CLI.md](docs/CLI.md)**

### One command install (PowerShell `iex`)

Downloads the latest **release** `diskspy.exe` and adds it to your PATH:

```powershell
iwr -useb https://raw.githubusercontent.com/Packetverlust/DiskSpy/main/install.ps1 | iex
```

Then open a NEW terminal and run:

```powershell
diskspy --version
```

You then can continue and run:

```powershell
diskspy scan C:\Users
```

OR:

```powershell
diskspy ui
```

Which Defaults to C:\Users\Your_Username

### Build from source

Download this Repo and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Usage

Help (multiple ways):
```bash
diskspy --help
diskspy -h
diskspy --h
diskspy :h
diskspy docs
```

Main command (mix outputs):
```bash
diskspy scan C:\Users --tree --types --top 40
```

Terminal UI:
```bash
diskspy ui C:\Users
```

Default ignores (on by default):
```bash
diskspy scan C:\Users --default-ignore
diskspy scan C:\Users --no-default-ignore
```

Shortcuts:
```bash
diskspy :sc C:\Users :d 4 :t 30 --types
```

Scans C:\Users with a Depth of 4 and Top of 30, also shows the types (dir, file)

Elevate (UAC):
```bash
diskspy scan C:\ --elevate --depth 4
```
# Note that the current update (v0.1.4) has broken the --elevate flag. Be patient thx

Exclude common junk:
```bash
diskspy scan C:\Users --exclude "node_modules,.git,AppData\Local\Temp" --types
```

## Commands

- `diskspy scan <path>` - main command (can be combined)
- `diskspy tree <path>` - tree only
- `diskspy top <path>` - top only
- `diskspy types <path>` - types only
- `diskspy ui <path>` - TUI
- `diskspy find <path> --name <glob>` - quick find (by filename glob)
- `diskspy export <path> -o diskspy.json` - export results to JSON
- `diskspy docs [topic]` - view docs inside the CLI

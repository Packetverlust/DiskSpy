# Installation Guide (Windows)

DiskSpy is a TreeSize-like disk usage analyzer written in Python.
You can install it as a single `diskspy.exe` (recommended for most users), or run it from source.

## Option A — One-command install (PowerShell `iex`)

This downloads the latest **release** `diskspy.exe` (from `update.json`) and installs it into:

`%LOCALAPPDATA%\Programs\DiskSpy\diskspy.exe`

Then it adds that folder to your **User PATH**.

```powershell
iwr -useb https://raw.githubusercontent.com/Packetverlust/Diskspy/main/install.ps1 | iex
```

If you get an execution policy error, open PowerShell as your user and run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Verify (open a **new** terminal first):

```powershell
diskspy --version
diskspy ui C:\Users
```

### Install from a local build (testing)

If you already have a `diskspy.exe` (for example from Releases), you can install it like this:

```powershell
.\install.ps1 -LocalExePath .\dist\diskspy.exe -Force
```

## Option B — Run / develop from source (Python)

### 1) Clone

```powershell
git clone https://github.com/Packetverlust/Diskspy.git
cd Diskspy
```

### 2) Create a virtualenv

PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

cmd.exe:
```bat
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 3) Install (editable)

```powershell
python -m pip install -e .
```

### 4) Run

```powershell
diskspy --help
diskspy scan C:\Users --tree --types --top 40
diskspy ui C:\Users
```


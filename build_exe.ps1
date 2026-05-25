$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found" }

python -m pip install --upgrade pip | Out-Null
python -m pip install --upgrade setuptools wheel | Out-Null
python -m pip install --upgrade pyinstaller | Out-Null
python -m pip install -e "." | Out-Null

if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

python -m PyInstaller --noconfirm "diskspy.spec" | Out-Null

if (-not (Test-Path "dist\\diskspy.exe")) { throw "Build failed: dist\\diskspy.exe not found" }

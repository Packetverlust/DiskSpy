param(
  [string]$Repo = "Packetverlust/DiskSpy",
  [string]$LocalExePath = "",
  [switch]$Force,
  [switch]$AllowDowngrade
)

$ErrorActionPreference = "Stop"

function Add-ToUserPath([string]$Dir) {
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (-not $userPath) { $userPath = "" }

  $parts = $userPath -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
  if ($parts -contains $Dir) { return }

  $newPath = ($parts + $Dir) -join ";"
  [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}

$ProgressPreference = "SilentlyContinue"

$installDir = Join-Path $env:LOCALAPPDATA "Programs\DiskSpy"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$targetExe = Join-Path $installDir "diskspy.exe"

function Norm-Ver([string]$s) {
  if (-not $s) { return "" }
  $t = ($s.Trim())
  if ($t.ToLower().StartsWith("diskspy")) {
    $t = ($t -replace '^(?i)diskspy\s*', '')
  }
  if ($t.StartsWith("v")) { $t = $t.Substring(1) }
  $m = [regex]::Match($t, '\d+(\.\d+){1,3}')
  if ($m.Success) { return $m.Value }
  return ""
}

function Ver-Obj([string]$s) {
  $n = (Norm-Ver $s)
  if (-not $n) { return $null }
  try { return [Version]$n } catch { return $null }
}

function Exe-Ver([string]$exe) {
  if (-not (Test-Path $exe)) { return $null }
  try {
    $out = & $exe --version 2>&1
    $v = Ver-Obj ($out | Out-String)
    if ($v) { return $v }

    try {
      $fvi = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($exe)
      $v = Ver-Obj ($fvi.ProductVersion)
      if ($v) { return $v }
      $v = Ver-Obj ($fvi.FileVersion)
      if ($v) { return $v }
    } catch { }

    try {
      $name = [System.IO.Path]::GetFileNameWithoutExtension($exe)
      $v = Ver-Obj $name
      if ($v) { return $v }
    } catch { }

    return $null
  } catch {
    return $null
  }
}

$installedVer = Exe-Ver $targetExe

function Assert-ValidExe([string]$Path, [string]$Context) {
  if (-not (Test-Path $Path)) { throw "$($Context): file not found: $Path" }
  $len = (Get-Item $Path).Length
  if ($len -lt 200000) {
    # Common failure case: GitHub returns "Not Found" or HTML and we copy that.
    $head = ""
    try { $head = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($Path)[0..63]) } catch { }
    throw "$($Context): downloaded file is too small ($len bytes). Head: $head"
  }
  try {
    $b = [System.IO.File]::ReadAllBytes($Path)[0..1]
    $sig = [System.Text.Encoding]::ASCII.GetString($b)
    if ($sig -ne "MZ") { throw "$($Context): invalid EXE signature (expected MZ, got '$sig')." }
  } catch {
    throw "$($Context): could not validate EXE signature."
  }
}

if ($LocalExePath) {
  if (-not (Test-Path $LocalExePath)) {
    throw "LocalExePath not found: $LocalExePath"
  }
    Assert-ValidExe $LocalExePath "LocalExePath"
  $srcVer = Exe-Ver $LocalExePath
  if (-not $srcVer) {
    if ($Force) {
      Write-Host "Installing DiskSpy from local build (version unknown)..." -ForegroundColor Yellow
      Copy-Item -Force -Path $LocalExePath -Destination $targetExe
      Assert-ValidExe $targetExe "Install"
      Add-ToUserPath $installDir
      $env:Path = "$installDir;$env:Path"
      Write-Host "Installed:" -ForegroundColor Green
      Write-Host "  $targetExe" -ForegroundColor Green
      Write-Host ""
      Write-Host "If your current terminal doesn't see diskspy yet, reopen the terminal, then run:" -ForegroundColor Cyan
      Write-Host "  diskspy --version" -ForegroundColor Cyan
      Write-Host "  diskspy --help" -ForegroundColor Cyan
      return
    }
    throw "Could not read version from LocalExePath."
  }
  if ($installedVer) {
    if ($srcVer -lt $installedVer) {
      if (-not $AllowDowngrade) {
        Write-Host "Refusing downgrade ($installedVer -> $srcVer). Re-run with -AllowDowngrade to override." -ForegroundColor Yellow
        Add-ToUserPath $installDir
        $env:Path = "$installDir;$env:Path"
        return
      }
      Write-Host "Downgrading ($installedVer -> $srcVer)..." -ForegroundColor Yellow
    }
    if ($srcVer -eq $installedVer -and (-not $Force)) {
      Write-Host "Same version already installed ($installedVer)." -ForegroundColor Green
      Add-ToUserPath $installDir
      $env:Path = "$installDir;$env:Path"
      return
    }
  }
  Write-Host "Installing DiskSpy $srcVer from local build..." -ForegroundColor Cyan
  Copy-Item -Force -Path $LocalExePath -Destination $targetExe
} else {
  Write-Host "Installing DiskSpy from GitHub ($Repo)..." -ForegroundColor Cyan

  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

  # Prefer update.json so "latest" is controlled by the repo,
  # not whatever GitHub happens to mark as "latest release" by date.
  $upd = $null
  try {
    $updUrl = "https://raw.githubusercontent.com/$Repo/main/update.json"
    $upd = Invoke-RestMethod -Uri $updUrl -Headers @{ "User-Agent" = "diskspy-installer" }
  } catch {
    $upd = $null
  }

  $dlUrl = ""
  $srcVer = $null

  if ($upd -and $upd.latest) {
    $srcVer = Ver-Obj ([string]$upd.latest)
    if (-not $srcVer) { throw "Could not parse version from update.json (latest=$($upd.latest))." }
    $dlUrl = [string]$upd.url
    if (-not $dlUrl) {
      $dlUrl = "https://github.com/$Repo/releases/download/v$($upd.latest)/diskspy.exe"
    }
  } else {
    # Fallback: GitHub API latest release (may be date-based).
    $api = "https://api.github.com/repos/$Repo/releases/latest"
    $rel = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "diskspy-installer" }
    if (-not $rel) { throw "Failed to fetch latest release from GitHub." }

    $assets = @($rel.assets)
    $asset = $assets | Where-Object { $_.name -and $_.name.ToLower() -eq "diskspy.exe" } | Select-Object -First 1
    if (-not $asset) {
      $asset = $assets | Where-Object { $_.name -and $_.name.ToLower().EndsWith(".exe") } | Select-Object -First 1
    }
    if (-not $asset -or -not $asset.browser_download_url) {
      throw "No suitable .exe asset found in latest release. Upload diskspy.exe to the GitHub Release assets."
    }

    $tag = $rel.tag_name
    if (-not $tag) { $tag = $rel.name }
    $srcVer = Ver-Obj $tag
    if (-not $srcVer) { throw "Could not parse latest release version." }
    $dlUrl = $asset.browser_download_url
  }

  if ($installedVer) {
    if ($srcVer -lt $installedVer) {
      if (-not $AllowDowngrade) {
        Write-Host "Refusing downgrade ($installedVer -> $srcVer). Re-run with -AllowDowngrade to override." -ForegroundColor Yellow
        Add-ToUserPath $installDir
        $env:Path = "$installDir;$env:Path"
        return
      }
      Write-Host "Downgrading ($installedVer -> $srcVer)..." -ForegroundColor Yellow
    }
    if ($srcVer -eq $installedVer -and (-not $Force)) {
      Write-Host "Same version already installed ($installedVer)." -ForegroundColor Green
      Add-ToUserPath $installDir
      $env:Path = "$installDir;$env:Path"
      return
    }
  }

  Write-Host "Downloading $srcVer..." -ForegroundColor Cyan
  Invoke-WebRequest -Uri $dlUrl -OutFile $targetExe -UseBasicParsing
  Assert-ValidExe $targetExe "Download"
}

Add-ToUserPath $installDir
$env:Path = "$installDir;$env:Path"

Write-Host "Installed:" -ForegroundColor Green
Write-Host "  $targetExe" -ForegroundColor Green
Write-Host ""
Write-Host "If your current terminal doesn't see diskspy yet, reopen the terminal, then run:" -ForegroundColor Cyan
Write-Host "  diskspy --version" -ForegroundColor Cyan
Write-Host "  diskspy --help" -ForegroundColor Cyan

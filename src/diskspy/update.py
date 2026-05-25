import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.panel import Panel

DEFAULT_REPO = "Packetverlust/DiskSpy"


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    min_supported: str
    download_url: Optional[str]
    notes: str = ""

    @property
    def update_available(self):
        return vcmp(self.latest, self.current) > 0

    @property
    def mandatory(self):
        return vcmp(self.current, self.min_supported) < 0


def vtuple(ver):
    ver = (ver or "").strip()
    if ver.startswith("v"):
        ver = ver[1:]
    parts = ver.split(".")
    nums: list[int] = []
    for idx in range(3):
        try:
            nums.append(int(parts[idx]) if idx < len(parts) else 0)
        except Exception:
            nums.append(0)
    return nums[0], nums[1], nums[2]


def vcmp(a, b):
    va = vtuple(a)
    vb = vtuple(b)
    return (va > vb) - (va < vb)


def cachefp():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    fold = base / "DiskSpy"
    fold.mkdir(parents=True, exist_ok=True)
    return fold / "update_cache.json"


def readcac(maxage):
    cfp = cachefp()
    try:
        data = json.loads(cfp.read_text(encoding="utf-8"))
        ts = float(data.get("ts", 0))
        if time.time() - ts <= maxage:
            return data
    except Exception:
        return None
    return None


def writeca(data):
    cfp = cachefp()
    out = dict(data)
    out["ts"] = time.time()
    cfp.write_text(json.dumps(out, indent=2), encoding="utf-8")


def fetchjs(url, timeout=3.0):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "diskspy-update-check",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as fp:
            txt = fp.read().decode("utf-8", errors="replace")
        return json.loads(txt)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None


def relurl(repo):
    return f"https://raw.githubusercontent.com/{repo}/main/update.json"


def apiurl(repo):
    return f"https://api.github.com/repos/{repo}/releases/latest"


def pickexe(rel):
    for ass in rel.get("assets", []) or []:
        name = (ass.get("name") or "").lower()
        if name.endswith(".exe") and ("diskspy" in name or name == "diskspy.exe"):
            return ass.get("browser_download_url")
    for ass in rel.get("assets", []) or []:
        name = (ass.get("name") or "").lower()
        if name.endswith(".exe"):
            return ass.get("browser_download_url")
    return None


def updinfo(curver, *, repo=DEFAULT_REPO, cache_seconds=21600):
    cur = curver
    cac = readcac(cache_seconds)
    if cac and cac.get("repo") == repo and cac.get("current") == cur:
        try:
            return UpdateInfo(
                current=cur,
                latest=str(cac["latest"]),
                min_supported=str(cac.get("min_supported", cur)),
                download_url=cac.get("download_url"),
                notes=str(cac.get("notes", "")),
            )
        except Exception:
            pass
    upd = fetchjs(relurl(repo))
    if upd:
        info = UpdateInfo(
            current=cur,
            latest=str(upd.get("latest", cur)),
            min_supported=str(upd.get("min_supported", cur)),
            download_url=upd.get("url"),
            notes=str(upd.get("notes", "")),
        )
        writeca(
            {
                "repo": repo,
                "current": cur,
                "latest": info.latest,
                "min_supported": info.min_supported,
                "download_url": info.download_url,
                "notes": info.notes,
            }
        )
        return info
    rel = fetchjs(apiurl(repo))
    if rel:
        latest = str(rel.get("tag_name") or rel.get("name") or cur).strip()
        url = pickexe(rel)
        info = UpdateInfo(
            current=cur, latest=latest, min_supported=cur, download_url=url, notes=""
        )
        writeca(
            {
                "repo": repo,
                "current": cur,
                "latest": info.latest,
                "min_supported": info.min_supported,
                "download_url": info.download_url,
                "notes": info.notes,
            }
        )
        return info
    return None


def updban(con, inf, *, show_run_hint: bool = True):
    tit = "Update required" if inf.mandatory else "Update available"
    msg = f"Current: [bold]{inf.current}[/bold]\nLatest: [bold]{inf.latest}[/bold]"
    if inf.download_url:
        if show_run_hint:
            msg += "\n\nRun: [bold]diskspy update[/bold]"
    else:
        msg += "\n\nNo download URL found (release may be missing a diskspy.exe asset)."
    if inf.notes:
        msg += f"\n\n[dim]{inf.notes}[/dim]"
    con.print(
        Panel(msg, title=tit, border_style="yellow" if inf.mandatory else "cyan")
    )


def dlfile(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "diskspy-updater"})
    with urllib.request.urlopen(req, timeout=15.0) as fp:
        data = fp.read()
    if len(data) < 200_000 or not data.startswith(b"MZ"):
        raise RuntimeError("Downloaded update does not look like a valid Windows executable.")
    dest.write_bytes(data)


def selfupd(con, inf):
    if not inf.download_url:
        con.print("[red]No download URL available.[/red]")
        return 1
    if not getattr(sys, "frozen", False):
        con.print(
            "[yellow]Self-update only works for the standalone .exe build.[/yellow]"
        )
        con.print(
            "If you installed from source, pull latest and rebuild, or re-run the installer."
        )
        return 1
    exe = Path(sys.executable).resolve()
    tmp = Path(os.environ.get("TEMP", str(exe.parent)))
    newexe = tmp / f"diskspy_{inf.latest}.exe"
    con.print(f"Downloading {inf.latest}…")
    dlfile(inf.download_url, newexe)
    bat = tmp / "diskspy_update.bat"
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                f'set "NEWEXE={newexe}"',
                f'set "TARGET={exe}"',
                "set /a tries=0",
                ":retry",
                "ping 127.0.0.1 -n 2 > nul",
                'copy /Y "%NEWEXE%" "%TARGET%" > nul',
                "if not errorlevel 1 goto ok",
                "set /a tries+=1",
                "if %tries% GEQ 10 goto fail",
                "goto retry",
                ":fail",
                "echo Update failed (could not overwrite the exe). Try running as admin or close apps using diskspy.exe",
                "exit /b 1",
                ":ok",
                "exit /b 0",
            ]
        ),
        encoding="ascii",
    )
    con.print("Applying update… (DiskSpy will exit)")
    con.print("[bold yellow]Please close this terminal and open a new one now.[/bold yellow]")
    con.print("[dim]Then run: diskspy --version[/dim]")
    try:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception:
        os.system(f'cmd.exe /c "{bat}" >nul 2>&1')
    return 0

def get_update_info(current_version, *, repo=DEFAULT_REPO, cache_seconds=21600):
    return updinfo(current_version, repo=repo, cache_seconds=cache_seconds)


def print_update_banner(console, info):
    return updban(console, info)


def self_update(console, info):
    return selfupd(console, info)

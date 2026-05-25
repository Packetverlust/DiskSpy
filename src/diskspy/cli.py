import fnmatch, json, os, re, sys
from pathlib import Path
from typing import List, Tuple
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from diskspy import __version__
from diskspy.docs import (
    DOCS_COMMANDS,
    DOCS_EXAMPLES,
    DOCS_FLAGS,
    DOCS_GLOSSARY,
    DOCS_INDEX,
    DOCS_OVERVIEW,
)
from diskspy.elevate import isadmin, runasadmin
from diskspy.render import (
    fmtbytes,
    rsum,
    rtop,
    rtree,
    rtypes,
)
from diskspy.scanner import ScanOptions, scanpath
from diskspy.shortcuts import preprocess_argv
from diskspy.update import updinfo, updban, selfupd

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": []},
)
con = Console()
DEFAULT_EXCLUDE = [
    "*__pycache__*",
    "*node_modules*",
    "*/.git*",
    "*\\.git*",
    "*/.venv*",
    "*\\.venv*",
    "*/dist*",
    "*\\dist*",
    "*/build*",
    "*\\build*",
]


def parsiz(s):
    txt = (s or "").strip()
    if not txt:
        return 0
    m = re.fullmatch("(?i)\\s*(\\d+(?:\\.\\d+)?)\\s*(b|kb|mb|gb|tb)?\\s*", txt)
    if not m:
        raise typer.BadParameter("Expected size like 10MB, 500KB, 2GB")
    num = float(m.group(1))
    unit = (m.group(2) or "b").lower()
    mult = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}[unit]
    return int(num * mult)


def mkopts(
    depth,
    top,
    min_size,
    include,
    exclude,
    follow_symlinks,
    default_ignore,
    *,
    collect_types: bool = False,
    files_only: bool = False,
    exclude_system: bool = False,
    progress=None,
):
    exc = list(exclude)
    if default_ignore:
        exc.extend(DEFAULT_EXCLUDE)
    return ScanOptions(
        depth=max(depth, 0),
        top=max(top, 0),
        min_size=parsiz(min_size),
        include=tuple(x for x in include if x),
        exclude=tuple(x for x in exc if x),
        follow_symlinks=follow_symlinks,
        collect_types=collect_types,
        files_only=files_only,
        exclude_system=exclude_system,
        progress=progress,
    )


def showhlp():
    optab = Table(show_header=False, box=None, pad_edge=False)
    optab.add_column("Option", style="cyan", no_wrap=True)
    optab.add_column("Description")
    optab.add_row("--version", "Show version and exit.")
    optab.add_row("--help", "Show this message and exit.")
    con.print(
        Panel(optab, title="Options", border_style="bright_black", box=box.ROUNDED)
    )
    cmdtab = Table(show_header=False, box=None, pad_edge=False)
    cmdtab.add_column("Command", style="cyan", no_wrap=True)
    cmdtab.add_column("Description")
    cmdtab.add_row("scan", "Scan a folder and print a TreeSize-like report.")
    cmdtab.add_row("tree", "Tree view only.")
    cmdtab.add_row("types", "Types breakdown only.")
    cmdtab.add_row("top", "Top list only.")
    cmdtab.add_row("ui", "Pane-based TUI.")
    cmdtab.add_row("find", "Find files/folders by name glob.")
    cmdtab.add_row("export", "Export a scan to JSON.")
    cmdtab.add_row("update", "Self-update DiskSpy (download latest .exe).")
    cmdtab.add_row("docs", "View docs inside the CLI.")
    con.print(
        Panel(cmdtab, title="Commands", border_style="bright_black", box=box.ROUNDED)
    )


@app.callback(invoke_without_command=True)
def cbmain(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", help="Show version and exit.", is_eager=True
    ),
    help: bool = typer.Option(
        False, "--help", "-h", help="Show help and exit.", is_eager=True
    ),
):
    if version:
        con.print(f"diskspy {__version__}")
        raise typer.Exit(0)
    if help:
        showhlp()
        raise typer.Exit(0)
    if (sys.stdout.isatty() or sys.stdin.isatty()) and ctx.invoked_subcommand != "update":
        info = updinfo(__version__, cache_seconds=0)
        if info and (info.update_available or info.mandatory):
            updban(con, info)
            try:
                if info.mandatory:
                    ok = typer.confirm("Update is required. Update now?", default=True)
                    if not ok:
                        raise typer.Exit(2)
                    rc = selfupd(con, info)
                    raise typer.Exit(rc)
                else:
                    ok = typer.confirm("Update now?", default=False)
                    if ok:
                        rc = selfupd(con, info)
                        raise typer.Exit(rc)
            except (EOFError, KeyboardInterrupt):
                pass
    if ctx.invoked_subcommand is None:
        showhlp()
        raise typer.Exit(0)


@app.command()
def scan(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    depth: int = typer.Option(
        4, "--depth", "-d", help="Scan depth (how deep we traverse)."
    ),
    top: int = typer.Option(
        0, "--top", "-t", help="Show Top N biggest items (files + dirs)."
    ),
    tree: bool = typer.Option(False, "--tree/--no-tree", help="Show tree view."),
    types: bool = typer.Option(
        False, "--types/--no-types", help="Show types (space by extension)."
    ),
    files_only: bool = typer.Option(
        False, "--files-only", help="Top list includes files only."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size (e.g. 10MB)."
    ),
    exclude: List[str] = typer.Option(
        [], "--exclude", help="Glob(s) to skip. Can be comma-separated."
    ),
    include: List[str] = typer.Option(
        [], "--include", help="Glob(s) to keep. Can be comma-separated."
    ),
    default_ignore: bool = typer.Option(
        True,
        "--default-ignore/--no-default-ignore",
        help="Ignore common junk folders by default.",
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    if elevate and os.name == "nt" and not isadmin():
        rc = runasadmin(sys.argv)
        if rc <= 32:
            raise typer.Exit(1)
        raise typer.Exit(0)
    with con.status(f"Scanning… {path}", spinner="dots") as st:
        opts = mkopts(
            depth,
            top,
            min_size,
            include,
            exclude,
            follow_symlinks,
            default_ignore,
            collect_types=types,
            files_only=files_only,
            exclude_system=exclude_system,
            progress=st.update,
        )
        res = scanpath(path, opts)
    rsum(con, res)
    if tree:
        rtree(con, res, depth=opts.depth)
    if top > 0:
        rtop(con, res, n=top)
    if types:
        rtypes(con, res, top=20)
    if res.skipped and os.name == "nt" and not elevate and not isadmin():
        con.print()
        con.print(
            "[dim]Tip:[/dim] rerun with [bold]--elevate[/bold] to include protected paths."
        )


@app.command()
def tree(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    depth: int = typer.Option(4, "--depth", "-d", help="Scan depth."),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size."
    ),
    exclude: List[str] = typer.Option([], "--exclude", help="Glob(s) to skip."),
    include: List[str] = typer.Option([], "--include", help="Glob(s) to keep."),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    scan(
        path=path,
        depth=depth,
        top=0,
        tree=True,
        types=False,
        files_only=False,
        exclude_system=exclude_system,
        min_size=min_size,
        exclude=exclude,
        include=include,
        follow_symlinks=follow_symlinks,
        elevate=elevate,
    )


@app.command()
def types(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    depth: int = typer.Option(8, "--depth", "-d", help="Scan depth."),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size."
    ),
    exclude: List[str] = typer.Option([], "--exclude", help="Glob(s) to skip."),
    include: List[str] = typer.Option([], "--include", help="Glob(s) to keep."),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    scan(
        path=path,
        depth=depth,
        top=0,
        tree=False,
        types=True,
        files_only=False,
        exclude_system=exclude_system,
        min_size=min_size,
        exclude=exclude,
        include=include,
        follow_symlinks=follow_symlinks,
        elevate=elevate,
    )


@app.command()
def top(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    depth: int = typer.Option(8, "--depth", "-d", help="Scan depth."),
    top: int = typer.Option(50, "--top", "-t", help="Show Top N biggest items."),
    files_only: bool = typer.Option(
        False, "--files-only", help="Top list includes files only."
    ),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size."
    ),
    exclude: List[str] = typer.Option([], "--exclude", help="Glob(s) to skip."),
    include: List[str] = typer.Option([], "--include", help="Glob(s) to keep."),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    scan(
        path=path,
        depth=depth,
        top=top,
        tree=False,
        types=False,
        files_only=files_only,
        exclude_system=exclude_system,
        min_size=min_size,
        exclude=exclude,
        include=include,
        follow_symlinks=follow_symlinks,
        elevate=elevate,
    )


@app.command()
def docs(
    topic = typer.Argument(
        "index", help="index | overview | commands | flags | glossary | examples"
    ),
):
    key = (topic or "index").strip().lower()
    text = {
        "index": DOCS_INDEX,
        "overview": DOCS_OVERVIEW,
        "commands": DOCS_COMMANDS,
        "flags": DOCS_FLAGS,
        "glossary": DOCS_GLOSSARY,
        "examples": DOCS_EXAMPLES,
    }
    con.print(text.get(key, DOCS_INDEX))


@app.command()
def ui(
    path: Path = typer.Argument(
        Path.cwd(), exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    depth: int = typer.Option(4, "--depth", "-d", help="Tree depth (left pane)."),
    top: int = typer.Option(30, "--top", "-t", help="Top list size (right pane)."),
    files_only: bool = typer.Option(
        False, "--files-only", help="Top list includes files only."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size (e.g. 10MB)."
    ),
    exclude: List[str] = typer.Option(
        [], "--exclude", help="Glob(s) to skip. Can be comma-separated."
    ),
    include: List[str] = typer.Option(
        [], "--include", help="Glob(s) to keep. Can be comma-separated."
    ),
    default_ignore: bool = typer.Option(
        True,
        "--default-ignore/--no-default-ignore",
        help="Ignore common junk folders by default.",
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    if elevate and os.name == "nt" and not isadmin():
        rc = runasadmin(sys.argv)
        if rc <= 32:
            raise typer.Exit(1)
        raise typer.Exit(0)
    opts = mkopts(
        depth,
        top,
        min_size,
        include,
        exclude,
        follow_symlinks,
        default_ignore,
        collect_types=True,
        files_only=files_only,
        exclude_system=exclude_system,
    )
    from diskspy.tui import runtui as runui

    runui(path, opts)


@app.command()
def find(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    pattern = typer.Argument(None, help="Optional name glob (e.g. *.txt)."),
    name = typer.Option(
        "*", "--name", "-n", help="Glob for file or folder name (e.g. *.mp4)."
    ),
    kind = typer.Option("any", "--kind", help="any | file | dir"),
    min_size = typer.Option("0B", "--min-size", help="Only show items >= size."),
    max_results: int = typer.Option(200, "--max", help="Max results to print."),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    nameg = name
    maxn = max_results
    if elevate and os.name == "nt" and not isadmin():
        rc = runasadmin(sys.argv)
        if rc <= 32:
            raise typer.Exit(1)
        raise typer.Exit(0)
    kind = kind.strip().lower()
    if kind not in ("any", "file", "dir"):
        raise typer.BadParameter("--kind must be: any | file | dir")
    if pattern and (nameg == "*" or not nameg):
        nameg = pattern
    minb = parsiz(min_size)
    root = path.resolve()
    fils = []
    dirs = []
    skp = 0
    for dirp, dirn, filn in os.walk(str(root), topdown=True):
        base = Path(dirp)
        if kind in ("any", "dir"):
            for subn in list(dirn):
                if fnmatch.fnmatch(subn.lower(), nameg.lower()):
                    path = base / subn
                    try:
                        dirs.append((0, "dir", path))
                        if len(dirs) > maxn * 4:
                            dirs = dirs[:maxn]
                    except OSError:
                        skp += 1
        if kind in ("any", "file"):
            for name in filn:
                if not fnmatch.fnmatch(name.lower(), nameg.lower()):
                    continue
                path = base / name
                try:
                    siz = int(path.stat().st_size)
                    if siz >= minb:
                        fils.append((siz, "file", path))
                        if len(fils) > maxn * 4:
                            fils.sort(key=lambda x: x[0], reverse=True)
                            del fils[maxn:]
                except (PermissionError, FileNotFoundError, OSError):
                    skp += 1
    fils.sort(key=lambda x: x[0], reverse=True)
    fils = fils[: maxn if maxn > 0 else None]
    dirs = dirs[: max(0, maxn - len(fils) if maxn > 0 else len(dirs))]
    rows = fils + dirs
    tab = Table(show_header=True, header_style="bold", box=None)
    tab.add_column("Size", style="cyan", no_wrap=True)
    tab.add_column("Kind", style="magenta", no_wrap=True)
    tab.add_column("Path", overflow="fold")
    for siz, knd, path in rows:
        tab.add_row("-" if knd == "dir" else fmtbytes(siz), knd, str(path))
    con.print(tab)
    if skp:
        con.print(f"[yellow]Skipped:[/yellow] {skp} paths (permission / missing).")


@app.command()
def export(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=False
    ),
    out: Path = typer.Option(
        Path("diskspy.json"), "--out", "-o", help="Output file path."
    ),
    depth: int = typer.Option(4, "--depth", "-d", help="Scan depth."),
    top: int = typer.Option(100, "--top", "-t", help="How many top items to include."),
    files_only: bool = typer.Option(
        False, "--files-only", help="Top list includes files only."
    ),
    exclude_system: bool = typer.Option(
        False, "--exclude-system", help="Skip common Windows system folders."
    ),
    min_size: str = typer.Option(
        "0B", "--min-size", help="Skip items smaller than size."
    ),
    exclude: List[str] = typer.Option(
        [], "--exclude", help="Glob(s) to skip. Can be comma-separated."
    ),
    include: List[str] = typer.Option(
        [], "--include", help="Glob(s) to keep. Can be comma-separated."
    ),
    default_ignore: bool = typer.Option(
        True,
        "--default-ignore/--no-default-ignore",
        help="Ignore common junk folders by default.",
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks/junctions."
    ),
    elevate: bool = typer.Option(
        False, "--elevate", help="Rerun as admin (Windows UAC)."
    ),
):
    outp = out
    if elevate and os.name == "nt" and not isadmin():
        rc = runasadmin(sys.argv)
        if rc <= 32:
            raise typer.Exit(1)
        raise typer.Exit(0)
    opts = mkopts(
        depth,
        top,
        min_size,
        include,
        exclude,
        follow_symlinks,
        default_ignore,
        collect_types=True,
        files_only=files_only,
        exclude_system=exclude_system,
    )
    res = scanpath(path, opts)
    data = {
        "version": __version__,
        "root": str(res.root),
        "total_bytes": res.total_bytes,
        "total_files": res.total_files,
        "total_dirs": res.total_dirs,
        "skipped": res.skipped,
        "skipped_samples": list(res.skipped_samples),
        "top_items": [
            {"bytes": nbytes, "path": str(path), "kind": kind}
            for (nbytes, path, kind) in res.top_items[: opts.top]
        ],
        "types": {
            ext: {"bytes": byt, "count": cnt} for ext, (byt, cnt) in res.types.items()
        },
    }
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    con.print(f"[green]Wrote[/green] {outp}")


@app.command()
def update(
    prompt: bool = typer.Option(
        False,
        "--prompt",
        help="Ask for confirmation before updating (default: update immediately).",
    ),
    yes: bool = typer.Option(
        True,
        "--yes",
        "-y",
        help="Update immediately (default). Kept for backwards compatibility.",
    ),
):
    info = updinfo(__version__, cache_seconds=0)
    if not info:
        con.print("[yellow]No update information available (offline?).[/yellow]")
        raise typer.Exit(1)
    if not info.update_available and not info.mandatory:
        con.print(f"[green]Up to date[/green] ({__version__})")
        raise typer.Exit(0)
    updban(con, info, show_run_hint=False)
    if prompt:
        yes = False
    if not yes:
        if info.mandatory:
            ok = typer.confirm("Update is required. Update now?", default=True)
        else:
            ok = typer.confirm("Update now?", default=True)
        if not ok:
            raise typer.Exit(0)
    rc = selfupd(con, info)
    raise typer.Exit(rc)


def main():
    sys.argv = preprocess_argv(sys.argv)
    if len(sys.argv) == 2 and sys.argv[1] == "__quit__":
        raise SystemExit(0)
    app()


if __name__ == "__main__":
    main()

import asyncio
import json
import os
import queue
from dataclasses import replace
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static, Tree

from diskspy import __version__
from diskspy.render import fmtbytes
from diskspy.scanner import scanpath
from diskspy.update import updinfo


def dpanel(path, r, title="Details"):
    tab = Table(show_header=False, box=None, pad_edge=False)
    tab.add_column("k", style="dim", no_wrap=True)
    tab.add_column("v", overflow="fold")
    tab.add_row("Path", str(path))
    tab.add_row("Total", f"[bold]{fmtbytes(r.total_bytes)}[/bold]")
    tab.add_row("Files", str(r.total_files))
    tab.add_row("Dirs", str(r.total_dirs))
    if r.skipped:
        tab.add_row("Skipped", f"[yellow]{r.skipped}[/yellow]")
    return Panel(tab, title=title, border_style="bright_black")


def ttable(r, top=12):
    tab = Table(title="Types", box=None, show_header=True, header_style="bold")
    tab.add_column("Ext", style="magenta", no_wrap=True)
    tab.add_column("Size", style="cyan", no_wrap=True)
    tab.add_column("Files", style="dim", justify="right", no_wrap=True)
    items = [(ext, byt, cnt) for ext, (byt, cnt) in r.types.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    for ext, nbytes, cnt in items[:top]:
        tab.add_row(ext, fmtbytes(nbytes), str(cnt))
    return tab


def toptable(r, n=12):
    tab = Table(title=f"Top {n}", box=None, show_header=True, header_style="bold")
    tab.add_column("Size", style="cyan", no_wrap=True)
    tab.add_column("Kind", style="magenta", no_wrap=True)
    tab.add_column("Path", overflow="fold")
    for nbytes, path, kind in r.top_items[:n]:
        tab.add_row(fmtbytes(nbytes), kind, str(path))
    return tab


class DSpy(App[None]):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "rescan", "Rescan"),
        ("/", "focus", "Command"),
    ]
    CSS = "\n  Screen {\n    background: #0b0f14;\n    color: #e6e6e6;\n    layout: vertical;\n  }\n\n  Header {\n    background: #0b0f14;\n    color: #e6e6e6;\n    dock: top;\n    height: 1;\n  }\n\n  Footer {\n    background: #0b0f14;\n    dock: bottom;\n    height: 1;\n  }\n\n  Horizontal {\n    height: 1fr;\n  }\n\n  Tree {\n    background: #0b0f14;\n    border: solid #1f2937;\n    width: 2fr;\n    padding: 0 1;\n  }\n\n  #right {\n    border: solid #1f2937;\n    width: 3fr;\n    layout: vertical;\n  }\n\n  #details {\n    border-bottom: solid #1f2937;\n    height: 12;\n  }\n\n  RichLog {\n    height: 1fr;\n    padding: 0 1;\n  }\n\n  #status {\n    height: 1;\n    padding: 0 1;\n    color: #9ca3af;\n  }\n\n  Input {\n    border: solid #1f2937;\n    background: #0b0f14;\n    dock: bottom;\n    height: 3;\n  }\n  "

    def __init__(self, start_path, opts, *, details_depth=2, details_top=12):
        super().__init__()
        self.cur = start_path
        self.opts = opts
        self.ddep = max(0, details_depth)
        self.dtop = max(0, details_top)
        self.last = None
        self.sel = None
        self.busy = False
        self.busy_msg = ""
        self.spin = 0
        self.progq: queue.Queue[str] = queue.Queue()

    def compose(self):
        yield Header(show_clock=False)
        with Horizontal():
            yield Tree("Scanning…", id="tree")
            with Vertical(id="right"):
                yield Static(id="details")
                yield RichLog(id="log", markup=True, highlight=True)
        yield Static(id="status")
        yield Input(
            placeholder=": cd <path>, depth <n>, top <n>, types on|off, filesonly on|off, system on|off, export <file>, open, rescan, help, quit",
            id="cmd",
        )
        yield Footer()

    async def on_mount(self):
        self.query_one(RichLog).write(
            "[dim]Tip:[/dim] press / to focus command input • r to rescan • q to quit"
        )
        self.set_interval(0.1, self.tick)
        self.run_worker(self.chkupd(), exclusive=False)
        await self.scan()

    def tick(self):
        dirty = False
        while True:
            try:
                msg = self.progq.get_nowait()
            except Exception:
                break
            self.busy_msg = msg
            dirty = True
        if self.busy:
            self.spin += 1
            dirty = True
        if dirty:
            self.rstatus()

    def rstatus(self):
        st = self.query_one("#status", Static)
        if not self.busy:
            st.update("")
            return
        frame = "|/-\\"[self.spin % 4]
        st.update(f"[dim]{frame}[/dim] {self.busy_msg}")

    def setbusy(self, on: bool, msg: str = ""):
        self.busy = on
        if msg:
            self.busy_msg = msg
        if not on:
            self.busy_msg = ""
        self.rstatus()

    def onprog(self, msg: str):
        try:
            self.progq.put_nowait(msg)
        except Exception:
            pass

    async def chkupd(self):
        log = self.query_one(RichLog)
        info = await asyncio.to_thread(lambda: updinfo(__version__, cache_seconds=0))
        if not info:
            return
        if not (info.update_available or info.mandatory):
            return
        if info.mandatory:
            log.write(
                f"[bold red]Update required[/bold red] · current={info.current} · latest={info.latest} · run: diskspy update"
            )
        else:
            log.write(
                f"[bold yellow]Update available[/bold yellow] · current={info.current} · latest={info.latest} · run: diskspy update"
            )

    def action_focus(self):
        self.query_one("#cmd", Input).focus()

    def action_rescan(self):
        self.run_worker(self.scan(), exclusive=True)

    async def scan(self):
        log = self.query_one(RichLog)
        log.write(
            f"[bold]Scanning[/bold] {self.cur} (depth={self.opts.depth}, top={self.opts.top})…"
        )
        self.setbusy(True, f"Scanning… {self.cur}")
        opts = replace(self.opts, progress=self.onprog)
        res = await asyncio.to_thread(scanpath, self.cur, opts)
        self.last = res
        self.sel = self.cur
        self.rtree(res)
        await self.rdet(self.cur)
        self.setbusy(False)
        log.write(
            f"[green]Done[/green] · {fmtbytes(res.total_bytes)} · files={res.total_files} · dirs={res.total_dirs} · skipped={res.skipped}"
        )

    def rtree(self, res):
        tree = self.query_one("#tree", Tree)
        tree.clear()
        label = Text(str(res.root), style="bold")
        label.append(f"  {fmtbytes(res.total_bytes)}", style="dim")
        root = tree.root
        root.set_label(label)
        root.data = (res.root, res.total_bytes)

        def addkids(node, base, lvl):
            if lvl >= self.opts.depth:
                return
            kids = sorted(res.children.get(base, []), key=lambda x: x[1], reverse=True)
            for path, nbytes, _, _ in kids:
                txt = Text(path.name)
                txt.append(f"  {fmtbytes(nbytes)}", style="dim")
                sub = node.add(txt)
                sub.data = (path, nbytes)
                addkids(sub, path, lvl + 1)

        addkids(root, res.root, 0)
        tree.root.expand()

    async def rdet(self, path):
        det = self.query_one("#details", Static)
        self.setbusy(True, f"Scanning… {path}")
        dopts = replace(self.opts, depth=self.ddep, top=self.dtop, progress=self.onprog)
        res = await asyncio.to_thread(scanpath, path, dopts)
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(dpanel(path, res), toptable(res, n=self.dtop))
        grid.add_row(ttable(res, top=self.dtop), Panel("", border_style="bright_black"))
        det.update(grid)
        self.setbusy(False)

    async def on_tree_node_selected(self, event):
        data = event.node.data
        if not data:
            return
        path, _ = data
        if not isinstance(path, Path):
            return
        self.sel = path
        await self.rdet(path)

    async def on_input_submitted(self, event):
        cmdln = (event.value or "").strip()
        if cmdln.startswith(":"):
            cmdln = cmdln[1:].lstrip()
        event.input.value = ""
        if not cmdln:
            return

        log = self.query_one(RichLog)
        log.write(f"[bold cyan]›[/bold cyan] {cmdln}")

        toks = cmdln.split()
        cmd = toks[0].lower()
        args = toks[1:]

        if cmd in ("quit", "exit", "q"):
            self.exit()
            return
        if cmd in ("help", "?"):
            log.write(
                "[bold]Commands[/bold]\n  cd <path|..>        Change root and rescan\n  rescan              Rescan current root\n  depth <n>           Set tree depth (left pane)\n  top <n>             Set top list size\n  types on|off        Toggle types collection\n  filesonly on|off    Top list files only\n  system on|off       Exclude Windows system folders\n  export <file>       Export JSON for selected folder\n  open                Open selected folder in Explorer\n  :q / :r             Vim-style aliases for quit / rescan\n  quit                Exit UI\n"
            )
            return

        if cmd == "open":
            path = self.sel or self.cur
            try:
                if os.name == "nt":
                    os.startfile(str(path))
                    log.write(f"[green]Opened[/green] {path}")
                else:
                    log.write("[yellow]open is Windows-only[/yellow]")
            except Exception as err:
                log.write(f"[red]open failed:[/red] {err}")
            return

        if cmd == "cd":
            if not args:
                log.write("[yellow]Usage:[/yellow] cd <path|..>")
                return
            raw = args[0]
            if raw == "..":
                nxt = self.cur.parent
            else:
                nxt = Path(raw).expanduser()
                if not nxt.is_absolute():
                    nxt = (self.cur / nxt).resolve()
            if not nxt.exists() or not nxt.is_dir():
                log.write(f"[red]Not a folder:[/red] {nxt}")
                return
            self.cur = nxt
            self.run_worker(self.scan(), exclusive=True)
            return

        if cmd == "depth":
            if not args or not args[0].isdigit():
                log.write("[yellow]Usage:[/yellow] depth <n>")
                return
            self.opts = replace(self.opts, depth=max(0, int(args[0])))
            self.run_worker(self.scan(), exclusive=True)
            return

        if cmd == "top":
            if not args or not args[0].isdigit():
                log.write("[yellow]Usage:[/yellow] top <n>")
                return
            self.opts = replace(self.opts, top=max(0, int(args[0])))
            self.run_worker(self.scan(), exclusive=True)
            return

        if cmd == "types":
            if not args or args[0].lower() not in ("on", "off"):
                log.write("[yellow]Usage:[/yellow] types on|off")
                return
            self.opts = replace(self.opts, collect_types=(args[0].lower() == "on"))
            self.run_worker(self.rdet(self.sel or self.cur), exclusive=True)
            log.write(f"[dim]types:[/dim] {args[0].lower()}")
            return

        if cmd == "filesonly":
            if not args or args[0].lower() not in ("on", "off"):
                log.write("[yellow]Usage:[/yellow] filesonly on|off")
                return
            self.opts = replace(self.opts, files_only=(args[0].lower() == "on"))
            self.run_worker(self.scan(), exclusive=True)
            log.write(f"[dim]filesonly:[/dim] {args[0].lower()}")
            return

        if cmd == "system":
            if not args or args[0].lower() not in ("on", "off"):
                log.write("[yellow]Usage:[/yellow] system on|off")
                return
            self.opts = replace(self.opts, exclude_system=(args[0].lower() == "on"))
            self.run_worker(self.scan(), exclusive=True)
            log.write(f"[dim]system:[/dim] {args[0].lower()}")
            return

        if cmd == "export":
            out = args[0] if args else "diskspy.json"
            outp = Path(out).expanduser()
            if not outp.is_absolute():
                outp = (Path.cwd() / outp).resolve()
            self.run_worker(self.doexport(outp), exclusive=True)
            return

        if cmd in ("rescan", "scan", "r"):
            self.run_worker(self.scan(), exclusive=True)
            return

        log.write(f"[yellow]Unknown command:[/yellow] {cmd} (type 'help')")

    async def doexport(self, outp: Path):
        log = self.query_one(RichLog)
        base = self.sel or self.cur
        self.setbusy(True, f"Exporting… {outp}")
        try:
            opts = replace(self.opts, collect_types=True, progress=self.onprog)
            res = await asyncio.to_thread(scanpath, base, opts)
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
            log.write(f"[green]Wrote[/green] {outp}")
        except Exception as err:
            log.write(f"[red]export failed:[/red] {err}")
        finally:
            self.setbusy(False)


def runtui(path, opts):
    if os.name == "nt":
        try:
            import ctypes
            import subprocess

            ctypes.windll.kernel32.SetConsoleTitle("DSpy TUI")
            subprocess.run(
                ["mode", "con:", "cols=220", "lines=50"],
                shell=True,
                capture_output=True,
            )
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)
        except Exception:
            pass
    DSpy(path, opts).run()

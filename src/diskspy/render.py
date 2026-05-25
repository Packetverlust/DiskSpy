from rich.table import Table
from rich.text import Text
from rich.tree import Tree


def fmtbytes(nbytes):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    val = float(nbytes)
    for unit in units:
        if val < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(val)} {unit}"
            return f"{val:.2f} {unit}"
        val /= 1024
    return f"{val:.2f} PB"


def rsum(con, res):
    root = Text(f"{res.root}", style="bold")
    con.print(root)
    con.print(
        f"Total: [bold]{fmtbytes(res.total_bytes)}[/bold] · Files: [bold]{res.total_files}[/bold] · Dirs: [bold]{res.total_dirs}[/bold]"
    )
    if res.skipped:
        con.print(
            f"[yellow]Skipped:[/yellow] {res.skipped} paths (permission / missing)."
        )
        if res.skipped_samples:
            for smp in res.skipped_samples[:6]:
                con.print(f"  [yellow]-[/yellow] {smp}")
            if len(res.skipped_samples) > 6:
                con.print("  ...")


def rtree(con, res, depth):
    con.print()
    con.print("[bold]Tree[/bold]")
    label = f"{res.root}  [dim]{fmtbytes(res.total_bytes)}[/dim]"
    tree = Tree(label, guide_style="dim")

    def addkids(node, base, lvl):
        if lvl >= depth:
            return
        kids = res.children.get(base, [])
        kids = sorted(kids, key=lambda x: x[1], reverse=True)
        for path, nbytes, _, _ in kids:
            nxt = node.add(f"{path.name}  [dim]{fmtbytes(nbytes)}[/dim]")
            addkids(nxt, path, lvl + 1)

    addkids(tree, res.root, 0)
    con.print(tree)


def rtop(con, res, n):
    if n <= 0:
        return
    con.print()
    con.print(f"[bold]Top {n}[/bold]")
    tab = Table(show_header=True, header_style="bold", box=None)
    tab.add_column("Size", style="cyan", no_wrap=True)
    tab.add_column("Kind", style="magenta", no_wrap=True)
    tab.add_column("Path", overflow="fold")
    for nbytes, path, kind in res.top_items[:n]:
        tab.add_row(fmtbytes(nbytes), kind, str(path))
    con.print(tab)


def rtypes(con, res, top=20):
    con.print()
    con.print("[bold]Types[/bold]")
    items = [(ext, nbytes, cnt) for ext, (nbytes, cnt) in res.types.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    items = items[:top]
    tab = Table(show_header=True, header_style="bold", box=None)
    tab.add_column("Ext", style="magenta", no_wrap=True)
    tab.add_column("Size", style="cyan", no_wrap=True)
    tab.add_column("Files", style="dim", justify="right", no_wrap=True)
    tab.add_column("%", style="dim", justify="right", no_wrap=True)
    tot = max(res.total_bytes, 1)
    for ext, nbytes, cnt in items:
        pct = nbytes / tot * 100.0
        tab.add_row(ext, fmtbytes(nbytes), str(cnt), f"{pct:.1f}")
    con.print(tab)

def fmt_bytes(n):
    return fmtbytes(n)


def render_summary(console, r):
    return rsum(console, r)


def render_tree(console, r, depth):
    return rtree(console, r, depth)


def render_top(console, r, n):
    return rtop(console, r, n)


def render_types(console, r, top=20):
    return rtypes(console, r, top=top)

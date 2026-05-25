import fnmatch
import heapq
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ScanOptions:
    depth: int
    top: int
    min_size: int
    include: Tuple[str, ...]
    exclude: Tuple[str, ...]
    follow_symlinks: bool
    collect_types: bool = False
    files_only: bool = False
    exclude_system: bool = False
    progress: object = None


@dataclass
class ScanResult:
    root: Path
    total_bytes: int
    total_files: int
    total_dirs: int
    skipped: int
    skipped_samples: List[str]
    children: Dict[Path, List[Tuple[Path, int, int, int]]]
    top_items: List[Tuple[int, Path, str]]
    types: Dict[str, Tuple[int, int]]


def scanpath(path, opts):
    progress = getattr(opts, "progress", None)
    files_only = bool(getattr(opts, "files_only", False))
    exclude_system = bool(getattr(opts, "exclude_system", False))
    root = path.resolve()
    skipped = 0
    skipped_samples: List[str] = []
    parent: Dict[Path, Path] = {}
    bytes_sum: Dict[Path, int] = {}
    file_cnt: Dict[Path, int] = {}
    dir_cnt: Dict[Path, int] = {}
    children: Dict[Path, List[Tuple[Path, int, int, int]]] = {}
    want_top = int(opts.top) > 0
    file_heap: list[tuple[int, Path, str]] = []
    types = defaultdict(lambda: [0, 0]) if opts.collect_types else None
    rparts = root.parts

    def normpath(p: str) -> str:
        return p.replace("\\", "/").lower()

    def compile_pats(pats: Tuple[str, ...]) -> list[str]:
        out: list[str] = []
        for pat in pats or ():
            for piece in (pat or "").split(","):
                piece = piece.strip()
                if piece:
                    out.append(normpath(piece))
        return out

    excl = compile_pats(opts.exclude)
    incl = compile_pats(opts.include)
    sysdirs: list[str] = []
    if exclude_system and os.name == "nt":
        for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
            val = os.environ.get(key)
            if val:
                sysdirs.append(normpath(str(Path(val).resolve())) + "/")

    def relvl(path):
        return max(0, len(path.parts) - len(rparts))

    def keep(p: str) -> bool:
        sp = normpath(p)
        if sysdirs:
            for sd in sysdirs:
                if sp.startswith(sd):
                    return False
        if exclude_system:
            if "/system volume information" in sp or "/$recycle.bin" in sp:
                return False
        if excl:
            for pat in excl:
                if fnmatch.fnmatch(sp, pat):
                    return False
        if incl:
            for pat in incl:
                if fnmatch.fnmatch(sp, pat):
                    return True
            return False
        return True

    def onerr(err):
        nonlocal skipped
        skipped += 1
        if len(skipped_samples) < 15:
            skipped_samples.append(str(getattr(err, "filename", "unknown")))

    def heap_push(heap: list[tuple[int, Path, str]], item: tuple[int, Path, str]):
        if opts.top <= 0:
            return
        if len(heap) < opts.top:
            heapq.heappush(heap, item)
        else:
            if item[0] > heap[0][0]:
                heapq.heapreplace(heap, item)

    dir_seen = 0
    file_seen = 0
    last_ui = 0.0

    for dirp, dirn, filn in os.walk(
        str(root), topdown=True, onerror=onerr, followlinks=opts.follow_symlinks
    ):
        base = Path(dirp)
        dir_seen += 1
        if progress:
            now = time.time()
            if now - last_ui >= 0.25:
                progress(f"Scanning… dirs={dir_seen} files={file_seen} · {dirp}")
                last_ui = now
        if relvl(base) >= opts.depth:
            dirn[:] = []
        ndirs: List[str] = []
        for name in list(dirn):
            full = os.path.join(dirp, name)
            path = base / name
            try:
                if not keep(full):
                    continue
                if not opts.follow_symlinks and os.path.islink(full):
                    continue
                ndirs.append(name)
                parent[path] = base
            except OSError as err:
                onerr(err)
        dirn[:] = ndirs
        nbytes = 0
        nfiles = 0
        for name in filn:
            full = os.path.join(dirp, name)
            try:
                if not keep(full):
                    continue
                st = os.stat(full)
                size = int(st.st_size)
                nbytes += size
                nfiles += 1
                file_seen += 1
                if want_top and size >= opts.min_size:
                    heap_push(file_heap, (size, Path(full), "file"))
                if types is not None:
                    ext = (os.path.splitext(name)[1].lower() or "<none>").lstrip(".")
                    types[ext][0] += size
                    types[ext][1] += 1
            except (PermissionError, FileNotFoundError, OSError):
                skipped += 1
                if len(skipped_samples) < 15:
                    skipped_samples.append(full)
        bytes_sum[base] = nbytes
        file_cnt[base] = nfiles
        dir_cnt[base] = 0

    dirs = sorted(bytes_sum.keys(), key=relvl, reverse=True)
    for path in dirs:
        if path == root:
            continue
        up = parent.get(path)
        if not up:
            continue
        bytes_sum[up] = bytes_sum.get(up, 0) + bytes_sum.get(path, 0)
        file_cnt[up] = file_cnt.get(up, 0) + file_cnt.get(path, 0)
        dir_cnt[up] = dir_cnt.get(up, 0) + dir_cnt.get(path, 0) + 1

    for path in dirs:
        up = parent.get(path)
        if not up:
            continue
        if relvl(up) < opts.depth:
            children.setdefault(up, []).append(
                (
                    path,
                    bytes_sum.get(path, 0),
                    file_cnt.get(path, 0),
                    dir_cnt.get(path, 0),
                )
            )

    top_items: List[Tuple[int, Path, str]] = []
    if want_top:
        dir_heap: list[tuple[int, Path, str]] = []
        if not files_only:
            for path, nbytes in bytes_sum.items():
                if path != root and nbytes >= opts.min_size:
                    heap_push(dir_heap, (int(nbytes), path, "dir"))
        top_items = sorted(
            [*file_heap, *([] if files_only else dir_heap)],
            key=lambda x: x[0],
            reverse=True,
        )[: opts.top]

    return ScanResult(
        root=root,
        total_bytes=int(bytes_sum.get(root, 0)),
        total_files=int(file_cnt.get(root, 0)),
        total_dirs=int(dir_cnt.get(root, 0)),
        skipped=skipped,
        skipped_samples=skipped_samples,
        children=children,
        top_items=top_items,
        types={}
        if types is None
        else {k: (int(v[0]), int(v[1])) for k, v in types.items()},
    )

def scan_path(path, opts):
    return scanpath(path, opts)

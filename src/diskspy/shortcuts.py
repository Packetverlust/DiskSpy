from pathlib import Path

SHORTCUTS = {
    ":sc": "scan",
    ":scan": "scan",
    ":tr": "tree",
    ":tree": "tree",
    ":ty": "types",
    ":types": "types",
    ":top": "top",
    ":find": "find",
    ":ui": "ui",
    ":tui": "ui",
    ":export": "export",
    ":r": "scan",
    ":rescan": "scan",
    ":d": "--depth",
    ":t": "--top",
    ":topn": "--top",
    ":e": "--elevate",
    ":h": "--help",
    ":help": "--help",
}


def preprocess_argv(argv):
    args = argv
    if len(args) <= 1:
        return args
    if len(args) == 2 and args[1] in (":q", ":quit"):
        return [args[0], "__quit__"]
    out = [args[0]]
    for tok in args[1:]:
        if tok in ("--h", "-H"):
            out.append("--help")
            continue
        rep = SHORTCUTS.get(tok)
        out.append(rep if rep else tok)
    if len(out) == 2 and out[1] == "help":
        return [out[0], "--help"]
    if len(out) >= 2 and out[1] == "find":
        pos = []
        flags = []
        seenfl = False
        for tok in out[2:]:
            if not seenfl and tok.startswith("-"):
                seenfl = True
            (flags if seenfl else pos).append(tok)
        if len(pos) >= 1 and not Path(pos[0]).exists():
            if len(pos) >= 2 and Path(pos[1]).exists() and Path(pos[1]).is_dir():
                pos = [pos[1], pos[0], *pos[2:]]
            else:
                pos = [str(Path.cwd()), *pos]
        out = [out[0], "find", *pos, *flags]
    if len(args) >= 2 and args[1] in (":r", ":rescan"):
        haspth = any(not x.startswith("-") and Path(x).exists() for x in out[2:])
        if not haspth:
            out.append(str(Path.cwd()))
        return out
    return out

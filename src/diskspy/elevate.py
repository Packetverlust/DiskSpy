import os, sys


def isadmin():
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# def runasadmin(argv):
#     if os.name != "nt":
#         raise RuntimeError("--elevate is Windows-only")
#     import ctypes
# 
#     args = [x for x in argv[1:] if x != "--elevate"]
#     if getattr(sys, "frozen", False):
#         exe = sys.executable
#         cmd = " ".join(qarg(x) for x in args)
#     else:
#         exe = sys.executable
#         cmd = " ".join(qarg(x) for x in ["-m", "diskspy", *args])
#     rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, cmd, None, 1)
#     return int(rc)

def runasadmin(argv):
    if os.name != "nt":
        raise RuntimeError("--elevate is Windows-Only")
    
    import ctypes

    args = [x for x in argv[1:] if x != "--elevate"]

    if getattr(sys, "frozen", False):
        exe = sys.executable
        cmd = " ".join(qarg(x) for x in args)
    else:
        exe = sys.executable
        cmd = " ".join(qarg(x) for x in ["-m", "diskspy", *args])

    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        cmd,
        None,
        0, ###
    )

    return int(rc)

def attachPc():
    import ctypes
    import sys

    if sys.platform != "win32":
        return False
    
    k32 = ctypes.windll.kernel32

    k32.FreeConsole()

    if not k32.AttachConsole(-1):
        return False
    
    sys.stdout = open(
        "CONOUT$",
        "w",
        encoding="utf-8",
        buffering=1,
    )

    sys.stderr = open(
        "CONIN$",
        "r",
        encoding="utf-8",
    )

    return True

def qarg(s):
    if not s:
        return '""'
    if any(ch.isspace() for ch in s) or '"' in s:
        return '"' + s.replace('"', '\\"') + '"'
    return s

def is_admin():
    return isadmin()


def relaunch_as_admin(argv):
    return runasadmin(argv)

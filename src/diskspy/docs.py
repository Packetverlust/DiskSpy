DOCS_INDEX = """DiskSpy docs

DiskSpy is a compact Client or Terminal User Interface storage analyzer for Windows.

Docs topics:
  - overview
  - commands
  - flags
  - glossary
  - examples

Use:
  diskspy docs <topic>
"""

DOCS_OVERVIEW = """Overview

DiskSpy scans a folder and reports what takes space:
  - Tree view (folders by size)
  - Top list (largest files/folders)
  - Types view (space by file extension)

It is safe-by-default:
  - Permission errors are skipped (and reported)
  - You can re-run with --elevate to include protected folders on Windows
"""

DOCS_COMMANDS = """Commands

Main command (mix outputs):
  diskspy scan <path> [--tree] [--types] [--top N]

Convenience commands:
  diskspy tree <path>   -> same as: diskspy scan <path> --tree
  diskspy types <path>  -> same as: diskspy scan <path> --types
  diskspy top <path>    -> same as: diskspy scan <path> --top N

Interactive UI:
  diskspy ui <path>     -> Terminal User Interface (folder tree + details + command input)

Utilities:
  diskspy find <path> --name <pattern> [--min-size 10MB]
  diskspy export <path> --out diskspy.json

Self-update (standalone .exe builds only):
  diskspy update           -> update immediately
  diskspy update --prompt  -> ask first

Docs:
  diskspy docs [topic]

Elevation:
  diskspy scan C:\\ --elevate
"""

DOCS_FLAGS = """Flags (most used)

  --depth, -d <N>        Scan depth (how deep we traverse directories)
  --top <N>              Show Top N biggest items (files + dirs)
  --tree / --no-tree     Show/hide the Tree section
  --types / --no-types   Show/hide the Types section
  --default-ignore / --no-default-ignore
                         By default ignores: __pycache__, node_modules, .git, .venv, dist, build
  --min-size <SIZE>      Skip items smaller than SIZE (e.g. 10MB, 500KB)
  --exclude <PATTERNS>   Glob(s) to skip (comma-separated)
  --include <PATTERNS>   Glob(s) to keep (comma-separated)
  --follow-symlinks      Follow symlinks/junctions (default off)
  --name <GLOB>          (find) name glob like *.mp4
  --out <FILE>           (export) output file path

Help:
  --help, -h, :h, :help, --h
"""

DOCS_GLOSSARY = """Glossary

Depth
  How deep DiskSpy scans directories.
  Example: depth=2 scans:
    root/
      child/
        grandchild/
  but does NOT enter great-grandchildren.

Top
  The biggest items by size.
  DiskSpy includes both folders and files in Top.

Types
  Breakdown by file extension (.mp4, .zip, .png, etc.).

Skipped
  Paths DiskSpy couldn't read due to permissions or missing files.
  Use --elevate to retry with admin permissions (Windows).
"""

DOCS_EXAMPLES = """Examples

Scan + show everything:
  diskspy scan C:\\Users --tree --types --top 30

Fast shortcuts:
  diskspy :sc C:\\Users :d 4 :t 30 --types
  diskspy :h

Terminal User Interface:
  diskspy ui C:\\Users
  diskspy :ui C:\\Users

Scan C:\\ and elevate (UAC):
  diskspy scan C:\\ --elevate --depth 4

Exclude common junk:
  diskspy scan C:\\Users --exclude "node_modules,.git,AppData\\\\Local\\\\Temp" --types

Export to JSON (for scripts):
  diskspy export C:\\Users -o diskspy.json
"""

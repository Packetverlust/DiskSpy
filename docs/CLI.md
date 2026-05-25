# DiskSpy CLI docs

You can read docs in two places:
- **Inside the CLI**: `diskspy docs` and `diskspy docs <topic>`
- **In this repo** (this folder)

Install guide: **[INSTALL.md](INSTALL.md)**

## Topics

- `overview`
- `commands`
- `flags`
- `glossary`
- `examples`

## Inside the CLI

```bash
diskspy docs
diskspy docs commands
diskspy docs glossary
```

## Mixing outputs

DiskSpy is designed so you can combine sections in one run:

```bash
diskspy scan C:\Users --tree --types --top 40
```

Shortcuts:
```bash
diskspy :sc C:\Users :d 4 :t 40 --types
```

## Pane UI (TUI)

Launch the interactive UI:

```bash
diskspy ui C:\Users
diskspy :ui C:\Users
```

## Elevation (Windows)

Scanning `C:\` without admin will skip protected folders.

```bash
diskspy scan C:\ --elevate
```

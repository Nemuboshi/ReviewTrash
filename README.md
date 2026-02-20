# Subtitle Proof GUI

A desktop subtitle review tool for `ASS + PNG` workflows, built with PySide6.

## Features

- Load an `.ass` subtitle file and a PNG image directory.
- Save/open project files (`JSON`) to restore subtitle path, image path, and review progress in one click.
- Sync subtitle navigation and screenshot preview by `Dialogue` order.
- Edit and save subtitles with automatic timestamped backup on save.
- Autosave and startup restore via `*.ass.autosave.json`.
- Original/current text diff highlighting.
- Replace in current entry and replace across all entries.
- Reviewed markers, plus quick jump to next unreviewed/modified row.
- Optional auto-mark current row as reviewed when moving to next row.
- Issues panel for parse errors and missing images, with click-to-jump.
- Chunked list rendering, asynchronous image loading, and cache prefetching.
- Top status summary for progress, missing images, and unsaved changes.

## Run

```bash
uv sync
uv run python -m review_trash
```

## Build EXE

```powershell
uv sync
.\scripts\build.ps1 -Mode onedir
```

Release notes: `release/README.md`

## Shortcuts

- `Up` / `Down`: Previous / Next row (when editor is not focused).
- `Ctrl+S`: Save.
- `Ctrl+R`: Toggle reviewed marker.
- `F8`: Jump to next unreviewed row.
- `F9`: Jump to next modified row.

## Project File

- Use **New Project** in the toolbar to select ASS subtitle file, image folder, and project config directory.
- The app creates a project JSON at `<project-dir>/<ass-stem>.subtitle-project.json`.
- Reviewed status changes are saved to the project JSON automatically (no manual project save action).
- Project JSON intentionally stores only:
- ASS file path
- Image directory path
- Reviewed row indexes

## Image Matching Rules

For the `n`-th `Dialogue` row:

1. Match `n.png` first.
2. If not found, match `000n.png` (zero-padded to 4 digits).
3. If neither exists, report as missing in the issues panel.


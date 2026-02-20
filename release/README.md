# Release Build

## Prerequisites

- Windows PowerShell
- `uv` installed
- A DM font `.ttf` file placed in repository root (for example `DMSans-VariableFont_opsz,wght.ttf`)

## Build Commands

```powershell
uv sync
.\scripts\build.ps1 -Mode onedir
```

Optional single-file build:

```powershell
.\scripts\build.ps1 -Mode onefile
```

## Output

- `onedir`: `dist/ReviewTrash/ReviewTrash.exe`
- `onefile`: `dist/ReviewTrash.exe`

## Font Packaging

The build script automatically packages one root-level `.ttf` into:

- `review_trash/assets/fonts/<font-file>.ttf`

Runtime font priority:

1. Bundled font in PyInstaller data path
2. Font next to executable in `review_trash/assets/fonts`
3. Root-level `.ttf` when running from source
4. Fallback family: `Source Han Sans SC`

# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.building.datastruct import TOC


project_root = Path.cwd().resolve()
font_from_env = os.environ.get("REVIEWTRASH_FONT_FILE", "").strip()
if font_from_env:
    font_file = Path(font_from_env)
else:
    font_candidates = sorted((project_root / "review_trash" / "assets" / "fonts").glob("*.ttf"))
    if not font_candidates:
        font_candidates = sorted(project_root.glob("*.ttf"))
    font_file = font_candidates[0] if font_candidates else None

datas = []
if font_file and font_file.exists():
    datas.append((str(font_file.resolve()), "review_trash/assets/fonts"))

a = Analysis(
    [str(project_root / "review_trash" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)


def _norm(text: str) -> str:
    return str(text).replace("\\", "/").lower()


def _drop_binary(entry) -> bool:
    dest = _norm(entry[0])
    src = _norm(entry[1])

    # Keep only qwindows platform plugin.
    if "/pyside6/plugins/platforms/" in src and not src.endswith("/qwindows.dll"):
        return True

    # Drop plugin families we do not use.
    for folder in (
        "/pyside6/plugins/imageformats/",
        "/pyside6/plugins/iconengines/",
        "/pyside6/plugins/platforminputcontexts/",
        "/pyside6/plugins/networkinformation/",
        "/pyside6/plugins/tls/",
        "/pyside6/plugins/generic/",
    ):
        if folder in src:
            return True

    # Drop heavy Qt DLLs that are not needed by a pure QWidget + QImage app.
    for dll in (
        "/qt6quick.dll",
        "/qt6qml.dll",
        "/qt6qmlmeta.dll",
        "/qt6qmlmodels.dll",
        "/qt6qmlworkerscript.dll",
        "/qt6virtualkeyboard.dll",
        "/qt6pdf.dll",
        "/qt6svg.dll",
    ):
        if src.endswith(dll):
            return True

    # Defensive drop by destination name as well.
    for dll_name in (
        "qt6quick.dll",
        "qt6qml.dll",
        "qt6qmlmeta.dll",
        "qt6qmlmodels.dll",
        "qt6qmlworkerscript.dll",
        "qt6virtualkeyboard.dll",
        "qt6pdf.dll",
        "qt6svg.dll",
    ):
        if dest.endswith("/" + dll_name):
            return True

    return False


def _drop_data(entry) -> bool:
    src = _norm(entry[1])
    # Remove optional translations to reduce size.
    return "/pyside6/translations/" in src


a.binaries = TOC([entry for entry in a.binaries if not _drop_binary(entry)])
a.datas = TOC([entry for entry in a.datas if not _drop_data(entry)])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ReviewTrash",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-onefile}" # onefile | onedir
TRIM_QT="${TRIM_QT:-1}" # 1=on, 0=off
USE_UPX="${USE_UPX:-1}" # 1=on, 0=off

if [[ "$MODE" != "onefile" && "$MODE" != "onedir" ]]; then
  echo "Usage: ./scripts/build.sh [onefile|onedir]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p build dist

mapfile -t FONT_CANDIDATES < <(find review_trash/assets/fonts -maxdepth 1 -type f -name '*.ttf' 2>/dev/null | sort)
if [[ ${#FONT_CANDIDATES[@]} -eq 0 ]]; then
  mapfile -t FONT_CANDIDATES < <(find . -maxdepth 1 -type f -name '*.ttf' | sort)
fi
if [[ ${#FONT_CANDIDATES[@]} -eq 0 ]]; then
  echo "No .ttf file found. Put your DM font in review_trash/assets/fonts or project root." >&2
  exit 1
fi

FONT_FILE="${FONT_CANDIDATES[0]}"
echo "Using font file: $(basename "$FONT_FILE")"

UPX_ARGS=()
if [[ "$USE_UPX" == "1" ]] && command -v upx >/dev/null 2>&1; then
  UPX_DIR="$(dirname "$(command -v upx)")"
  echo "Using UPX: $(command -v upx)"
  UPX_ARGS+=(--upx-dir "$UPX_DIR")
elif [[ "$USE_UPX" == "1" ]]; then
  echo "WARNING: UPX is not installed; skipping UPX compression." >&2
fi

if [[ "$MODE" == "onefile" ]]; then
  REVIEWTRASH_FONT_FILE="$FONT_FILE" uv run pyinstaller ./scripts/release_onefile.spec \
    --clean \
    --noconfirm \
    "${UPX_ARGS[@]}"
  exit 0
fi

ADD_DATA="${FONT_FILE};review_trash/assets/fonts"
TRIM_ARGS=()
if [[ "$TRIM_QT" == "1" ]]; then
  TRIM_ARGS+=(
    --exclude-module PySide6.QtQml
    --exclude-module PySide6.QtQuick
    --exclude-module PySide6.QtPdf
    --exclude-module PySide6.QtVirtualKeyboard
    --exclude-module PySide6.QtWebEngineCore
    --exclude-module PySide6.QtWebEngineWidgets
    --exclude-module PySide6.QtWebChannel
    --exclude-module PySide6.QtOpenGL
    --exclude-module PySide6.QtOpenGLWidgets
    --exclude-module PySide6.QtSvg
    --exclude-module PySide6.QtBluetooth
    --exclude-module PySide6.QtNfc
    --exclude-module PySide6.QtPositioning
    --exclude-module PySide6.QtLocation
    --exclude-module PySide6.QtMultimedia
    --exclude-module PySide6.QtMultimediaWidgets
    --exclude-module PySide6.QtDesigner
    --exclude-module PySide6.QtHelp
    --exclude-module PySide6.QtTest
    --exclude-module PySide6.QtXml
    --exclude-module PySide6.QtSql
    --exclude-module PySide6.QtDBus
  )
fi

uv run pyinstaller review_trash/__main__.py \
  --name ReviewTrash \
  --windowed \
  --onedir \
  --clean \
  --noconfirm \
  --optimize 2 \
  --add-data "$ADD_DATA" \
  "${TRIM_ARGS[@]}" \
  "${UPX_ARGS[@]}"

#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-onefile}" # onefile | onedir
USE_UPX="${USE_UPX:-1}" # 1=on, 0=off

if [[ "$MODE" != "onefile" ]]; then
  echo "Usage: ./scripts/build.sh [onefile]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SPEC_PATH="./scripts/release_windows.spec"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Spec file not found: $SPEC_PATH" >&2
  exit 1
fi

export REVIEWTRASH_USE_UPX="$USE_UPX"

mkdir -p build dist
uv run pyinstaller "$SPEC_PATH" --clean --noconfirm

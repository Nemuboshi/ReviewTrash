from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageMatchResult:
    path: Path | None
    expected_names: list[str]


class ImageMatcher:
    def __init__(self) -> None:
        self._root: Path | None = None
        self._numeric_pngs: dict[int, list[Path]] = {}

    @property
    def root(self) -> Path | None:
        return self._root

    def set_directory(self, path: str | Path) -> None:
        """Index numeric PNG files once so matching stays O(1) per lookup."""
        root = Path(path)
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Image directory not found: {root}")

        self._root = root
        self._numeric_pngs = {}

        for file_path in root.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() != ".png":
                continue
            if not file_path.stem.isdigit():
                continue

            number = int(file_path.stem)
            self._numeric_pngs.setdefault(number, []).append(file_path)

    def count_png_files(self) -> int:
        return sum(len(files) for files in self._numeric_pngs.values())

    def match(self, line_number: int) -> ImageMatchResult:
        expected = [f"{line_number}.png", f"{line_number:04d}.png"]
        candidates = self._numeric_pngs.get(line_number, [])
        if not candidates:
            return ImageMatchResult(path=None, expected_names=expected)
        return ImageMatchResult(path=self._pick_candidate(candidates, line_number), expected_names=expected)

    @staticmethod
    def _pick_candidate(candidates: list[Path], line_number: int) -> Path:
        """Prefer exact `N.png`, then `000N.png`, then deterministic fallback."""
        target_plain = f"{line_number}.png"
        target_padded = f"{line_number:04d}.png"

        ranked = sorted(
            candidates,
            key=lambda path: (
                0
                if path.name.lower() == target_plain.lower()
                else 1
                if path.name.lower() == target_padded.lower()
                else 2,
                len(path.stem),
                path.name.lower(),
            ),
        )
        return ranked[0]

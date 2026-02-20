from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


def build_project_path(ass_path: Path, project_dir: Path) -> Path:
    """Build default project config file path from ASS stem and project directory."""
    return project_dir / f"{ass_path.stem}.subtitle-project.json"


@dataclass
class ProjectData:
    ass_path: Path
    image_dir: Path
    reviewed_indexes: list[int]


class ProjectStore:
    def write(self, project_path: str | Path, data: ProjectData) -> Path:
        """Persist project state with relative paths when possible."""
        path = Path(project_path)
        base = path.parent
        payload = {
            "ass_path": self._to_rel(base, data.ass_path),
            "image_dir": self._to_rel(base, data.image_dir),
            "reviewed_indexes": [int(i) for i in data.reviewed_indexes],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read(self, project_path: str | Path) -> ProjectData | None:
        """Load project state and normalize path fields to absolute paths."""
        path = Path(project_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            base = path.parent
            ass_path = self._to_abs(base, str(payload.get("ass_path", "")))
            image_dir = self._to_abs(base, str(payload.get("image_dir", "")))
            reviewed_indexes = [int(i) for i in payload.get("reviewed_indexes", [])]
            return ProjectData(
                ass_path=ass_path,
                image_dir=image_dir,
                reviewed_indexes=reviewed_indexes,
            )
        except Exception:
            return None

    @staticmethod
    def _to_rel(base: Path, value: Path) -> str:
        try:
            return str(value.resolve().relative_to(base.resolve()))
        except Exception:
            return str(value.resolve())

    @staticmethod
    def _to_abs(base: Path, value: str) -> Path:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return (base / candidate).resolve()

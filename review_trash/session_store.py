from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from .ass_parser import AssDocument


@dataclass
class SessionSnapshot:
    entries: list[str]
    reviewed_indexes: list[int]
    current_index: int


class SessionSnapshotStore:
    def snapshot_path_for(self, ass_path: str | Path) -> Path:
        path = Path(ass_path)
        return path.with_suffix(path.suffix + ".autosave.json")

    def write_snapshot(
        self,
        document: AssDocument,
        reviewed_indexes: Iterable[int],
        current_index: int,
    ) -> Path:
        """Persist volatile editor state for crash/close recovery."""
        path = self.snapshot_path_for(document.path)
        payload = {
            "entries": [entry.text_current for entry in document.dialogue_entries],
            "reviewed_indexes": sorted(set(int(i) for i in reviewed_indexes)),
            "current_index": int(current_index),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_snapshot(self, ass_path: str | Path) -> SessionSnapshot | None:
        """Return autosave payload when valid, otherwise `None`."""
        path = self.snapshot_path_for(ass_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entries = payload.get("entries", [])
            reviewed_indexes = payload.get("reviewed_indexes", [])
            current_index = int(payload.get("current_index", 0))
            if not isinstance(entries, list):
                return None
            return SessionSnapshot(
                entries=[str(text) for text in entries],
                reviewed_indexes=[int(i) for i in reviewed_indexes],
                current_index=current_index,
            )
        except Exception:
            return None

    def clear_snapshot(self, ass_path: str | Path) -> None:
        path = self.snapshot_path_for(ass_path)
        if path.exists():
            path.unlink()

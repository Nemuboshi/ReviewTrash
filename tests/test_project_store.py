from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from review_trash.project_store import ProjectData, ProjectStore, build_project_path


ASS_SAMPLE_VALID = """[Script Info]
Title: Demo
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello
Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,World
"""


class ProjectStoreTests(unittest.TestCase):
    def test_build_project_path_uses_ass_stem_and_project_dir(self) -> None:
        ass_path = Path("D:/work/subs/episode01.ass")
        project_dir = Path("D:/work/projects")
        expected = project_dir / "episode01.subtitle-project.json"
        self.assertEqual(expected, build_project_path(ass_path, project_dir))

    def test_save_and_load_project_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ass_path = root / "sub.ass"
            image_dir = root / "images"
            image_dir.mkdir()
            ass_path.write_text(ASS_SAMPLE_VALID, encoding="utf-8")

            project_path = root / "session.subtitle-project.json"
            store = ProjectStore()
            data = ProjectData(
                ass_path=ass_path,
                image_dir=image_dir,
                reviewed_indexes=[0, 1],
            )
            store.write(project_path, data)

            payload = json.loads(project_path.read_text(encoding="utf-8"))
            self.assertEqual({"ass_path", "image_dir", "reviewed_indexes"}, set(payload.keys()))

            loaded = store.read(project_path)

            assert loaded is not None
            self.assertEqual(ass_path.resolve(), loaded.ass_path.resolve())
            self.assertEqual(image_dir.resolve(), loaded.image_dir.resolve())
            self.assertEqual([0, 1], loaded.reviewed_indexes)

    def test_load_returns_none_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "broken.subtitle-project.json"
            project_path.write_text("{ nope ", encoding="utf-8")

            store = ProjectStore()
            self.assertIsNone(store.read(project_path))


if __name__ == "__main__":
    unittest.main()

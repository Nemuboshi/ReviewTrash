from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from review_trash.ass_parser import AssDocument
from review_trash.session_store import SessionSnapshotStore


ASS_SAMPLE_VALID = """[Script Info]
Title: Demo
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello
Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,World
"""


ASS_SAMPLE_WITH_BAD_LINE = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,OK
Dialogue: 0,0:00:04.00
Dialogue: 0,0:00:05.00,0:00:06.00,Default,,0,0,0,,Still OK
"""


class AssParserBehaviorTests(unittest.TestCase):
    def test_malformed_dialogue_is_recorded_as_issue_and_parse_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ass_path = Path(tmpdir) / "bad.ass"
            ass_path.write_text(ASS_SAMPLE_WITH_BAD_LINE, encoding="utf-8")

            document = AssDocument.load(ass_path)

            self.assertEqual(2, len(document.dialogue_entries))
            self.assertGreaterEqual(len(document.issues), 1)
            self.assertIn("Malformed Dialogue line", document.issues[0].message)

    def test_save_creates_timestamped_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ass_path = Path(tmpdir) / "demo.ass"
            ass_path.write_text(ASS_SAMPLE_VALID, encoding="utf-8")
            document = AssDocument.load(ass_path)
            document.update_entry(0, "Hello Updated")

            backup_path = document.save_with_backup()

            self.assertTrue(backup_path.exists())
            self.assertTrue(backup_path.name.startswith("demo.ass."))
            self.assertTrue(backup_path.name.endswith(".bak"))


class SessionStoreTests(unittest.TestCase):
    def test_snapshot_write_read_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ass_path = Path(tmpdir) / "demo.ass"
            ass_path.write_text(ASS_SAMPLE_VALID, encoding="utf-8")
            document = AssDocument.load(ass_path)
            document.update_entry(1, "World Updated")

            store = SessionSnapshotStore()
            snapshot_path = store.snapshot_path_for(ass_path)

            store.write_snapshot(document, reviewed_indexes={1}, current_index=1)
            self.assertTrue(snapshot_path.exists())

            snapshot = store.read_snapshot(ass_path)
            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(1, snapshot.current_index)
            self.assertEqual({1}, set(snapshot.reviewed_indexes))
            self.assertEqual("World Updated", snapshot.entries[1])

            store.clear_snapshot(ass_path)
            self.assertFalse(snapshot_path.exists())

    def test_read_snapshot_returns_none_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ass_path = Path(tmpdir) / "demo.ass"
            ass_path.write_text(ASS_SAMPLE_VALID, encoding="utf-8")
            snapshot_path = ass_path.with_suffix(ass_path.suffix + ".autosave.json")
            snapshot_path.write_text("{ not-json ", encoding="utf-8")

            store = SessionSnapshotStore()
            self.assertIsNone(store.read_snapshot(ass_path))


if __name__ == "__main__":
    unittest.main()

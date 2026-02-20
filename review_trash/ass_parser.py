from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import shutil
from typing import Iterable


_DIALOGUE_PREFIX = re.compile(r"^(\s*Dialogue\s*:\s*)(.*)$", re.IGNORECASE)
_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp932", "gb18030")


@dataclass
class AssEntry:
    index: int
    line_index: int
    start: str
    end: str
    text_original: str
    text_current: str
    prefix: str
    newline: str
    dirty: bool = False
    reviewed: bool = False


@dataclass
class AssIssue:
    line_index: int
    message: str


@dataclass
class AssDocument:
    path: Path
    encoding: str
    lines: list[str]
    dialogue_entries: list[AssEntry]
    issues: list[AssIssue]

    @classmethod
    def load(cls, path: str | Path) -> "AssDocument":
        """Load an ASS file with encoding fallback and parse dialogue lines."""
        ass_path = Path(path)
        content, encoding = _read_with_fallback(ass_path)
        lines = content.splitlines(keepends=True)
        dialogue_entries, issues = _parse_dialogue_entries(lines)
        return cls(path=ass_path, encoding=encoding, lines=lines, dialogue_entries=dialogue_entries, issues=issues)

    def update_entry(self, entry_index: int, new_text: str) -> None:
        entry = self.dialogue_entries[entry_index]
        entry.text_current = new_text
        entry.dirty = entry.text_current != entry.text_original

    def dirty_count(self) -> int:
        return sum(1 for entry in self.dialogue_entries if entry.dirty)

    def save_with_backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.path.with_name(f"{self.path.name}.{stamp}.bak")
        shutil.copy2(self.path, backup_path)

        output_lines = list(self.lines)
        for entry in self.dialogue_entries:
            output_lines[entry.line_index] = f"{entry.prefix}{entry.text_current}{entry.newline}"

        self.path.write_text("".join(output_lines), encoding=self.encoding)
        for entry in self.dialogue_entries:
            entry.text_original = entry.text_current
            entry.dirty = False
        self.lines = output_lines
        return backup_path


def _read_with_fallback(path: Path) -> tuple[str, str]:
    """Try common encodings and return the first successful decode."""
    last_error: Exception | None = None
    for encoding in _ENCODING_CANDIDATES:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("No encoding candidates were available.")


def _parse_dialogue_entries(lines: Iterable[str]) -> tuple[list[AssEntry], list[AssIssue]]:
    """Parse Dialogue rows while keeping malformed lines as recoverable issues."""
    entries: list[AssEntry] = []
    issues: list[AssIssue] = []
    for line_index, raw_line in enumerate(lines):
        line_text, newline = _split_newline(raw_line)
        prefix_match = _DIALOGUE_PREFIX.match(line_text)
        if not prefix_match:
            continue

        body = prefix_match.group(2)
        parts = body.split(",", 9)
        if len(parts) < 10:
            issues.append(
                AssIssue(
                    line_index=line_index,
                    message=f"Malformed Dialogue line at line {line_index + 1}: missing fields.",
                )
            )
            continue

        prefix = f"{prefix_match.group(1)}{','.join(parts[:9])},"
        text = parts[9]
        entries.append(
            AssEntry(
                index=len(entries) + 1,
                line_index=line_index,
                start=parts[1].strip(),
                end=parts[2].strip(),
                text_original=text,
                text_current=text,
                prefix=prefix,
                newline=newline,
            )
        )
    return entries, issues


def _split_newline(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    return raw_line, ""

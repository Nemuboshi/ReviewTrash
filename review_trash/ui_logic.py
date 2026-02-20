from __future__ import annotations

ENTER_KEYS = {16777220, 16777221}


def should_mark_reviewed_on_next(auto_review_enabled: bool, current_row: int, total_rows: int) -> bool:
    """Decide if moving to next row should toggle reviewed state for current row."""
    if not auto_review_enabled:
        return False
    if current_row < 0:
        return False
    return current_row + 1 < total_rows


def should_enter_go_next(key: int) -> bool:
    """Return true for Enter keys used as quick-next shortcuts."""
    return key in ENTER_KEYS

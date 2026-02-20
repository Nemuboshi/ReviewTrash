from __future__ import annotations

import unittest

from review_trash.ui_logic import ENTER_KEYS, should_mark_reviewed_on_next, should_enter_go_next


class UiLogicTests(unittest.TestCase):
    def test_auto_review_marks_when_enabled_and_next_exists(self) -> None:
        self.assertTrue(should_mark_reviewed_on_next(True, 0, 3))

    def test_auto_review_does_not_mark_when_disabled(self) -> None:
        self.assertFalse(should_mark_reviewed_on_next(False, 0, 3))

    def test_auto_review_does_not_mark_on_last_row(self) -> None:
        self.assertFalse(should_mark_reviewed_on_next(True, 2, 3))

    def test_return_keys_trigger_next_navigation(self) -> None:
        for key in ENTER_KEYS:
            self.assertTrue(should_enter_go_next(key))

    def test_non_return_key_does_not_trigger_next_navigation(self) -> None:
        self.assertFalse(should_enter_go_next(ord("A")))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QToolBar

from . import ui_strings as S


def build_main_toolbar(
    window: QMainWindow,
    on_new_project: Callable[[], None],
    on_open_project: Callable[[], None],
    on_save_subtitle: Callable[[], None],
) -> None:
    toolbar = QToolBar("Main")
    toolbar.setMovable(False)
    window.addToolBar(toolbar)

    new_project_action = QAction(S.ACT_NEW_PROJECT, window)
    new_project_action.triggered.connect(on_new_project)
    toolbar.addAction(new_project_action)

    open_project_action = QAction(S.ACT_OPEN_PROJECT, window)
    open_project_action.triggered.connect(on_open_project)
    toolbar.addAction(open_project_action)

    save_action = QAction(S.ACT_SAVE_SUBTITLE, window)
    save_action.setShortcut(QKeySequence.Save)
    save_action.triggered.connect(on_save_subtitle)
    toolbar.addAction(save_action)

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import ui_strings as S


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(S.DLG_NEW_PROJECT_TITLE)
        self.resize(620, 180)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.ass_input = QLineEdit()
        self.image_dir_input = QLineEdit()
        self.project_dir_input = QLineEdit()

        root.addWidget(self._build_row(S.LBL_ASS_SUBTITLE, self.ass_input, self._browse_ass))
        root.addWidget(self._build_row(S.LBL_IMAGE_FOLDER, self.image_dir_input, self._browse_image_dir))
        root.addWidget(self._build_row(S.LBL_PROJECT_CONFIG_DIR, self.project_dir_input, self._browse_project_dir))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_row(self, label_text: str, input_box: QLineEdit, browse_callback) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setMinimumWidth(110)
        browse_button = QPushButton(S.BTN_BROWSE)
        browse_button.clicked.connect(browse_callback)
        layout.addWidget(label)
        layout.addWidget(input_box, stretch=1)
        layout.addWidget(browse_button)
        return row

    def _browse_ass(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, S.DLG_SELECT_ASS, "", S.DLG_ASS_FILTER)
        if file_path:
            self.ass_input.setText(file_path)

    def _browse_image_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, S.DLG_SELECT_PNG_DIR)
        if directory:
            self.image_dir_input.setText(directory)

    def _browse_project_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, S.DLG_SELECT_PROJECT_DIR)
        if directory:
            self.project_dir_input.setText(directory)

    def ass_path(self) -> Path:
        return Path(self.ass_input.text().strip())

    def image_dir(self) -> Path:
        return Path(self.image_dir_input.text().strip())

    def project_dir(self) -> Path:
        return Path(self.project_dir_input.text().strip())


class ReplaceDialog(QDialog):
    def __init__(self, find_text: str = "", replace_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(S.DLG_REPLACE_TITLE)
        self.resize(620, 150)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.find_input = QLineEdit(find_text)
        self.find_input.setPlaceholderText(S.LBL_FIND)
        self.replace_input = QLineEdit(replace_text)
        self.replace_input.setPlaceholderText(S.LBL_REPLACE_WITH)
        root.addWidget(self._build_row(S.LBL_FIND, self.find_input))
        root.addWidget(self._build_row(S.LBL_REPLACE, self.replace_input))

        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        self.replace_current_button = QPushButton(S.BTN_REPLACE_CURRENT)
        self.replace_all_button = QPushButton(S.BTN_REPLACE_ALL)
        self.close_button = QPushButton(S.BTN_CLOSE)
        self.close_button.clicked.connect(self.reject)
        actions_layout.addWidget(self.replace_current_button)
        actions_layout.addWidget(self.replace_all_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.close_button)
        root.addWidget(actions)

    def _build_row(self, label_text: str, input_box: QLineEdit) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(70)
        layout.addWidget(label)
        layout.addWidget(input_box, stretch=1)
        return row

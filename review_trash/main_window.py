from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from collections.abc import Callable
import difflib
from html import escape
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .ass_parser import AssDocument, AssEntry
from .dialogs import NewProjectDialog, ReplaceDialog
from .image_matcher import ImageMatcher
from .project_store import ProjectData, ProjectStore, build_project_path
from .session_store import SessionSnapshotStore
from .toolbar import build_main_toolbar
from .ui_logic import should_enter_go_next, should_mark_reviewed_on_next
from . import ui_strings as S


class FocusLabel(QLabel):
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(event)


class ImageLoadSignals(QObject):
    loaded = Signal(int, str, QImage, str, bool)


class ImageLoadTask(QRunnable):
    def __init__(self, request_id: int, path: Path, for_display: bool) -> None:
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.for_display = for_display
        self.signals = ImageLoadSignals()

    def run(self) -> None:
        """Decode the image off the UI thread and return the result via signal."""
        try:
            qimage = QImage(str(self.path))
            if qimage.isNull():
                raise RuntimeError(f"Failed to decode image: {self.path}")
            self.signals.loaded.emit(self.request_id, str(self.path), qimage, "", self.for_display)
        except Exception as exc:
            self.signals.loaded.emit(self.request_id, str(self.path), QImage(), str(exc), self.for_display)


@dataclass
class SessionState:
    ass_path: Path | None = None
    image_dir: Path | None = None
    current_index: int = 0


class SubtitleEditor(QTextEdit):
    go_next_requested = Signal()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if should_enter_go_next(event.key()):
            self.go_next_requested.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    LIST_CHUNK_SIZE = 250
    IMAGE_CACHE_MAX = 64
    AUTOSAVE_INTERVAL_MS = 45_000

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(S.APP_TITLE)
        self.resize(1400, 880)

        self.ass_doc: AssDocument | None = None
        self.image_matcher = ImageMatcher()
        self.snapshot_store = SessionSnapshotStore()
        self.project_store = ProjectStore()
        self.session = SessionState()
        self.project_path: Path | None = None
        self._current_image: QImage | None = None
        self._updating_ui = False
        self._missing_count = 0
        self._missing_indexes: set[int] = set()
        self._dirty_count = 0
        self._reviewed_indexes: set[int] = set()
        self._image_cache: OrderedDict[str, QImage] = OrderedDict()
        self._thread_pool = QThreadPool.globalInstance()
        self._request_id = 0
        self._active_display_request_id = -1
        self._pending_tasks: dict[int, ImageLoadTask] = {}
        self._list_building_entries: list[AssEntry] = []
        self._list_build_cursor = 0
        self._list_target_row = 0
        self._last_find_text = ""
        self._last_replace_text = ""

        self._build_ui()
        self._bind_shortcuts()
        self._apply_styles()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(self.AUTOSAVE_INTERVAL_MS)
        self.autosave_timer.timeout.connect(self._auto_save_snapshot)
        self.autosave_timer.start()

        self._update_status(S.STATUS_INIT)

    def _build_ui(self) -> None:
        self._build_toolbar()

        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        progress_panel = QWidget()
        progress_layout = QHBoxLayout(progress_panel)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_info_label = QLabel(S.UI_PROGRESS_ZERO)
        self.quick_stats_label = QLabel(S.UI_STATS_ZERO)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        progress_layout.addWidget(self.progress_info_label)
        progress_layout.addWidget(self.quick_stats_label)
        root_layout.addWidget(progress_panel)

        outer_splitter = QSplitter(Qt.Horizontal)

        left_splitter = QSplitter(Qt.Vertical)
        self.subtitle_list = QListWidget()
        self.subtitle_list.currentRowChanged.connect(self._on_list_changed)
        left_splitter.addWidget(self._build_card(S.LBL_SUBTITLE_INDEX, self.subtitle_list))

        self.issue_list = QListWidget()
        self.issue_list.itemClicked.connect(self._on_issue_clicked)
        left_splitter.addWidget(self._build_card(S.LBL_ISSUES, self.issue_list))
        left_splitter.setSizes([560, 220])
        outer_splitter.addWidget(left_splitter)

        right_splitter = QSplitter(Qt.Vertical)

        self.image_label = FocusLabel(S.LBL_NO_IMAGE)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(320)
        self.image_label.setObjectName("previewLabel")
        self.image_label.setFocusPolicy(Qt.ClickFocus)
        right_splitter.addWidget(self._build_card(S.LBL_IMAGE_PREVIEW, self.image_label))

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        nav_row = QWidget()
        nav_layout = QHBoxLayout(nav_row)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)

        self.prev_button = QPushButton(S.BTN_PREVIOUS)
        self.prev_button.clicked.connect(self.go_prev)
        self.next_button = QPushButton(S.BTN_NEXT)
        self.next_button.clicked.connect(self.go_next)
        self.toggle_reviewed_button = QPushButton(S.BTN_TOGGLE_REVIEWED)
        self.toggle_reviewed_button.clicked.connect(self.toggle_reviewed)
        self.auto_review_on_next_checkbox = QCheckBox(S.BTN_AUTO_REVIEW)
        self.auto_review_on_next_checkbox.setChecked(True)
        self.next_unreviewed_button = QPushButton(S.BTN_NEXT_UNREVIEWED)
        self.next_unreviewed_button.clicked.connect(self.go_next_unreviewed)
        self.next_modified_button = QPushButton(S.BTN_NEXT_MODIFIED)
        self.next_modified_button.clicked.connect(self.go_next_modified)
        self.replace_button = QPushButton(S.BTN_REPLACE)
        self.replace_button.clicked.connect(self.open_replace_dialog)

        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.toggle_reviewed_button)
        nav_layout.addWidget(self.auto_review_on_next_checkbox)
        nav_layout.addWidget(self.next_unreviewed_button)
        nav_layout.addWidget(self.next_modified_button)
        nav_layout.addWidget(self.replace_button)
        editor_layout.addWidget(nav_row)

        self.editor = SubtitleEditor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.go_next_requested.connect(self.go_next)
        self.editor.setFocusPolicy(Qt.ClickFocus)
        editor_layout.addWidget(self._build_card(S.LBL_SUBTITLE_TEXT, self.editor))

        diff_splitter = QSplitter(Qt.Horizontal)
        self.original_view = QTextEdit()
        self.original_view.setReadOnly(True)
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        diff_splitter.addWidget(self._build_card(S.LBL_ORIGINAL, self.original_view))
        diff_splitter.addWidget(self._build_card(S.LBL_DIFF, self.diff_view))
        diff_splitter.setSizes([300, 350])
        editor_layout.addWidget(diff_splitter)

        right_splitter.addWidget(editor_panel)
        right_splitter.setSizes([400, 420])

        outer_splitter.addWidget(right_splitter)
        outer_splitter.setSizes([470, 940])
        root_layout.addWidget(outer_splitter)

        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())

    def _build_card(self, title: str, widget: QWidget) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        layout.addWidget(widget)
        return frame

    def _build_toolbar(self) -> None:
        build_main_toolbar(self, self.new_project, self.open_project_file, self.save_ass)

    def new_project(self) -> None:
        dialog = NewProjectDialog(self)
        if dialog.exec() != NewProjectDialog.DialogCode.Accepted:
            return

        ass_path = dialog.ass_path()
        image_dir = dialog.image_dir()
        project_dir = dialog.project_dir()
        if not ass_path.exists() or not ass_path.is_file():
            self._error(S.ERR_ASS_FILE_NOT_FOUND.format(ass_path=ass_path))
            return
        if not image_dir.exists() or not image_dir.is_dir():
            self._error(S.ERR_IMAGE_DIRECTORY_NOT_FOUND.format(image_dir=image_dir))
            return
        if not project_dir.exists() or not project_dir.is_dir():
            self._error(S.ERR_PROJECT_CONFIG_DIR_NOT_FOUND.format(project_dir=project_dir))
            return

        if not self._load_ass_document(ass_path, restore_snapshot=True):
            return
        try:
            self.image_matcher.set_directory(image_dir)
        except Exception as exc:
            self._error(S.ERR_IMAGE_DIR_LOAD_FAILED.format(exc=exc))
            return

        self.session.image_dir = image_dir
        self.project_path = build_project_path(ass_path, project_dir)
        self._image_cache.clear()
        self._recount_missing()
        self._update_preview_for_current()
        self._save_project_state(show_errors=True)
        self._update_status(S.STATUS_PROJECT_INITIALIZED.format(project_path=self.project_path))

    def _bind_shortcuts(self) -> None:
        up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self)
        up_shortcut.setContext(Qt.ApplicationShortcut)
        up_shortcut.activated.connect(self._go_prev_if_editor_not_focused)

        down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self)
        down_shortcut.setContext(Qt.ApplicationShortcut)
        down_shortcut.activated.connect(self._go_next_if_editor_not_focused)

        reviewed_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        reviewed_shortcut.setContext(Qt.ApplicationShortcut)
        reviewed_shortcut.activated.connect(self.toggle_reviewed)

        next_unreviewed_shortcut = QShortcut(QKeySequence(Qt.Key_F8), self)
        next_unreviewed_shortcut.setContext(Qt.ApplicationShortcut)
        next_unreviewed_shortcut.activated.connect(self.go_next_unreviewed)

        next_modified_shortcut = QShortcut(QKeySequence(Qt.Key_F9), self)
        next_modified_shortcut.setContext(Qt.ApplicationShortcut)
        next_modified_shortcut.activated.connect(self.go_next_modified)

    def _apply_styles(self) -> None:
        font = QFont()
        font.setFamilies(self._resolve_app_font_families())
        font.setPointSize(11)
        self.setFont(font)

        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fa; }
            QToolBar {
                spacing: 6px;
                padding: 4px;
                background: #ffffff;
                border: 1px solid #d6dee8;
                border-radius: 6px;
            }
            QStatusBar { font-size: 12px; color: #243447; }
            QFrame#card {
                background: #ffffff;
                border: 1px solid #d6dee8;
                border-radius: 7px;
            }
            QLabel#cardTitle {
                color: #1d4e89;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#previewLabel {
                color: #526275;
                border: 1px dashed #9cb1c8;
                border-radius: 6px;
                background: #edf3fb;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #c8d4e2;
                border-radius: 6px;
                padding: 5px;
                selection-background-color: #2d79d5;
                selection-color: #ffffff;
                font-size: 13px;
                line-height: 1.45;
            }
            QTextEdit, QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c8d4e2;
                border-radius: 6px;
                padding: 5px;
            }
            QPushButton {
                background: #2d79d5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2567b6; }
            QPushButton:disabled { background: #9ab0ca; }
            QProgressBar {
                border: 1px solid #c8d4e2;
                border-radius: 6px;
                text-align: center;
                background: #ffffff;
            }
            QProgressBar::chunk {
                background: #2d79d5;
                border-radius: 6px;
            }
            """
        )
        editor_font = QFont(self.font())
        editor_font.setPointSizeF(self.font().pointSizeF() * 1.3)
        self.editor.setFont(editor_font)

    def _resolve_app_font_families(self) -> list[str]:
        """Prefer bundled DM font file, fallback to Source Han Sans for CJK."""
        # Search in this order:
        # 1) PyInstaller bundle data path
        # 2) Executable directory data path
        # 3) Package asset path (source run)
        # 4) Project root (legacy fallback)
        ttf_candidates: list[Path] = []
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            bundle_path = Path(str(bundle_dir)) / "review_trash" / "assets" / "fonts"
            if bundle_path.exists():
                ttf_candidates.extend(sorted(bundle_path.glob("*.ttf")))

        exe_fonts = Path(sys.executable).resolve().parent / "review_trash" / "assets" / "fonts"
        if exe_fonts.exists():
            ttf_candidates.extend(sorted(exe_fonts.glob("*.ttf")))

        source_assets = Path(__file__).resolve().parent / "assets" / "fonts"
        if source_assets.exists():
            ttf_candidates.extend(sorted(source_assets.glob("*.ttf")))

        project_root = Path(__file__).resolve().parent.parent
        ttf_candidates.extend(sorted(project_root.glob("*.ttf")))

        def _priority(path: Path) -> tuple[int, str]:
            name = path.name.lower()
            if "dm" in name and "mono" in name:
                return (0, name)
            if name.startswith("dm"):
                return (1, name)
            return (2, name)

        dm_family: str | None = None
        for ttf_path in sorted({p.resolve() for p in ttf_candidates}, key=_priority):
            font_id = QFontDatabase.addApplicationFont(str(ttf_path))
            if font_id < 0:
                continue
            families = QFontDatabase.applicationFontFamilies(font_id)
            if not families:
                continue
            dm_family = families[0]
            if _priority(ttf_path)[0] == 0:
                break

        if dm_family:
            return [dm_family, "Source Han Sans SC"]
        return ["DM Mono", "Source Han Sans SC"]

    def open_project_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            S.DLG_OPEN_PROJECT,
            "",
            S.DLG_OPEN_PROJECT_FILTER,
        )
        if not file_path:
            return

        project_path = Path(file_path)
        project_data = self.project_store.read(project_path)
        if not project_data:
            self._error(S.ERR_READ_PROJECT_FAILED)
            return
        if not project_data.ass_path.exists():
            self._error(S.ERR_ASS_NOT_FOUND.format(ass_path=project_data.ass_path))
            return
        if not project_data.image_dir.exists():
            self._error(S.ERR_IMAGE_DIR_NOT_FOUND.format(image_dir=project_data.image_dir))
            return

        if not self._load_ass_document(project_data.ass_path, restore_snapshot=False):
            return
        try:
            self.image_matcher.set_directory(project_data.image_dir)
        except Exception as exc:
            self._error(S.ERR_PROJECT_IMAGE_DIR_LOAD_FAILED.format(exc=exc))
            return
        self.session.image_dir = project_data.image_dir
        self._image_cache.clear()
        self._apply_project_data(project_data)
        self.project_path = project_path
        self._update_status(S.STATUS_PROJECT_OPENED.format(project_path=project_path))

    def _load_ass_document(self, ass_path: Path, restore_snapshot: bool) -> bool:
        try:
            document = AssDocument.load(ass_path)
        except Exception as exc:
            self._error(S.ERR_READ_ASS_FAILED.format(exc=exc))
            return False

        self.ass_doc = document
        self.session.ass_path = ass_path
        self._dirty_count = self.ass_doc.dirty_count()
        self._reviewed_indexes.clear()

        target_row = self._restore_snapshot_if_available() if restore_snapshot else 0
        self._populate_list(target_row=target_row)
        self._recount_missing()
        self._rebuild_issue_panel()
        self._refresh_status_line()
        return True

    def _apply_project_data(self, project_data: ProjectData) -> None:
        if not self.ass_doc:
            return
        reviewed = {idx for idx in project_data.reviewed_indexes if 0 <= idx < len(self.ass_doc.dialogue_entries)}
        self._reviewed_indexes = reviewed
        for idx, entry in enumerate(self.ass_doc.dialogue_entries):
            entry.reviewed = idx in reviewed
        self._dirty_count = self.ass_doc.dirty_count()
        target_row = 0
        self._populate_list(target_row=target_row)
        self._recount_missing()
        self._rebuild_issue_panel()
        self._refresh_status_line()

    def _restore_snapshot_if_available(self) -> int:
        if not self.ass_doc:
            return 0
        snapshot = self.snapshot_store.read_snapshot(self.ass_doc.path)
        if not snapshot:
            return 0
        if len(snapshot.entries) != len(self.ass_doc.dialogue_entries):
            return 0

        result = QMessageBox.question(
            self,
            S.DLG_AUTOSAVE_FOUND_TITLE,
            S.DLG_AUTOSAVE_FOUND_TEXT,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result != QMessageBox.Yes:
            return 0

        reviewed = set(snapshot.reviewed_indexes)
        for idx, text in enumerate(snapshot.entries):
            entry = self.ass_doc.dialogue_entries[idx]
            entry.text_current = text
            entry.dirty = entry.text_current != entry.text_original
            entry.reviewed = idx in reviewed
        self._reviewed_indexes = reviewed
        self._dirty_count = self.ass_doc.dirty_count()
        self._update_status(S.STATUS_AUTOSAVE_RESTORED)
        return max(0, min(snapshot.current_index, len(self.ass_doc.dialogue_entries) - 1))

    def _populate_list(self, target_row: int = 0) -> None:
        """Render list rows incrementally so large ASS files stay responsive."""
        self._updating_ui = True
        self.subtitle_list.clear()
        self.editor.clear()
        self.original_view.clear()
        self.diff_view.clear()

        if not self.ass_doc:
            self._updating_ui = False
            return

        self._list_building_entries = list(self.ass_doc.dialogue_entries)
        self._list_build_cursor = 0
        self._list_target_row = max(0, target_row)
        QTimer.singleShot(0, self._append_list_chunk)

    def _append_list_chunk(self) -> None:
        if not self.ass_doc:
            self._updating_ui = False
            return
        if self._list_build_cursor >= len(self._list_building_entries):
            self._updating_ui = False
            if self.ass_doc.dialogue_entries:
                self.subtitle_list.setCurrentRow(min(self._list_target_row, len(self.ass_doc.dialogue_entries) - 1))
            else:
                self._update_status(S.STATUS_NO_DIALOGUE)
            return

        end = min(self._list_build_cursor + self.LIST_CHUNK_SIZE, len(self._list_building_entries))
        for row in range(self._list_build_cursor, end):
            entry = self._list_building_entries[row]
            item = QListWidgetItem(self._render_entry_text(entry))
            self.subtitle_list.addItem(item)
        self._list_build_cursor = end
        QTimer.singleShot(0, self._append_list_chunk)

    def _render_entry_text(self, entry: AssEntry) -> str:
        preview = entry.text_current.replace("\\N", " / ").strip()
        if len(preview) > 42:
            preview = preview[:39] + "..."
        dirty_marker = "*" if entry.dirty else " "
        reviewed_marker = "R" if entry.reviewed else " "
        return f"{dirty_marker}{reviewed_marker}{entry.index:04d} | {entry.start} -> {entry.end} | {preview}"

    def _on_list_changed(self, row: int) -> None:
        if self._updating_ui or not self.ass_doc:
            return
        if row < 0 or row >= len(self.ass_doc.dialogue_entries):
            return

        self.session.current_index = row
        entry = self.ass_doc.dialogue_entries[row]
        self._updating_ui = True
        self.editor.setPlainText(entry.text_current)
        self.original_view.setPlainText(entry.text_original)
        self.diff_view.setHtml(self._make_diff_html(entry.text_original, entry.text_current))
        self._updating_ui = False
        self._update_preview_for_current()
        self._refresh_list_item(row, entry)
        self._refresh_status_line()
        self._prefetch_adjacent_images(row)

    def _on_text_changed(self) -> None:
        if self._updating_ui or not self.ass_doc:
            return

        row = self.subtitle_list.currentRow()
        if row < 0 or row >= len(self.ass_doc.dialogue_entries):
            return
        self._set_entry_text(row, self.editor.toPlainText())

    def _set_entry_text(self, row: int, new_text: str) -> None:
        if not self.ass_doc:
            return
        entry = self.ass_doc.dialogue_entries[row]
        was_dirty = entry.dirty
        self.ass_doc.update_entry(row, new_text)
        is_dirty = entry.dirty
        if not was_dirty and is_dirty:
            self._dirty_count += 1
        elif was_dirty and not is_dirty:
            self._dirty_count -= 1
        self.diff_view.setHtml(self._make_diff_html(entry.text_original, entry.text_current))
        self._refresh_list_item(row, entry)
        self._refresh_status_line()

    def _refresh_list_item(self, row: int, entry: AssEntry) -> None:
        item = self.subtitle_list.item(row)
        if not item:
            return
        item.setText(self._render_entry_text(entry))

    def _update_preview_for_current(self) -> None:
        if not self.ass_doc or self.session.current_index < 0:
            self.image_label.setText(S.STATUS_NO_SUBTITLE)
            self.image_label.setPixmap(QPixmap())
            self._current_image = None
            return

        row = self.session.current_index
        if row >= len(self.ass_doc.dialogue_entries):
            return

        line_number = self.ass_doc.dialogue_entries[row].index
        match_result = self.image_matcher.match(line_number)
        if not match_result.path:
            expected = " / ".join(match_result.expected_names)
            self.image_label.setPixmap(QPixmap())
            self._current_image = None
            self.image_label.setText(S.STATUS_NO_MATCHING_IMAGE.format(expected=expected))
            return

        path_key = str(match_result.path)
        cached = self._image_cache.get(path_key)
        if cached is not None:
            self._cache_touch(path_key, cached)
            self._current_image = cached
            self._render_current_image()
            return

        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(S.STATUS_LOADING_IMAGE)
        self._request_image(match_result.path, for_display=True)

    def _request_image(self, path: Path, for_display: bool) -> None:
        """Queue async image loading and track request ids for stale result filtering."""
        self._request_id += 1
        request_id = self._request_id
        if for_display:
            self._active_display_request_id = request_id

        task = ImageLoadTask(request_id=request_id, path=path, for_display=for_display)
        task.signals.loaded.connect(self._on_image_loaded)
        self._pending_tasks[request_id] = task
        self._thread_pool.start(task)

    def _on_image_loaded(self, request_id: int, path_text: str, image: QImage, error: str, for_display: bool) -> None:
        """Accept the newest image request result and ignore outdated display tasks."""
        self._pending_tasks.pop(request_id, None)
        if not error and not image.isNull():
            self._cache_put(path_text, image)

        if not for_display or request_id != self._active_display_request_id:
            return

        if error or image.isNull():
            self._current_image = None
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(S.STATUS_IMAGE_LOAD_FAILED.format(error=error or "Unknown error"))
            return
        self._current_image = image
        self._render_current_image()

    def _cache_put(self, key: str, image: QImage) -> None:
        """Store image in an LRU cache with a fixed upper bound."""
        self._image_cache[key] = image
        self._image_cache.move_to_end(key)
        while len(self._image_cache) > self.IMAGE_CACHE_MAX:
            self._image_cache.popitem(last=False)

    def _cache_touch(self, key: str, image: QImage) -> None:
        self._image_cache[key] = image
        self._image_cache.move_to_end(key)

    def _prefetch_adjacent_images(self, row: int) -> None:
        """Preload nearby rows to reduce wait time when navigating."""
        if not self.ass_doc:
            return
        for neighbor in (row - 1, row + 1, row + 2):
            if neighbor < 0 or neighbor >= len(self.ass_doc.dialogue_entries):
                continue
            line_number = self.ass_doc.dialogue_entries[neighbor].index
            match_result = self.image_matcher.match(line_number)
            if not match_result.path:
                continue
            key = str(match_result.path)
            if key in self._image_cache:
                continue
            self._request_image(match_result.path, for_display=False)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_current_image()

    def _render_current_image(self) -> None:
        if not self._current_image or self._current_image.isNull():
            return
        pixmap = QPixmap.fromImage(self._current_image)
        scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def go_prev(self) -> None:
        row = self.subtitle_list.currentRow()
        if row > 0:
            self.subtitle_list.setCurrentRow(row - 1)

    def go_next(self) -> None:
        row = self.subtitle_list.currentRow()
        if self.ass_doc and should_mark_reviewed_on_next(
            self.auto_review_on_next_checkbox.isChecked(),
            row,
            len(self.ass_doc.dialogue_entries),
        ):
            entry = self.ass_doc.dialogue_entries[row]
            if not entry.reviewed:
                entry.reviewed = True
                self._reviewed_indexes.add(row)
                self._refresh_list_item(row, entry)
                self._save_project_state(show_errors=False)
        if row + 1 < self.subtitle_list.count():
            self.subtitle_list.setCurrentRow(row + 1)

    def go_next_unreviewed(self) -> None:
        self._jump_by_predicate(lambda e: not e.reviewed)

    def go_next_modified(self) -> None:
        self._jump_by_predicate(lambda e: e.dirty)

    def _jump_by_predicate(self, predicate: Callable[[AssEntry], bool]) -> None:
        if not self.ass_doc or not self.ass_doc.dialogue_entries:
            return
        start = self.subtitle_list.currentRow() + 1
        total = len(self.ass_doc.dialogue_entries)
        for idx in range(start, total):
            if predicate(self.ass_doc.dialogue_entries[idx]):
                self.subtitle_list.setCurrentRow(idx)
                return
        for idx in range(0, start):
            if predicate(self.ass_doc.dialogue_entries[idx]):
                self.subtitle_list.setCurrentRow(idx)
                return
        self._update_status(S.STATUS_NO_MATCHED_ENTRY)

    def _go_prev_if_editor_not_focused(self) -> None:
        if not self.editor.hasFocus():
            self.go_prev()

    def _go_next_if_editor_not_focused(self) -> None:
        if not self.editor.hasFocus():
            self.go_next()

    def toggle_reviewed(self) -> None:
        if not self.ass_doc:
            return
        row = self.subtitle_list.currentRow()
        if row < 0 or row >= len(self.ass_doc.dialogue_entries):
            return
        entry = self.ass_doc.dialogue_entries[row]
        entry.reviewed = not entry.reviewed
        if entry.reviewed:
            self._reviewed_indexes.add(row)
        else:
            self._reviewed_indexes.discard(row)
        self._refresh_list_item(row, entry)
        self._refresh_status_line()
        self._save_project_state(show_errors=False)

    def open_replace_dialog(self) -> None:
        if not self.ass_doc:
            self._error(S.ERR_OPEN_ASS_FIRST)
            return
        dialog = ReplaceDialog(
            find_text=self._last_find_text,
            replace_text=self._last_replace_text,
            parent=self,
        )
        dialog.replace_current_button.clicked.connect(
            lambda: self._replace_from_dialog(dialog, replace_all=False)
        )
        dialog.replace_all_button.clicked.connect(lambda: self._replace_from_dialog(dialog, replace_all=True))
        dialog.exec()

    def _replace_from_dialog(self, dialog: ReplaceDialog, replace_all: bool) -> None:
        find_text = dialog.find_input.text()
        replace_text = dialog.replace_input.text()
        self._last_find_text = find_text
        self._last_replace_text = replace_text
        if replace_all:
            self.replace_in_all(find_text, replace_text)
            return
        self.replace_in_current(find_text, replace_text)

    def replace_in_current(self, find_text: str, replace_text: str) -> None:
        if not self.ass_doc:
            return
        if not find_text:
            self._error(S.ERR_FIND_TEXT_REQUIRED)
            return
        row = self.subtitle_list.currentRow()
        if row < 0:
            return
        current_text = self.editor.toPlainText()
        replaced = current_text.replace(find_text, replace_text)
        if replaced == current_text:
            self._update_status(S.STATUS_REPLACE_CURRENT_NO_MATCH)
            return
        self._updating_ui = True
        self.editor.setPlainText(replaced)
        self._updating_ui = False
        self._set_entry_text(row, replaced)

    def replace_in_all(self, find_text: str, replace_text: str) -> None:
        if not self.ass_doc:
            return
        if not find_text:
            self._error(S.ERR_FIND_TEXT_REQUIRED)
            return
        changed_rows = 0
        replace_hits = 0
        for row, entry in enumerate(self.ass_doc.dialogue_entries):
            hit = entry.text_current.count(find_text)
            if hit <= 0:
                continue
            replace_hits += hit
            changed_rows += 1
            self._set_entry_text(row, entry.text_current.replace(find_text, replace_text))
        if changed_rows == 0:
            self._update_status(S.STATUS_REPLACE_ALL_NO_MATCH)
            return
        current_row = self.subtitle_list.currentRow()
        self._populate_list(target_row=max(0, current_row))
        self._update_status(
            S.STATUS_REPLACE_ALL_DONE.format(changed_rows=changed_rows, replace_hits=replace_hits)
        )

    def save_ass(self) -> None:
        if not self.ass_doc:
            self._error(S.ERR_OPEN_ASS_FIRST)
            return
        try:
            backup_path = self.ass_doc.save_with_backup()
        except Exception as exc:
            self._error(S.ERR_SAVE_FAILED.format(exc=exc))
            return

        self._dirty_count = 0
        self.snapshot_store.clear_snapshot(self.ass_doc.path)
        current_row = self.subtitle_list.currentRow()
        self._populate_list(target_row=max(0, current_row))
        self._refresh_status_line()
        self._update_status(
            S.STATUS_SAVED.format(backup_name=backup_path.name, backup_path=backup_path)
        )

    def _auto_save_snapshot(self) -> None:
        """Persist current editing state periodically for crash recovery."""
        if not self.ass_doc:
            return
        has_work = self._dirty_count > 0 or bool(self._reviewed_indexes)
        if not has_work:
            return
        try:
            self.snapshot_store.write_snapshot(
                document=self.ass_doc,
                reviewed_indexes=self._reviewed_indexes,
                current_index=max(0, self.subtitle_list.currentRow()),
            )
        except Exception:
            pass

    def _save_project_state(self, show_errors: bool) -> None:
        """Persist reviewed progress automatically when project path is configured."""
        if not self.project_path or not self.ass_doc or not self.session.image_dir:
            return
        data = ProjectData(
            ass_path=self.ass_doc.path,
            image_dir=self.session.image_dir,
            reviewed_indexes=sorted(self._reviewed_indexes),
        )
        try:
            self.project_store.write(self.project_path, data)
        except Exception as exc:
            if show_errors:
                self._error(S.ERR_PROJECT_STATE_SAVE_FAILED.format(exc=exc))

    def _recount_missing(self) -> None:
        if not self.ass_doc or not self.image_matcher.root:
            self._missing_count = 0
            self._missing_indexes.clear()
            self._rebuild_issue_panel()
            return
        missing_indexes: set[int] = set()
        for row, entry in enumerate(self.ass_doc.dialogue_entries):
            if self.image_matcher.match(entry.index).path is None:
                missing_indexes.add(row)
        self._missing_indexes = missing_indexes
        self._missing_count = len(missing_indexes)
        self._rebuild_issue_panel()

    def _rebuild_issue_panel(self) -> None:
        self.issue_list.clear()
        if not self.ass_doc:
            return
        for issue in self.ass_doc.issues:
            row = self._dialogue_row_by_line_index(issue.line_index)
            item = QListWidgetItem(S.ISSUE_PARSE.format(message=issue.message))
            item.setData(Qt.UserRole, row)
            self.issue_list.addItem(item)
        for row in sorted(self._missing_indexes):
            item = QListWidgetItem(S.ISSUE_MISSING.format(row=row + 1))
            item.setData(Qt.UserRole, row)
            self.issue_list.addItem(item)

    def _dialogue_row_by_line_index(self, line_index: int) -> int:
        if not self.ass_doc:
            return -1
        for row, entry in enumerate(self.ass_doc.dialogue_entries):
            if entry.line_index == line_index:
                return row
        return -1

    def _on_issue_clicked(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.UserRole)
        if isinstance(row, int) and row >= 0 and row < self.subtitle_list.count():
            self.subtitle_list.setCurrentRow(row)

    def _refresh_status_line(self) -> None:
        if not self.ass_doc:
            self.progress_bar.setValue(0)
            self.progress_info_label.setText(S.UI_PROGRESS_ZERO)
            self.quick_stats_label.setText(S.UI_STATS_ZERO)
            return
        total = len(self.ass_doc.dialogue_entries)
        current = self.subtitle_list.currentRow() + 1 if self.subtitle_list.currentRow() >= 0 else 0
        reviewed = len(self._reviewed_indexes)
        progress_value = int((reviewed / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_value)
        self.progress_info_label.setText(
            S.UI_PROGRESS.format(reviewed=reviewed, total=total, progress=progress_value)
        )
        self.quick_stats_label.setText(
            S.UI_STATS.format(missing=self._missing_count, unsaved=self._dirty_count)
        )
        self._update_status(
            S.STATUS_PROGRESS.format(
                current=current,
                total=total,
                reviewed=reviewed,
                missing=self._missing_count,
                unsaved=self._dirty_count,
            )
        )

    def _make_diff_html(self, source: str, target: str) -> str:
        """Build inline HTML diff that highlights insert/replace/delete chunks."""
        matcher = difflib.SequenceMatcher(a=source, b=target)
        chunks: list[str] = []
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            piece = escape(target[j1:j2]).replace("\n", "<br>")
            if op == "equal":
                chunks.append(piece)
            elif op == "insert":
                chunks.append(f"<span style='background:#d7f9dd;'>{piece}</span>")
            elif op == "replace":
                chunks.append(f"<span style='background:#ffe5c2;'>{piece}</span>")
            elif op == "delete":
                deleted = escape(source[i1:i2]).replace("\n", "<br>")
                chunks.append(f"<span style='color:#b23b3b;text-decoration:line-through;'>{deleted}</span>")
        if not chunks:
            return "<span></span>"
        return "".join(chunks)

    def _update_status(self, text: str) -> None:
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(text)

    def _error(self, text: str) -> None:
        QMessageBox.critical(self, S.ERR_TITLE, text)
        self._update_status(text)

    def _has_unsaved_changes(self) -> bool:
        return self._dirty_count > 0

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._has_unsaved_changes():
            event.accept()
            return

        result = QMessageBox.question(
            self,
            S.DLG_UNSAVED_TITLE,
            S.DLG_UNSAVED_TEXT,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            event.accept()
            return
        event.ignore()



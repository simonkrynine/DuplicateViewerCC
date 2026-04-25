import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

THUMB_SIZE = 140
MAX_THUMBNAILS_PER_GROUP = None


class ThumbnailCard(QWidget):
    mark_changed = Signal(str, bool)

    def __init__(self, path: str, is_oldest: bool, parent=None):
        super().__init__(parent)
        self._path = path
        self._is_oldest = is_oldest
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        thumb_label = QLabel()
        thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setFrameShape(QFrame.Shape.Box)
        self._load_thumbnail(thumb_label)
        layout.addWidget(thumb_label)

        filename = os.path.basename(self._path)
        name_label = QLabel(filename)
        name_label.setToolTip(self._path)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setMaximumWidth(THUMB_SIZE + 20)
        layout.addWidget(name_label)

        try:
            size_str = self._format_size(os.path.getsize(self._path))
        except OSError:
            size_str = "Unknown"
        size_label = QLabel(size_str)
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(size_label)

        if self._is_oldest:
            keep_label = QLabel("Keep")
            keep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(keep_label)
        else:
            checkbox = QCheckBox("Mark for deletion")
            checkbox.stateChanged.connect(self._on_check_changed)
            layout.addWidget(checkbox)

    def _load_thumbnail(self, label: QLabel):
        try:
            from PIL import Image
            img = Image.open(self._path)
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            label.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            label.setText("⚠ unreadable")

    def _on_check_changed(self, state):
        self.mark_changed.emit(self._path, bool(state))

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    @property
    def path(self) -> str:
        return self._path


class DuplicateGroupWidget(QWidget):
    def __init__(self, paths: list, group_number: int, mark_callback, parent=None):
        super().__init__(parent)
        self._paths = list(paths)
        self._group_number = group_number
        self._mark_callback = mark_callback
        self._cards: list[ThumbnailCard] = []
        self._cards_row: QHBoxLayout | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel(f"Group {self._group_number}  ·  {len(self._paths)} duplicates")
        font = QFont()
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(8)

        paths_to_show = self._paths
        if MAX_THUMBNAILS_PER_GROUP is not None:
            paths_to_show = self._paths[:MAX_THUMBNAILS_PER_GROUP]

        for i, path in enumerate(paths_to_show):
            card = ThumbnailCard(path, is_oldest=(i == 0))
            if i != 0:
                card.mark_changed.connect(self._mark_callback)
            self._cards_row.addWidget(card)
            self._cards.append(card)

        self._cards_row.addStretch()
        layout.addLayout(self._cards_row)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

    def remove_path(self, path: str) -> None:
        for card in list(self._cards):
            if card.path == path:
                self._cards.remove(card)
                self._cards_row.removeWidget(card)
                card.deleteLater()
                return

    @property
    def file_count(self) -> int:
        return len(self._cards)

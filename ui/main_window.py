import os

from PySide6.QtCore import QSettings, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.scanner import ScanWorker
from ui.duplicate_group import DuplicateGroupWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._directory: str | None = None
        self._settings = QSettings("ImageDedup", "ImageDeduplicator")
        self._worker: ScanWorker | None = None
        self._group_count = 0
        self._marked_paths: set[str] = set()
        self._setup_ui()
        self._restore_last_directory()

    def _setup_ui(self):
        self.setWindowTitle("Image Deduplicator")
        self.resize(1100, 700)
        self.setMinimumSize(860, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Toolbar ---
        toolbar = QWidget()
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(8, 6, 8, 6)
        toolbar_row.setSpacing(8)

        self._choose_folder_btn = QPushButton("Choose Folder")
        self._choose_folder_btn.clicked.connect(self._on_choose_folder)
        toolbar_row.addWidget(self._choose_folder_btn)

        self._folder_label = QLabel("No folder selected")
        self._folder_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_row.addWidget(self._folder_label)

        toolbar_row.addWidget(QLabel("Threshold:"))

        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(0, 20)
        self._threshold_spin.setValue(0)
        self._threshold_spin.setToolTip(
            "0 = exact perceptual match.\n"
            "Higher values catch near-duplicates (resized, recompressed)."
        )
        toolbar_row.addWidget(self._threshold_spin)

        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setEnabled(False)
        self._scan_btn.clicked.connect(self._on_scan)
        toolbar_row.addWidget(self._scan_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        toolbar_row.addWidget(self._cancel_btn)

        root.addWidget(toolbar)

        # --- Progress bar (hidden until scan starts) ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        # --- Results area (scrollable, hidden until results arrive) ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVisible(False)

        results_container = QWidget()
        self._results_layout = QVBoxLayout(results_container)
        self._results_layout.setContentsMargins(8, 8, 8, 8)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()

        self._scroll_area.setWidget(results_container)
        root.addWidget(self._scroll_area, stretch=1)

        # --- Delete bar (hidden when nothing is marked) ---
        self._delete_bar = QWidget()
        delete_row = QHBoxLayout(self._delete_bar)
        delete_row.setContentsMargins(8, 4, 8, 4)

        self._marked_label = QLabel()
        self._marked_label.setVisible(False)
        delete_row.addWidget(self._marked_label)

        delete_row.addStretch()

        self._delete_btn = QPushButton("Move to Recycle Bin")
        self._delete_btn.setEnabled(False)
        delete_row.addWidget(self._delete_btn)

        self._delete_bar.setVisible(False)
        root.addWidget(self._delete_bar)

        # --- Status bar ---
        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------
    # Directory selection (Story 1)
    # ------------------------------------------------------------------

    def _restore_last_directory(self):
        saved = self._settings.value("last_directory", "")
        if saved and os.path.isdir(saved):
            self._apply_directory(saved)

    def _on_choose_folder(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Select Folder", self._directory or ""
        )
        if chosen:
            self._apply_directory(chosen)
            self._settings.setValue("last_directory", chosen)

    def _apply_directory(self, directory: str):
        self._directory = directory
        display = directory if len(directory) <= 70 else "…" + directory[-67:]
        self._folder_label.setText(display)
        self._folder_label.setToolTip(directory)
        self._scan_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Scan control (Story 2)
    # ------------------------------------------------------------------

    def _on_scan(self):
        self._clear_results()
        self._scroll_area.setVisible(False)
        self._progress_bar.setMaximum(0)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._group_count = 0
        self._marked_paths.clear()
        self._update_delete_bar()
        self.statusBar().showMessage("Scanning…")

        self._worker = ScanWorker(
            self._directory,
            threshold=self._threshold_spin.value(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.found_duplicate.connect(self._on_found_duplicate)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def _on_cancel(self):
        self._disconnect_worker()
        if self._worker:
            self._worker.abort()
        self._worker = None
        self._restore_idle()
        self.statusBar().showMessage("Ready")

    def _disconnect_worker(self):
        if self._worker is None:
            return
        pairs = [
            (self._worker.progress, self._on_progress),
            (self._worker.found_duplicate, self._on_found_duplicate),
            (self._worker.finished, self._on_scan_finished),
            (self._worker.error, self._on_scan_error),
        ]
        for sig, slot in pairs:
            try:
                sig.disconnect(slot)
            except RuntimeError:
                pass

    def _restore_idle(self):
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(bool(self._directory))
        self._cancel_btn.setEnabled(False)

    def _clear_results(self):
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # Worker signal handlers (Stories 2 & 3)
    # ------------------------------------------------------------------

    @Slot(int, int)
    def _on_progress(self, done: int, total: int):
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)
        self.statusBar().showMessage(f"Scanning… {done} / {total} files")

    @Slot(list)
    def _on_found_duplicate(self, paths: list):
        self._group_count += 1
        widget = DuplicateGroupWidget(paths, self._group_count, self._on_mark_changed)
        insert_at = self._results_layout.count() - 1
        self._results_layout.insertWidget(insert_at, widget)
        if not self._scroll_area.isVisible():
            self._scroll_area.setVisible(True)

    @Slot(int, int)
    def _on_scan_finished(self, total: int, groups: int):
        self._worker = None
        self._restore_idle()
        if groups == 0:
            self.statusBar().showMessage("Scan complete — no duplicates found.")
        else:
            self.statusBar().showMessage(
                f"Scan complete — {total} files scanned, {groups} duplicate group(s) found."
            )

    @Slot(str)
    def _on_scan_error(self, message: str):
        self._worker = None
        self._restore_idle()
        self.statusBar().showMessage(f"Error: {message}")

    # ------------------------------------------------------------------
    # Mark-for-deletion tracking (Story 4 hook, wired here for Story 3)
    # ------------------------------------------------------------------

    @Slot(str, bool)
    def _on_mark_changed(self, path: str, checked: bool):
        if checked:
            self._marked_paths.add(path)
        else:
            self._marked_paths.discard(path)
        self._update_delete_bar()

    def _update_delete_bar(self):
        count = len(self._marked_paths)
        if count > 0:
            self._marked_label.setText(f"{count} file(s) marked for deletion")
            self._marked_label.setVisible(True)
            self._delete_btn.setEnabled(True)
            self._delete_bar.setVisible(True)
        else:
            self._marked_label.setVisible(False)
            self._delete_btn.setEnabled(False)
            self._delete_bar.setVisible(False)

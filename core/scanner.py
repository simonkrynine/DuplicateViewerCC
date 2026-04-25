import os
from pathlib import Path

import imagehash
from PIL import Image
from PySide6.QtCore import QThread, Signal

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'}


class ScanWorker(QThread):
    progress = Signal(int, int)
    found_duplicate = Signal(list)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, directory: str, hash_size: int = 8, threshold: int = 0):
        super().__init__()
        self._directory = directory
        self._hash_size = hash_size
        self._threshold = threshold
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            files = [
                p for p in Path(self._directory).rglob('*')
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
        except PermissionError as e:
            self.error.emit(str(e))
            return

        total = len(files)
        buckets: dict[str, list[str]] = {}
        scanned = 0

        for file_path in files:
            if self._abort:
                return

            path_str = str(file_path)
            try:
                img = Image.open(file_path)
                h = imagehash.phash(img, hash_size=self._hash_size)
            except Exception:
                scanned += 1
                self.progress.emit(scanned, total)
                continue

            if self._threshold == 0:
                key = str(h)
                buckets.setdefault(key, []).append(path_str)
            else:
                key = self._find_bucket(h, buckets)
                if key is None:
                    key = str(h)
                    buckets[key] = []
                buckets[key].append(path_str)

            scanned += 1
            self.progress.emit(scanned, total)

        groups = 0
        for paths in buckets.values():
            if len(paths) >= 2:
                sorted_paths = sorted(paths, key=os.path.getctime)
                self.found_duplicate.emit(sorted_paths)
                groups += 1

        self.finished.emit(scanned, groups)

    def _find_bucket(self, h: imagehash.ImageHash, buckets: dict) -> str | None:
        best_key = None
        best_dist = self._threshold + 1
        for key_str in buckets:
            dist = h - imagehash.hex_to_hash(key_str)
            if dist <= self._threshold and dist < best_dist:
                best_dist = dist
                best_key = key_str
        return best_key

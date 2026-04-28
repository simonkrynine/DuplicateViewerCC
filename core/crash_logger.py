import sys
import traceback
from datetime import datetime
from pathlib import Path


def _get_log_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(sys.argv[0]).resolve().parent


def _excepthook(exc_type, exc_value, exc_tb):
    log_path = _get_log_dir() / 'crash_log.txt'

    header = (
        f"\n{'=' * 80}\n"
        f"CRASH — {datetime.now().isoformat()}\n"
        f"Python {sys.version} | {sys.platform}\n"
        f"{'=' * 80}\n"
    )
    body = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))

    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(header + body)
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                'Application Crashed',
                f'An unexpected error occurred.\n\nA crash log has been saved to:\n{log_path}',
            )
    except Exception:
        pass

    _original_hook(exc_type, exc_value, exc_tb)


_original_hook = sys.excepthook


def setup_crash_logger():
    sys.excepthook = _excepthook

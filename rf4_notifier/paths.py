import os
from pathlib import Path


def data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RF4Notifier"
    root.mkdir(parents=True, exist_ok=True)
    return root

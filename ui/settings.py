import json
import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """
    Return the directory used for writable LocalBot user data.
    """

    if sys.platform == "darwin":
        path = (
            Path.home()
            / "Library"
            / "Application Support"
            / "LocalBot"
        )

    elif sys.platform == "win32":
        base = Path(
            os.environ.get(
                "APPDATA",
                Path.home() / "AppData" / "Roaming"
            )
        )
        path = base / "LocalBot"

    else:
        path = Path.home() / ".localbot"

    path.mkdir(parents=True, exist_ok=True)

    return path


PREFS_PATH = get_app_data_dir() / "settings.json"


def load_preferences() -> dict:
    if PREFS_PATH.is_file():
        try:
            return json.loads(
                PREFS_PATH.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            pass

    return {}


def save_preferences(prefs: dict):
    PREFS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    PREFS_PATH.write_text(
        json.dumps(prefs, indent=2),
        encoding="utf-8"
    )
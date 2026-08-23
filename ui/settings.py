import json
from pathlib import Path

PREFS_PATH = Path("data/settings.json")

def load_preferences() -> dict:
    if PREFS_PATH.is_file():
        try:
            return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_preferences(prefs: dict):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
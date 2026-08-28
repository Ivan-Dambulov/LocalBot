"""Preferences in the platform app-data directory + legacy migration."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Optional


def get_app_data_dir() -> Path:
    if sys.platform == "darwin":
        path = (
            Path.home()
            / "Library"
            / "Application Support"
            / "LocalBot"
        )
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "LocalBot"
    else:
        path = Path.home() / ".localbot"

    path.mkdir(parents=True, exist_ok=True)
    return path


PREFS_PATH = get_app_data_dir() / "settings.json"
_migration_done = False


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def _executable_dir() -> Optional[Path]:
    if not _is_frozen():
        return None
    try:
        return Path(sys.executable).resolve().parent
    except Exception:
        return None


def _package_root() -> Optional[Path]:
    try:
        return Path(__file__).resolve().parents[1]
    except Exception:
        return None


def _legacy_settings_candidates() -> List[Path]:
    candidates: List[Path] = [
        Path("data") / "settings.json",
        Path("settings.json"),
    ]
    root = _package_root()
    if root is not None:
        candidates.append(root / "data" / "settings.json")
        candidates.append(root / "settings.json")
    exe_dir = _executable_dir()
    if exe_dir is not None:
        candidates.append(exe_dir / "data" / "settings.json")
        candidates.append(exe_dir / "settings.json")
        candidates.append(exe_dir.parent / "data" / "settings.json")

    seen = set()
    unique: List[Path] = []
    for path in candidates:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _path_search_roots(legacy_settings: Optional[Path] = None) -> List[Path]:
    roots: List[Path] = [
        get_app_data_dir(),
        get_app_data_dir() / "models",
        Path.cwd(),
        Path.cwd() / "models",
    ]
    if legacy_settings is not None:
        roots.append(legacy_settings.parent)
        roots.append(legacy_settings.parent / "models")
        if legacy_settings.parent.name == "data":
            roots.append(legacy_settings.parent.parent)
            roots.append(legacy_settings.parent.parent / "models")
    root = _package_root()
    if root is not None:
        roots.append(root)
        roots.append(root / "models")
        roots.append(root / "data")
    exe_dir = _executable_dir()
    if exe_dir is not None:
        roots.append(exe_dir)
        roots.append(exe_dir / "models")
        roots.append(exe_dir / "data")

    seen = set()
    unique: List[Path] = []
    for path in roots:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _resolve_existing_path(value: str, roots: Iterable[Path]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        if raw.exists():
            try:
                return str(raw.resolve())
            except Exception:
                return str(raw)
        return None
    for root in roots:
        candidate = (root / raw).expanduser()
        if candidate.exists():
            try:
                return str(candidate.resolve())
            except Exception:
                return str(candidate)
    return None


def _normalize_migrated_prefs(prefs: dict, legacy_settings: Optional[Path]) -> dict:
    if not isinstance(prefs, dict):
        return {}
    out = dict(prefs)
    roots = _path_search_roots(legacy_settings)

    model_path = out.get("model_path")
    if isinstance(model_path, str) and model_path.strip():
        resolved = _resolve_existing_path(model_path.strip(), roots)
        if resolved:
            out["model_path"] = resolved

    models_dir = out.get("models_dir")
    if isinstance(models_dir, str) and models_dir.strip():
        resolved = _resolve_existing_path(models_dir.strip(), roots)
        if resolved:
            out["models_dir"] = resolved
        else:
            out["models_dir"] = str(get_app_data_dir() / "models")
    else:
        out.setdefault("models_dir", str(get_app_data_dir() / "models"))

    mode = out.get("appearance_mode", "System")
    if mode not in ("Light", "Dark", "System"):
        out["appearance_mode"] = "System"

    return out


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def migrate_settings_if_needed() -> bool:
    global _migration_done
    if _migration_done:
        return False
    if PREFS_PATH.is_file():
        _migration_done = True
        return False

    for legacy in _legacy_settings_candidates():
        if not legacy.is_file():
            continue
        try:
            if legacy.resolve() == PREFS_PATH.resolve():
                continue
        except Exception:
            if str(legacy) == str(PREFS_PATH):
                continue

        data = _read_json(legacy)
        if data is None:
            continue

        normalized = _normalize_migrated_prefs(data, legacy_settings=legacy)
        try:
            PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
            PREFS_PATH.write_text(
                json.dumps(normalized, indent=2),
                encoding="utf-8",
            )
            _migration_done = True
            print(f"[LocalBot] Migrated settings from {legacy} → {PREFS_PATH}")
            return True
        except Exception as exc:
            print(f"[LocalBot] Settings migration failed from {legacy}: {exc}")
    _migration_done = True
    return False


def migrate_conversations_db_if_needed() -> bool:
    dest = get_app_data_dir() / "conversations.db"
    if dest.is_file():
        return False

    candidates: List[Path] = [
        Path("data") / "conversations.db",
        Path("conversations.db"),
    ]
    root = _package_root()
    if root is not None:
        candidates.append(root / "data" / "conversations.db")
        candidates.append(root / "conversations.db")
    exe_dir = _executable_dir()
    if exe_dir is not None:
        candidates.append(exe_dir / "data" / "conversations.db")
        candidates.append(exe_dir / "conversations.db")

    for src in candidates:
        if not src.is_file():
            continue
        try:
            if src.resolve() == dest.resolve():
                continue
        except Exception:
            pass
        try:
            shutil.copy2(src, dest)
            print(f"[LocalBot] Migrated conversations DB from {src} → {dest}")
            return True
        except Exception as exc:
            print(f"[LocalBot] DB migration failed from {src}: {exc}")
    return False


def load_preferences() -> dict:
    migrate_settings_if_needed()
    if PREFS_PATH.is_file():
        data = _read_json(PREFS_PATH)
        if data is not None:
            return data
    return {}


def save_preferences(prefs: dict) -> None:
    migrate_settings_if_needed()
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
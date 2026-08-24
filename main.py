#!/usr/bin/env python3
"""Local AI Assistant – Modern CustomTkinter version."""

import os
import sys
from pathlib import Path
from tkinter import messagebox

from assistant.conversation_store import ConversationStore
from assistant.engine import AssistantEngine

from llm.llama_runtime import LlamaRuntime
from llm.hardware import (
    detect_hardware,
    recommend_gpu_layers,
    recommend_context_size,
    format_hardware_summary,
)

from ui.main_window import MainWindow
from ui.settings import load_preferences


# ============================================================
# Application paths
# ============================================================

def get_app_data_dir() -> Path:
    """
    Return the directory used for writable LocalBot user data.

    macOS:
        ~/Library/Application Support/LocalBot

    Windows:
        %APPDATA%/LocalBot

    Linux/other:
        ~/.localbot
    """

    if sys.platform == "darwin":
        path = (
            Path.home()
            / "Library"
            / "Application Support"
            / "LocalBot"
        )

    elif sys.platform == "win32":
        path = (
            Path(
                os.environ.get(
                    "APPDATA",
                    Path.home() / "AppData" / "Roaming",
                )
            )
            / "LocalBot"
        )

    else:
        path = Path.home() / ".localbot"

    path.mkdir(parents=True, exist_ok=True)

    return path


# ============================================================
# Settings
# ============================================================

def resolve_settings():
    prefs = load_preferences()
    hw = detect_hardware()

    print("=== Hardware ===")
    print(format_hardware_summary(hw))
    print("================")

    # --------------------------------------------------------
    # Model path
    # --------------------------------------------------------

    model_path = (
        os.getenv("MY_ASSISTANT_MODEL")
        or prefs.get("model_path")
        or ""
    )

    model_size_mb = None

    if model_path:
        model_file = Path(model_path).expanduser()

        if model_file.is_file():
            model_size_mb = (
                model_file.stat().st_size
                / (1024 * 1024)
            )

    # --------------------------------------------------------
    # GPU layers
    # --------------------------------------------------------

    if "MY_ASSISTANT_GPU_LAYERS" in os.environ:

        gpu_layers = int(
            os.environ["MY_ASSISTANT_GPU_LAYERS"]
        )

    elif prefs.get("use_auto", "1") == "1":

        gpu_layers = recommend_gpu_layers(
            hw,
            model_size_mb=model_size_mb,
        )

    else:

        try:
            gpu_layers = int(
                prefs.get("gpu_layers", 0)
            )

        except (ValueError, TypeError):

            gpu_layers = recommend_gpu_layers(
                hw,
                model_size_mb=model_size_mb,
            )

    # --------------------------------------------------------
    # Context size
    # --------------------------------------------------------

    if "MY_ASSISTANT_CONTEXT" in os.environ:

        context_size = int(
            os.environ["MY_ASSISTANT_CONTEXT"]
        )

    elif prefs.get("use_auto", "1") == "1":

        context_size = recommend_context_size(hw)

    else:

        try:
            context_size = int(
                prefs.get("context_size", 8192)
            )

        except (ValueError, TypeError):

            context_size = recommend_context_size(hw)

    # --------------------------------------------------------
    # Models directory
    # --------------------------------------------------------

    default_models_dir = (
        get_app_data_dir() / "models"
    )

    models_dir = (
        prefs.get("models_dir")
        or str(default_models_dir)
    )

    # Expand ~ if the user configured it.
    models_dir = str(
        Path(models_dir).expanduser()
    )

    # Make sure the directory exists.
    Path(models_dir).mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        model_path,
        gpu_layers,
        context_size,
        models_dir,
        hw,
    )


# ============================================================
# Main
# ============================================================

def main():

    print("Starting Local AI Assistant...")

    # --------------------------------------------------------
    # Application data directory
    # --------------------------------------------------------

    app_data_dir = get_app_data_dir()

    print(f"Application data: {app_data_dir}")

    # --------------------------------------------------------
    # Resolve settings and hardware
    # --------------------------------------------------------

    (
        model_path,
        gpu_layers,
        context_size,
        models_dir,
        _hw,
    ) = resolve_settings()

    print(f"Model      : {model_path or '(none)'}")
    print(f"GPU layers : {gpu_layers}")
    print(f"Context    : {context_size}")
    print(f"Models dir : {models_dir}")

    # --------------------------------------------------------
    # Conversation database
    # --------------------------------------------------------

    conversations_db = (
        app_data_dir / "conversations.db"
    )

    store = ConversationStore(
        str(conversations_db)
    )

    # --------------------------------------------------------
    # Load LLM
    # --------------------------------------------------------

    llm = None

    if model_path:

        model_file = Path(
            model_path
        ).expanduser()

        if model_file.is_file():

            try:

                print("Loading model...")

                llm = LlamaRuntime(
                    model_path=str(model_file),
                    context_size=context_size,
                    gpu_layers=gpu_layers,
                )

                # Store the normalized absolute path.
                model_path = str(
                    model_file.resolve()
                )

            except Exception as exc:

                print(
                    "Model load failed:",
                    exc,
                )

                try:

                    messagebox.showwarning(
                        "Could not load model",
                        (
                            "Starting without a model."
                            "\n\n"
                            f"{exc}"
                        ),
                    )

                except Exception:
                    pass

                model_path = ""

        else:

            print(
                f"Model file not found: {model_file}"
            )

            model_path = ""

    # --------------------------------------------------------
    # Assistant engine
    # --------------------------------------------------------

    engine = AssistantEngine(
        llm=llm,
        store=store,
    )

    # --------------------------------------------------------
    # Main window
    # --------------------------------------------------------

    print("Creating window...")

    app = MainWindow(
        engine=engine,
        model_path=model_path,
        gpu_layers=gpu_layers,
        context_size=context_size,
        models_dir=models_dir,
    )

    print(
        "Window created, starting mainloop..."
    )

    app.mainloop()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
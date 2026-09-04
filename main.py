#!/usr/bin/env python3
"""Local AI Assistant – Modern CustomTkinter version."""

import multiprocessing
import os
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
from ui.settings import (
    get_app_data_dir,
    load_preferences,
    migrate_conversations_db_if_needed,
)


def resolve_settings():
    prefs = load_preferences()
    hw = detect_hardware()

    print("=== Hardware ===")
    print(format_hardware_summary(hw))
    print("================")

    model_path = (
        os.getenv("MY_ASSISTANT_MODEL")
        or prefs.get("model_path")
        or ""
    )

    model_size_mb = None
    if model_path:
        model_file = Path(model_path).expanduser()
        if model_file.is_file():
            model_size_mb = model_file.stat().st_size / (1024 * 1024)

    if "MY_ASSISTANT_GPU_LAYERS" in os.environ:
        gpu_layers = int(os.environ["MY_ASSISTANT_GPU_LAYERS"])
    elif prefs.get("use_auto", "1") == "1":
        gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)
    else:
        try:
            gpu_layers = int(prefs.get("gpu_layers", 0))
        except (ValueError, TypeError):
            gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)

    if "MY_ASSISTANT_CONTEXT" in os.environ:
        context_size = int(os.environ["MY_ASSISTANT_CONTEXT"])
    elif prefs.get("use_auto", "1") == "1":
        context_size = recommend_context_size(hw)
    else:
        try:
            context_size = int(prefs.get("context_size", 8192))
        except (ValueError, TypeError):
            context_size = recommend_context_size(hw)

    default_models_dir = get_app_data_dir() / "models"
    models_dir = prefs.get("models_dir") or str(default_models_dir)
    models_dir = str(Path(models_dir).expanduser())
    Path(models_dir).mkdir(parents=True, exist_ok=True)

    return model_path, gpu_layers, context_size, models_dir, hw


def main():
    print("Starting Local AI Assistant...")

    app_data_dir = get_app_data_dir()
    print(f"Application data: {app_data_dir}")

    migrate_conversations_db_if_needed()

    model_path, gpu_layers, context_size, models_dir, _hw = resolve_settings()

    print(f"Model      : {model_path or '(none)'}")
    print(f"GPU layers : {gpu_layers}")
    print(f"Context    : {context_size}")
    print(f"Models dir : {models_dir}")

    store = ConversationStore(str(app_data_dir / "conversations.db"))

    llm = None
    if model_path:
        model_file = Path(model_path).expanduser()
        if model_file.is_file():
            try:
                print("Loading model...")
                llm = LlamaRuntime(
                    model_path=str(model_file),
                    context_size=context_size,
                    gpu_layers=gpu_layers,
                )
                model_path = str(model_file.resolve())
            except Exception as exc:
                print("Model load failed:", exc)
                try:
                    messagebox.showwarning(
                        "Could not load model",
                        f"Starting without a model.\n\n{exc}",
                    )
                except Exception:
                    pass
                model_path = ""
        else:
            print(f"Model file not found: {model_file}")
            model_path = ""

    engine = AssistantEngine(llm=llm, store=store)

    print("Creating window...")
    app = MainWindow(
        engine=engine,
        model_path=model_path,
        gpu_layers=gpu_layers,
        context_size=context_size,
        models_dir=models_dir,
    )
    print("Window created, starting mainloop...")
    app.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

#!/usr/bin/env python3
"""Local AI Assistant – Modern CustomTkinter version"""

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
from ui.settings import load_preferences


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
    if model_path and Path(model_path).is_file():
        model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)

    # GPU layers
    if "MY_ASSISTANT_GPU_LAYERS" in os.environ:
        gpu_layers = int(os.environ["MY_ASSISTANT_GPU_LAYERS"])
    elif prefs.get("use_auto", "1") == "1":
        gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)
    else:
        try:
            gpu_layers = int(prefs.get("gpu_layers", 0))
        except ValueError:
            gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)

    # Context size
    if "MY_ASSISTANT_CONTEXT" in os.environ:
        context_size = int(os.environ["MY_ASSISTANT_CONTEXT"])
    elif prefs.get("use_auto", "1") == "1":
        context_size = recommend_context_size(hw)
    else:
        try:
            context_size = int(prefs.get("context_size", 8192))
        except ValueError:
            context_size = recommend_context_size(hw)

    models_dir = prefs.get("models_dir") or "models"
    return model_path, gpu_layers, context_size, models_dir, hw


def main():
    print("Starting Local AI Assistant...")

    model_path, gpu_layers, context_size, models_dir, _hw = resolve_settings()

    print(f"Model      : {model_path or '(none)'}")
    print(f"GPU layers : {gpu_layers}")
    print(f"Context    : {context_size}")

    store = ConversationStore("data/conversations.db")
    llm = None

    if model_path and Path(model_path).is_file():
        try:
            print("Loading model...")
            llm = LlamaRuntime(
                model_path=model_path,
                context_size=context_size,
                gpu_layers=gpu_layers,
            )
        except Exception as exc:
            print("Model load failed:", exc)
            messagebox.showwarning(
                "Could not load model",
                f"Starting without a model.\n\n{exc}",
            )
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
    main()
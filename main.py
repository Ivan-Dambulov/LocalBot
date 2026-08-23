import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QStyleFactory

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
from ui.settings_dialog import load_preferences


def _resolve_settings():
    prefs = load_preferences("data/settings.ini")

    # No hardcoded default model
    model_path = os.getenv("MY_ASSISTANT_MODEL") or prefs.get("model_path") or ""

    hw = detect_hardware()
    print("=== Hardware ===")
    print(format_hardware_summary(hw))
    print("================")

    model_size_mb = None
    if model_path and os.path.isfile(model_path):
        model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)

    if "MY_ASSISTANT_GPU_LAYERS" in os.environ:
        gpu_layers = int(os.environ["MY_ASSISTANT_GPU_LAYERS"])
    elif prefs.get("use_auto", "1") == "1" or "gpu_layers" not in prefs:
        gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)
    else:
        try:
            gpu_layers = int(prefs["gpu_layers"])
        except ValueError:
            gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)

    if "MY_ASSISTANT_CONTEXT" in os.environ:
        context_size = int(os.environ["MY_ASSISTANT_CONTEXT"])
    elif prefs.get("use_auto", "1") == "1" or "context_size" not in prefs:
        context_size = recommend_context_size(hw, default=8192)
    else:
        try:
            context_size = int(prefs["context_size"])
        except ValueError:
            context_size = recommend_context_size(hw, default=8192)

    models_dir = prefs.get("models_dir") or "models"
    return model_path, gpu_layers, context_size, models_dir, hw


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Assistant")
    app.setOrganizationName("MyAssistant")
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    model_path, gpu_layers, context_size, models_dir, _hw = _resolve_settings()

    print(f"Model: {model_path or '(none — pick in Model Manager)'}")
    print(f"GPU layers: {gpu_layers}")
    print(f"Context size: {context_size}")

    llm = None
    if model_path and os.path.isfile(model_path):
        try:
            llm = LlamaRuntime(
                model_path=model_path,
                context_size=context_size,
                gpu_layers=gpu_layers,
            )
        except Exception as exc:
            QMessageBox.warning(
                None,
                "Could not load model",
                f"Starting without a model.\n\n{exc}",
            )
            llm = None
            model_path = ""

    store = ConversationStore("data/conversations.db")
    engine = AssistantEngine(llm=llm, store=store)

    window = MainWindow(
        engine,
        model_path=model_path or "",
        gpu_layers=gpu_layers,
        context_size=context_size,
        models_dir=models_dir,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
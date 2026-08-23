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
    """
    Priority:
      1. Environment variables (highest)
      2. data/settings.ini from Settings dialog
      3. Hardware auto-detection
      4. Built-in defaults
    """
    prefs = load_preferences("data/settings.ini")

    default_model = "models/Qwen3-4B-Q4_K_M.gguf"
    model_path = os.getenv(
        "MY_ASSISTANT_MODEL",
        prefs.get("model_path") or default_model,
    )
    if not model_path:
        model_path = default_model

    hw = detect_hardware()
    print("=== Hardware ===")
    print(format_hardware_summary(hw))
    print("================")

    model_size_mb = None
    if os.path.isfile(model_path):
        model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)

    # GPU layers
    if "MY_ASSISTANT_GPU_LAYERS" in os.environ:
        gpu_layers = int(os.environ["MY_ASSISTANT_GPU_LAYERS"])
    elif prefs.get("use_auto", "1") == "1" or "gpu_layers" not in prefs:
        gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)
    else:
        try:
            gpu_layers = int(prefs["gpu_layers"])
        except ValueError:
            gpu_layers = recommend_gpu_layers(hw, model_size_mb=model_size_mb)

    # Context
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
    # Fusion gives a clean base; our stylesheet adds the macOS look
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    model_path, gpu_layers, context_size, models_dir, _hw = _resolve_settings()

    print(f"Model: {model_path}")
    print(f"GPU layers: {gpu_layers}")
    print(f"Context size: {context_size}")

    if not os.path.isfile(model_path):
        QMessageBox.critical(
            None,
            "Model not found",
            (
                f"Could not find the LLM model:\n\n{model_path}\n\n"
                "Place a GGUF model in the models folder, "
                "use Settings → Models, or set MY_ASSISTANT_MODEL."
            ),
        )
        sys.exit(1)

    store = ConversationStore("data/conversations.db")

    try:
        llm = LlamaRuntime(
            model_path=model_path,
            context_size=context_size,
            gpu_layers=gpu_layers,
        )
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Could not load model",
            f"The LLM model could not be loaded.\n\n{exc}",
        )
        sys.exit(1)

    engine = AssistantEngine(llm=llm, store=store)

    window = MainWindow(
        engine,
        model_path=model_path,
        gpu_layers=gpu_layers,
        context_size=context_size,
        models_dir=models_dir,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

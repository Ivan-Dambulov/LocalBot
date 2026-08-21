import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from assistant.conversation_store import ConversationStore
from assistant.engine import AssistantEngine
from llm.llama_runtime import LlamaRuntime
from ui.main_window import MainWindow




MODEL_PATH = os.getenv(
    "MY_ASSISTANT_MODEL",
    "models/Qwen3-4B-Q4_K_M.gguf"
)

# Number of GPU layers.

# 0  = CPU only
# -1 = use as many GPU layers as possible
#
# Start with 0 if you are unsure.
GPU_LAYERS = int(
    os.getenv("MY_ASSISTANT_GPU_LAYERS", "0")
)

CONTEXT_SIZE = int(
    os.getenv("MY_ASSISTANT_CONTEXT", "8192")
)


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("My Assistant")
    app.setOrganizationName("MyAssistant")



    if not os.path.isfile(MODEL_PATH):
        QMessageBox.critical(
            None,
            "Model not found",
            (
                f"Could not find the LLM model:\n\n"
                f"{MODEL_PATH}\n\n"
                f"Place a GGUF model in the models folder "
                f"or set the MY_ASSISTANT_MODEL environment "
                f"variable."
            )
        )

        sys.exit(1)



    store = ConversationStore(
        "data/conversations.db"
    )



    try:
        llm = LlamaRuntime(
            model_path=MODEL_PATH,
            context_size=CONTEXT_SIZE,
            gpu_layers=GPU_LAYERS
        )

    except Exception as exc:
        QMessageBox.critical(
            None,
            "Could not load model",
            (
                "The LLM model could not be loaded.\n\n"
                f"{exc}"
            )
        )

        sys.exit(1)


    engine = AssistantEngine(
        llm=llm,
        store=store
    )

    window = MainWindow(engine)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
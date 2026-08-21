Right now you get:

A clean PySide6 desktop app
Local GGUF models running through llama.cpp
SQLite-backed conversation history
Streaming responses
Multiple saved chats and a New Conversation button

Everything works without an internet connection. Your chats stay on your machine.

You need to create folder /models/ and download Qwen3-4B-Q4_K_M.gguf from Hugging Face or change model in main.py with the one you want

MODEL_PATH = os.getenv(
    "MY_ASSISTANT_MODEL",
    "models/Qwen3-4B-Q4_K_M.gguf"
)


Future updates:
Model manager with hardware detection
Tool system (web search, file access)
Plugins and an auto-updater

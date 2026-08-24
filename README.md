# LocalBot

**A lightweight desktop application for running AI models locally.**

LocalBot provides a simple interface for running GGUF language models directly on your computer using `llama.cpp`, with local conversation storage and automatic hardware optimization.

> **⚠️ BETA**
>
> LocalBot is currently in **beta**. The project is actively under development, and bugs, performance issues, and missing features are still being worked on. Expect changes as the project evolves.

## Features

* Local LLM inference with **GGUF** models
* Powered by **llama-cpp-python**
* Streaming responses
* Persistent conversations using SQLite
* Model Manager with Hugging Face downloads
* Automatic CPU/GPU and memory detection
* Automatic GPU-layer and context-size recommendations
* NVIDIA, AMD, Apple Silicon, and CPU support
* Dark/Light mode

## Requirements

* Python 3.10+
* A compatible GGUF model
* Sufficient RAM/VRAM for the selected model

## Installation

```bash
git clone https://github.com/Ivan-Dambulov/LocalBot.git
cd LocalBot

python -m venv .venv
```

Activate the virtual environment:

**Linux / macOS**

```bash
source .venv/bin/activate
```

**Windows**

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install customtkinter
```

Run LocalBot:

```bash
python main.py
```

## Models

LocalBot uses **GGUF** models and includes a Model Manager for discovering, downloading, and selecting supported models.

Models are stored locally and inference is performed on your machine. No remote AI API is required for model execution.

For best performance, choose a model and quantization appropriate for your available RAM/VRAM.


## Development Status

LocalBot is actively developed. New features, hardware support, model integrations, performance improvements, and bug fixes are being worked on.

Because the project is currently in **beta**, behavior and configuration may change between releases.

If you encounter a bug or have a feature request, please open an issue on GitHub.

## License

No license has currently been specified for the project.

## Links

**Repository:**
https://github.com/Ivan-Dambulov/LocalBot

---

**LocalBot — private, local AI for your desktop.**

# Local AI Assistant

A privacy-first desktop chat app that runs large language models **entirely on your machine**.

Built with Python, PySide6, and llama.cpp. No cloud API for chat. No account. Conversations stay in a local SQLite database.

---

## What it does

Local AI Assistant is a small desktop client for **GGUF** models. You chat in a familiar interface; inference runs offline through llama.cpp. A built-in **Model Manager** detects your hardware, scores which models fit, and can download GGUF files from Hugging Face.

---

**Still in BETA, bugs and features are being worked on.**

---

## Features

### Chat
- Streaming responses token-by-token  
- Multiple conversations with automatic titles from the first message  
- History stored locally in SQLite (`data/conversations.db`)  
- Clear conversations by scope: **today**, **last 7 days**, or **all**  
- Empty chats are not saved until you send a message  

### Hardware awareness
- Detects **NVIDIA (CUDA)**, **Apple Silicon (Metal)**, and **AMD (ROCm)** when available  
- Reads CPU cores and system RAM  
- Suggests GPU layer offload and context size  
- Environment variables still override auto settings  

### Model Manager
- Compact hardware summary (with optional full details)  
- List of **installed** local `.gguf` models with one-click **Use**  
- Curated catalog (Qwen3 / Qwen3.5 / Qwen3.8, NVIDIA Nemotron, Llama, Mistral, Phi, Gemma, DeepSeek, …)  
- Compatibility labels: Excellent · Recommended · Possible · Slow · Not compatible  
- Quant picker and **Download** to your `models/` folder (progress + resume)  
- Optional Hugging Face token for gated models  

### Appearance
- macOS-inspired light UI  
- Light / Dark toggle (top-right); preference is remembered  

### Privacy
- Chat does not require the internet  
- Network is only used when you explicitly download a model  
- No telemetry built into the app  

### Still in works
- Tools
- Web Search
- Conversation summery

---

## Requirements

| | |
|---|---|
| **OS** | Windows, macOS, or Linux |
| **Python** | 3.10 or newer |
| **RAM** | 8 GB minimum · 16 GB+ recommended |
| **Disk** | Space for GGUF files (typically a few GB each) |
| **GPU** | Optional (CPU works; CUDA / Metal / ROCm speed things up) |

---

## Quick start

```bash
git clone https://github.com/Ivan-Dambulov/Local_AI_assistant.git
cd Local_AI_assistant

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt

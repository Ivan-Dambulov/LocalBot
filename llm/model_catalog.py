"""
Curated GGUF model catalog — keep this file updated independently of the UI.

Focus: recent, practical local models. Filenames are hints; the downloader
resolves the real name from the Hub by quant label when needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QuantOption:
    label: str
    filename: str
    size_gb: float
    quality: str = "balanced"


@dataclass
class CatalogModel:
    id: str
    name: str
    family: str
    params_b: float
    repo_id: str
    quants: List[QuantOption] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    blurb: str = ""
    priority: int = 100  # lower = higher in list


CATALOG: List[CatalogModel] = [

    # ── Qwen 3.5 / 3.8 (newest) ──────────────────────────────────────────
    CatalogModel(
        id="qwen3.5-4b",
        name="Qwen3.5 4B",
        family="Qwen",
        params_b=4.0,
        repo_id="unsloth/Qwen3-4B-Instruct-2507-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", 2.5),
            QuantOption("Q5_K_M", "Qwen3-4B-Instruct-2507-Q5_K_M.gguf", 2.9),
            QuantOption("Q8_0", "Qwen3-4B-Instruct-2507-Q8_0.gguf", 4.3, "high"),
        ],
        tags=["chat"],
        blurb="Fast everyday model.",
        priority=3,
    ),
    CatalogModel(
        id="qwen3-8b",
        name="Qwen3 8B",
        family="Qwen",
        params_b=8.0,
        repo_id="bartowski/Qwen_Qwen3-8B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Qwen_Qwen3-8B-Q4_K_M.gguf", 5.0),
            QuantOption("Q5_K_M", "Qwen_Qwen3-8B-Q5_K_M.gguf", 5.8),
            QuantOption("Q6_K", "Qwen_Qwen3-8B-Q6_K.gguf", 6.7),
            QuantOption("Q8_0", "Qwen_Qwen3-8B-Q8_0.gguf", 8.7, "high"),
        ],
        tags=["chat", "coding"],
        blurb="Strong default for 8–12 GB GPUs.",
        priority=1,
    ),
    CatalogModel(
        id="qwen3-14b",
        name="Qwen3 14B",
        family="Qwen",
        params_b=14.0,
        repo_id="unsloth/Qwen3-14B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Qwen3-14B-Q4_K_M.gguf", 9.0),
            QuantOption("Q5_K_M", "Qwen3-14B-Q5_K_M.gguf", 10.5),
            QuantOption("Q6_K", "Qwen3-14B-Q6_K.gguf", 12.0),
        ],
        tags=["chat", "reasoning"],
        blurb="Higher quality; needs ~12 GB+ VRAM for Q4.",
        priority=8,
    ),
    CatalogModel(
        id="qwen3.8-27b",
        name="Qwen3.8 27B",
        family="Qwen",
        params_b=27.0,
        repo_id="bartowski/Qwen3.8-27B-GGUF",
        quants=[
            QuantOption("Q3_K_M", "Qwen3.8-27B-Q3_K_M.gguf", 13.5, "fast"),
            QuantOption("Q4_K_M", "Qwen3.8-27B-Q4_K_M.gguf", 16.5),
            QuantOption("Q5_K_M", "Qwen3.8-27B-Q5_K_M.gguf", 19.5),
        ],
        tags=["chat", "reasoning", "coding"],
        blurb="Top dense Qwen for local use. 24 GB+ ideal.",
        priority=5,
    ),
    CatalogModel(
        id="qwen3-1.7b",
        name="Qwen3 1.7B",
        family="Qwen",
        params_b=1.7,
        repo_id="bartowski/Qwen_Qwen3-1.7B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Qwen3-1.7B-Q4_K_M.gguf", 1.1),
            QuantOption("Q8_0", "Qwen3-1.7B-Q8_0.gguf", 2.2, "high"),
        ],
        tags=["chat", "fast"],
        blurb="Tiny and quick for weak hardware.",
        priority=20,
    ),

    # ── NVIDIA Nemotron ──────────────────────────────────────────────────
    CatalogModel(
        id="nemotron-3-nano-4b",
        name="Nemotron 3 Nano 4B",
        family="NVIDIA",
        params_b=4.0,
        repo_id="bartowski/nvidia_Nemotron-3-Nano-4B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Nemotron-3-Nano-4B-Q4_K_M.gguf", 2.6),
            QuantOption("Q5_K_M", "Nemotron-3-Nano-4B-Q5_K_M.gguf", 3.0),
            QuantOption("Q8_0", "Nemotron-3-Nano-4B-Q8_0.gguf", 4.2, "high"),
        ],
        tags=["chat"],
        blurb="NVIDIA small instruct model.",
        priority=6,
    ),
    CatalogModel(
        id="nemotron-cascade-8b",
        name="Nemotron Cascade 8B Thinking",
        family="NVIDIA",
        params_b=8.0,
        repo_id="bartowski/nvidia_Nemotron-Cascade-8B-Thinking-GGUF",
        quants=[
            QuantOption("Q4_K_M", "nvidia_Nemotron-Cascade-8B-Thinking-Q4_K_M.gguf", 4.8),
            QuantOption("Q5_K_M", "nvidia_Nemotron-Cascade-8B-Thinking-Q5_K_M.gguf", 5.6),
            QuantOption("Q6_K", "nvidia_Nemotron-Cascade-8B-Thinking-Q6_K.gguf", 6.5),
        ],
        tags=["reasoning", "chat"],
        blurb="NVIDIA reasoning-oriented 8B.",
        priority=7,
    ),
    CatalogModel(
        id="openmath-nemotron-7b",
        name="OpenMath Nemotron 7B",
        family="NVIDIA",
        params_b=7.0,
        repo_id="bartowski/nvidia_OpenMath-Nemotron-7B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "nvidia_OpenMath-Nemotron-7B-Q4_K_M.gguf", 4.4),
            QuantOption("Q5_K_M", "nvidia_OpenMath-Nemotron-7B-Q5_K_M.gguf", 5.1),
            QuantOption("Q8_0", "nvidia_OpenMath-Nemotron-7B-Q8_0.gguf", 7.7, "high"),
        ],
        tags=["math", "reasoning"],
        blurb="Math-focused Nemotron.",
        priority=18,
    ),
    CatalogModel(
        id="acereason-nemotron-14b",
        name="AceReason Nemotron 14B",
        family="NVIDIA",
        params_b=14.0,
        repo_id="bartowski/nvidia_AceReason-Nemotron-14B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "nvidia_AceReason-Nemotron-14B-Q4_K_M.gguf", 8.5),
            QuantOption("Q5_K_M", "nvidia_AceReason-Nemotron-14B-Q5_K_M.gguf", 10.0),
            QuantOption("Q6_K", "nvidia_AceReason-Nemotron-14B-Q6_K.gguf", 11.5),
        ],
        tags=["reasoning", "math", "coding"],
        blurb="NVIDIA reasoning 14B.",
        priority=12,
    ),

    # ── Llama ────────────────────────────────────────────────────────────
    CatalogModel(
        id="llama3.2-3b",
        name="Llama 3.2 3B",
        family="Llama",
        params_b=3.0,
        repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Llama-3.2-3B-Instruct-Q4_K_M.gguf", 2.0),
            QuantOption("Q8_0", "Llama-3.2-3B-Instruct-Q8_0.gguf", 3.4, "high"),
        ],
        tags=["chat"],
        blurb="Compact Meta model.",
        priority=15,
    ),
    CatalogModel(
        id="llama3.1-8b",
        name="Llama 3.1 8B",
        family="Llama",
        params_b=8.0,
        repo_id="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", 4.9),
            QuantOption("Q5_K_M", "Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf", 5.7),
            QuantOption("Q8_0", "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf", 8.5, "high"),
        ],
        tags=["chat", "coding"],
        blurb="Reliable Meta baseline.",
        priority=10,
    ),

    # ── Mistral / Phi / Gemma (still useful) ─────────────────────────────
    CatalogModel(
        id="mistral-7b",
        name="Mistral 7B Instruct",
        family="Mistral",
        params_b=7.0,
        repo_id="bartowski/Mistral-7B-Instruct-v0.3-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf", 4.4),
            QuantOption("Q5_K_M", "Mistral-7B-Instruct-v0.3-Q5_K_M.gguf", 5.1),
            QuantOption("Q8_0", "Mistral-7B-Instruct-v0.3-Q8_0.gguf", 7.7, "high"),
        ],
        tags=["chat"],
        blurb="Classic efficient 7B.",
        priority=25,
    ),
    CatalogModel(
        id="phi-3.5-mini",
        name="Phi-3.5 Mini",
        family="Phi",
        params_b=3.8,
        repo_id="bartowski/Phi-3.5-mini-instruct-GGUF",
        quants=[
            QuantOption("Q4_K_M", "Phi-3.5-mini-instruct-Q4_K_M.gguf", 2.4),
            QuantOption("Q8_0", "Phi-3.5-mini-instruct-Q8_0.gguf", 4.1, "high"),
        ],
        tags=["chat", "reasoning"],
        blurb="Small Microsoft model.",
        priority=16,
    ),
    CatalogModel(
        id="gemma2-9b",
        name="Gemma 2 9B",
        family="Gemma",
        params_b=9.0,
        repo_id="bartowski/gemma-2-9b-it-GGUF",
        quants=[
            QuantOption("Q4_K_M", "gemma-2-9b-it-Q4_K_M.gguf", 5.8),
            QuantOption("Q5_K_M", "gemma-2-9b-it-Q5_K_M.gguf", 6.7),
        ],
        tags=["chat"],
        blurb="Google open 9B.",
        priority=22,
    ),

    # ── DeepSeek ─────────────────────────────────────────────────────────
    CatalogModel(
        id="deepseek-r1-7b",
        name="DeepSeek R1 Distill 7B",
        family="DeepSeek",
        params_b=7.0,
        repo_id="bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF",
        quants=[
            QuantOption("Q4_K_M", "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf", 4.7),
            QuantOption("Q5_K_M", "DeepSeek-R1-Distill-Qwen-7B-Q5_K_M.gguf", 5.4),
        ],
        tags=["reasoning", "coding"],
        blurb="Distilled reasoning model.",
        priority=11,
    ),
]


# ── Compatibility ────────────────────────────────────────────────────────────

@dataclass
class Compatibility:
    level: str
    label: str
    color: str
    score: float
    detail: str = ""


def estimate_max_params_b(vram_mb: int, ram_gb: float, shared_memory: bool) -> float:
    if shared_memory:
        usable_gb = max(0.0, ram_gb - 4.0) * 0.55
    else:
        usable_gb = max(0.0, (vram_mb / 1024.0) - 1.8)
    if usable_gb <= 0:
        return 1.0
    return usable_gb / 0.6


def score_quant_for_hardware(
    size_gb: float,
    vram_mb: int,
    ram_gb: float,
    shared_memory: bool,
) -> Compatibility:
    if shared_memory:
        usable_gb = max(0.0, ram_gb - 3.0) * 0.70
        tight_gb = max(0.0, ram_gb - 2.0) * 0.85
    else:
        usable_gb = max(0.0, vram_mb / 1024.0 - 1.5)
        tight_gb = max(0.0, vram_mb / 1024.0 - 0.5)
        if size_gb > tight_gb and size_gb > ram_gb * 0.75:
            return Compatibility("incompatible", "Not compatible", "#c0392b", 5)

    if size_gb <= usable_gb * 0.75:
        return Compatibility("excellent", "Excellent", "#27ae60", 95)
    if size_gb <= usable_gb:
        return Compatibility("good", "Recommended", "#2ecc71", 80)
    if size_gb <= tight_gb:
        return Compatibility("possible", "Possible", "#f39c12", 55)
    if size_gb <= max(usable_gb, tight_gb) * 1.6 or size_gb < ram_gb * 0.7:
        return Compatibility("slow", "Slow", "#e67e22", 30)
    return Compatibility("incompatible", "Not compatible", "#c0392b", 5)


def best_quant_for_hardware(
    model: CatalogModel,
    vram_mb: int,
    ram_gb: float,
    shared_memory: bool,
) -> Optional[QuantOption]:
    ranked = []
    for q in model.quants:
        comp = score_quant_for_hardware(q.size_gb, vram_mb, ram_gb, shared_memory)
        ranked.append((comp.score, q.quality != "fast", q))
    ranked.sort(key=lambda t: (-t[0], -t[1]))
    if not ranked:
        return None
    for score, _, q in ranked:
        if score >= 50:
            return q
    return ranked[0][2]


def families() -> List[str]:
    seen = []
    for m in CATALOG:
        if m.family not in seen:
            seen.append(m.family)
    return seen


def models_for_family(family: str) -> List[CatalogModel]:
    if family in ("", "All"):
        return sorted(CATALOG, key=lambda m: (m.priority, m.params_b))
    return sorted(
        [m for m in CATALOG if m.family == family],
        key=lambda m: (m.priority, m.params_b),
    )

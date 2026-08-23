"""
Model manager: scan local GGUF files, estimate fit vs hardware, recommend quant.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from llm.hardware import HardwareInfo, recommend_gpu_layers, recommend_context_size


# Rough relative size of common quantizations vs FP16 (for display / ranking)
QUANT_WEIGHT = {
    "f16": 1.00,
    "bf16": 1.00,
    "q8_0": 0.53,
    "q6_k": 0.41,
    "q5_k_m": 0.36,
    "q5_k_s": 0.35,
    "q5_0": 0.35,
    "q4_k_m": 0.29,
    "q4_k_s": 0.28,
    "q4_0": 0.27,
    "q3_k_m": 0.23,
    "q3_k_s": 0.21,
    "q2_k": 0.18,
    "iq4_xs": 0.26,
    "iq3_xxs": 0.19,
}


@dataclass
class ModelInfo:
    path: str
    filename: str
    size_mb: float
    quant: str  # e.g. "Q4_K_M" or "unknown"
    param_hint: str  # e.g. "4B", "7B", "" if unknown
    fits_vram: bool
    fits_ram: bool
    recommended_gpu_layers: int
    recommended_context: int
    score: float  # higher = better match for this machine
    notes: str = ""

    @property
    def size_gb(self) -> float:
        return self.size_mb / 1024.0


def scan_models(
    models_dir: str | Path,
    hardware: HardwareInfo,
    default_context: int = 8192,
) -> List[ModelInfo]:
    """Scan a folder for .gguf files and score them against hardware."""
    models_dir = Path(models_dir)
    if not models_dir.is_dir():
        return []

    results: List[ModelInfo] = []
    for path in sorted(models_dir.glob("*.gguf")):
        try:
            size_mb = path.stat().st_size / (1024 * 1024)
        except OSError:
            continue

        quant = _parse_quant(path.name)
        param_hint = _parse_param_hint(path.name)

        gpu_layers = recommend_gpu_layers(hardware, model_size_mb=size_mb)
        ctx = recommend_context_size(hardware, default=default_context)

        # VRAM / RAM fit heuristics
        vram_budget = hardware.primary_vram_mb
        g = hardware.primary_gpu
        if g and g.shared_memory:
            # Unified memory: model + KV need to share system RAM
            fits_vram = size_mb < (hardware.total_ram_gb * 1024 * 0.55)
            fits_ram = size_mb < (hardware.total_ram_gb * 1024 * 0.70)
        else:
            # Leave ~1.5–2 GB for KV + overhead when checking full offload
            fits_vram = vram_budget <= 0 or size_mb < max(0, vram_budget - 1800)
            fits_ram = size_mb < (hardware.total_ram_gb * 1024 * 0.75)

        score, notes = _score_model(
            size_mb=size_mb,
            quant=quant,
            fits_vram=fits_vram,
            fits_ram=fits_ram,
            gpu_layers=gpu_layers,
            hardware=hardware,
        )

        results.append(
            ModelInfo(
                path=str(path.resolve()),
                filename=path.name,
                size_mb=size_mb,
                quant=quant,
                param_hint=param_hint,
                fits_vram=fits_vram,
                fits_ram=fits_ram,
                recommended_gpu_layers=gpu_layers,
                recommended_context=ctx,
                score=score,
                notes=notes,
            )
        )

    results.sort(key=lambda m: (-m.score, m.size_mb))
    return results


def best_model(
    models_dir: str | Path,
    hardware: HardwareInfo,
) -> Optional[ModelInfo]:
    models = scan_models(models_dir, hardware)
    return models[0] if models else None


def format_model_row(m: ModelInfo) -> str:
    fit = []
    if m.fits_vram:
        fit.append("VRAM OK")
    else:
        fit.append("VRAM tight")
    if m.fits_ram:
        fit.append("RAM OK")
    else:
        fit.append("RAM tight")
    param = f" · {m.param_hint}" if m.param_hint else ""
    quant = f" · {m.quant}" if m.quant != "unknown" else ""
    return (
        f"{m.filename}{param}{quant}  "
        f"({m.size_gb:.2f} GB)  [{', '.join(fit)}]"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUANT_RE = re.compile(
    r"(q[2-8](?:_[k01]|_k_[msxl]+)?|iq[1-4]_[a-z]+|f16|bf16|fp16)",
    re.IGNORECASE,
)

_PARAM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[bB]\b|(?:[-_])(\d+(?:\.\d+)?)[bB](?:[-_.]|$)"
)


def _parse_quant(filename: str) -> str:
    stem = Path(filename).stem
    matches = _QUANT_RE.findall(stem)
    if not matches:
        return "unknown"
    # Prefer the last match (usually the actual quant suffix)
    return matches[-1].upper().replace("FP16", "F16")


def _parse_param_hint(filename: str) -> str:
    stem = Path(filename).stem
    m = _PARAM_RE.search(stem)
    if not m:
        return ""
    val = m.group(1) or m.group(2)
    return f"{val}B"


def _score_model(
    *,
    size_mb: float,
    quant: str,
    fits_vram: bool,
    fits_ram: bool,
    gpu_layers: int,
    hardware: HardwareInfo,
) -> tuple[float, str]:
    """
    Higher score = better default choice for this machine.
    Prefer models that fit in VRAM, then quality quant, then not oversized.
    """
    score = 50.0
    notes: list[str] = []

    if fits_vram:
        score += 40
        notes.append("fits GPU memory")
    else:
        score -= 15
        notes.append("may need partial offload / CPU")

    if fits_ram:
        score += 15
    else:
        score -= 25
        notes.append("may not fit in RAM")

    if gpu_layers != 0:
        score += 10

    q = quant.lower()
    # Prefer Q4_K_M / Q5_K_M as good quality/size balance
    preferred = ("q4_k_m", "q5_k_m", "q4_k_s", "q5_k_s", "q6_k")
    if q in preferred:
        score += 12 - preferred.index(q)
        notes.append(f"solid quant ({quant})")
    elif q in ("q8_0", "f16", "bf16"):
        score += 5
        notes.append("high quality, larger file")
    elif q.startswith("q2") or q.startswith("iq2"):
        score -= 5
        notes.append("very aggressive quant")

    # Mild preference for not-huge models on modest hardware
    vram = hardware.primary_vram_mb
    if vram and size_mb > vram:
        score -= min(20, (size_mb - vram) / 500)

    return score, "; ".join(notes) if notes else "ok"

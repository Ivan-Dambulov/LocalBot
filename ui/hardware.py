"""
Hardware detection for Local AI Assistant.

Supports:
  - NVIDIA (CUDA) via NVML / nvidia-smi
  - Apple Silicon (Metal) via sysctl / platform
  - AMD (ROCm) via rocminfo / rocm-smi when available
  - CPU cores + system RAM

Used to recommend n_gpu_layers and context size for llama.cpp.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GPUInfo:
    index: int
    name: str
    vendor: str  # "nvidia" | "apple" | "amd" | "unknown"
    total_vram_mb: int
    free_vram_mb: Optional[int] = None
    backend: str = ""  # "cuda" | "metal" | "rocm" | ""
    shared_memory: bool = False  # True for unified memory (Apple, some APUs)


@dataclass
class HardwareInfo:
    os_name: str
    arch: str
    cpu_name: str
    physical_cores: int
    logical_cores: int
    total_ram_gb: float
    gpus: List[GPUInfo] = field(default_factory=list)
    llama_gpu_offload_supported: bool = False
    is_apple_silicon: bool = False

    @property
    def has_gpu(self) -> bool:
        return len(self.gpus) > 0

    @property
    def primary_gpu(self) -> Optional[GPUInfo]:
        if not self.gpus:
            return None
        # Prefer discrete NVIDIA, then AMD, then Apple
        order = {"nvidia": 0, "amd": 1, "apple": 2, "unknown": 3}
        return sorted(self.gpus, key=lambda g: (order.get(g.vendor, 9), -g.total_vram_mb))[0]

    @property
    def primary_vram_mb(self) -> int:
        g = self.primary_gpu
        return g.total_vram_mb if g else 0

    @property
    def recommended_backend(self) -> str:
        g = self.primary_gpu
        if not g:
            return "cpu"
        return g.backend or "cpu"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_hardware() -> HardwareInfo:
    is_apple = _is_apple_silicon()
    gpus: List[GPUInfo] = []

    # Order matters: try each vendor independently
    gpus.extend(_detect_nvidia_gpus())
    gpus.extend(_detect_amd_gpus())
    if is_apple:
        gpus.extend(_detect_apple_gpus())

    return HardwareInfo(
        os_name=platform.system(),
        arch=platform.machine(),
        cpu_name=_cpu_name(),
        physical_cores=_physical_cores(),
        logical_cores=_logical_cores(),
        total_ram_gb=_total_ram_gb(),
        gpus=gpus,
        llama_gpu_offload_supported=_llama_supports_gpu_offload(),
        is_apple_silicon=is_apple,
    )


def recommend_gpu_layers(
    hardware: HardwareInfo,
    model_size_mb: Optional[float] = None,
    prefer_full_offload: bool = True,
) -> int:
    """
    Recommend n_gpu_layers for Llama(...).

    0  = CPU only
    -1 = offload as many layers as possible
    """
    if not hardware.has_gpu:
        return 0

    # If the installed llama_cpp build has no GPU support, stay on CPU
    # (except Metal often works when the wheel was built with Metal).
    if not hardware.llama_gpu_offload_supported and hardware.recommended_backend != "metal":
        return 0

    g = hardware.primary_gpu
    if g is None:
        return 0

    # Apple Silicon: unified memory — full offload is almost always best
    if g.vendor == "apple":
        return -1 if prefer_full_offload else 0

    vram = g.total_vram_mb
    usable = max(0, vram - 1500)  # KV cache + overhead margin

    if model_size_mb is not None and model_size_mb > usable + 500:
        # Model larger than VRAM — still try auto offload (partial)
        return -1 if prefer_full_offload else 0

    if vram >= 2000:
        return -1

    return 0


def recommend_context_size(hardware: HardwareInfo, default: int = 8192) -> int:
    """Lower context on low-RAM / low-VRAM machines."""
    ram = hardware.total_ram_gb
    vram = hardware.primary_vram_mb
    g = hardware.primary_gpu

    # Unified memory: treat RAM as the limiting factor
    if g and g.shared_memory:
        if ram < 8:
            return min(default, 2048)
        if ram < 16:
            return min(default, 4096)
        if ram < 24:
            return min(default, 8192)
        return default

    if ram < 8 and vram < 4000:
        return min(default, 2048)
    if ram < 12 or vram < 6000:
        return min(default, 4096)
    return default


def format_hardware_summary(h: HardwareInfo) -> str:
    lines = [
        f"OS: {h.os_name} ({h.arch})",
        f"CPU: {h.cpu_name}",
        f"Cores: {h.physical_cores} physical / {h.logical_cores} logical",
        f"RAM: {h.total_ram_gb:.1f} GB",
        f"Apple Silicon: {h.is_apple_silicon}",
        f"llama.cpp GPU offload supported: {h.llama_gpu_offload_supported}",
        f"Recommended backend: {h.recommended_backend}",
    ]
    if h.gpus:
        for g in h.gpus:
            free = f", free {g.free_vram_mb} MB" if g.free_vram_mb is not None else ""
            shared = " [unified memory]" if g.shared_memory else ""
            lines.append(
                f"GPU {g.index}: {g.name} ({g.vendor}/{g.backend}) — "
                f"{g.total_vram_mb} MB{free}{shared}"
            )
    else:
        lines.append("GPU: none detected")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CPU / RAM
# ---------------------------------------------------------------------------

def _cpu_name() -> str:
    try:
        import cpuinfo
        brand = cpuinfo.get_cpu_info().get("brand_raw")
        if brand:
            return brand
    except Exception:
        pass

    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                timeout=3,
            ).strip()
            if out:
                return out
        except Exception:
            pass

    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass

    return platform.processor() or platform.machine() or "Unknown"


def _physical_cores() -> int:
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return n
    except Exception:
        pass
    return _logical_cores()


def _logical_cores() -> int:
    try:
        import psutil
        n = psutil.cpu_count(logical=True)
        if n:
            return n
    except Exception:
        pass
    return os.cpu_count() or 1


def _total_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=3
            ).strip()
            return int(out) / (1024 ** 3)
        except Exception:
            pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Apple Silicon / Metal
# ---------------------------------------------------------------------------

def _is_apple_silicon() -> bool:
    if platform.system() != "Darwin":
        return False
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return True
    # Rosetta edge case
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "hw.optional.arm64"], text=True, timeout=2
        ).strip()
        return out == "1"
    except Exception:
        return False


def _detect_apple_gpus() -> List[GPUInfo]:
    if not _is_apple_silicon():
        return []

    # Chip name (M1, M2 Pro, M3 Max, …)
    chip = "Apple Silicon"
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            timeout=3,
        ).strip()
        if out:
            chip = out
    except Exception:
        pass

    # Unified memory ≈ system RAM (usable fraction for Metal)
    ram_gb = _total_ram_gb()
    # Rough usable GPU memory: leave headroom for OS + app
    usable_mb = int(max(0, (ram_gb - 2.0) * 1024))

    return [
        GPUInfo(
            index=0,
            name=chip,
            vendor="apple",
            total_vram_mb=usable_mb,
            free_vram_mb=None,
            backend="metal",
            shared_memory=True,
        )
    ]


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------

def _detect_nvidia_gpus() -> List[GPUInfo]:
    gpus = _gpus_via_nvml()
    if gpus:
        return gpus
    return _gpus_via_nvidia_smi()


def _gpus_via_nvml() -> List[GPUInfo]:
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        result = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            result.append(
                GPUInfo(
                    index=i,
                    name=name,
                    vendor="nvidia",
                    total_vram_mb=int(mem.total / (1024 * 1024)),
                    free_vram_mb=int(mem.free / (1024 * 1024)),
                    backend="cuda",
                    shared_memory=False,
                )
            )
        pynvml.nvmlShutdown()
        return result
    except Exception:
        return []


def _gpus_via_nvidia_smi() -> List[GPUInfo]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        result = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            result.append(
                GPUInfo(
                    index=int(parts[0]),
                    name=parts[1],
                    vendor="nvidia",
                    total_vram_mb=int(float(parts[2])),
                    free_vram_mb=int(float(parts[3])),
                    backend="cuda",
                    shared_memory=False,
                )
            )
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# AMD / ROCm
# ---------------------------------------------------------------------------

def _detect_amd_gpus() -> List[GPUInfo]:
    gpus = _gpus_via_rocm_smi()
    if gpus:
        return gpus
    return _gpus_via_rocminfo()


def _gpus_via_rocm_smi() -> List[GPUInfo]:
    if not shutil.which("rocm-smi"):
        return []
    try:
        # Product name
        names_out = subprocess.check_output(
            ["rocm-smi", "--showproductname", "--csv"],
            text=True,
            timeout=8,
            stderr=subprocess.DEVNULL,
        )
        # Memory
        mem_out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            text=True,
            timeout=8,
            stderr=subprocess.DEVNULL,
        )

        names: dict[int, str] = {}
        for line in names_out.strip().splitlines()[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0].isdigit():
                names[int(parts[0])] = parts[-1]

        result = []
        for line in mem_out.strip().splitlines()[1:]:
            parts = [p.strip() for p in line.split(",")]
            # device, Total Memory (B), ...
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            idx = int(parts[0])
            try:
                total_b = int(parts[1])
            except ValueError:
                continue
            result.append(
                GPUInfo(
                    index=idx,
                    name=names.get(idx, f"AMD GPU {idx}"),
                    vendor="amd",
                    total_vram_mb=int(total_b / (1024 * 1024)),
                    free_vram_mb=None,
                    backend="rocm",
                    shared_memory=False,
                )
            )
        return result
    except Exception:
        return []


def _gpus_via_rocminfo() -> List[GPUInfo]:
    if not shutil.which("rocminfo"):
        return []
    try:
        out = subprocess.check_output(
            ["rocminfo"], text=True, timeout=10, stderr=subprocess.DEVNULL
        )
        result = []
        current_name = None
        current_mem_mb = 0
        idx = 0
        for line in out.splitlines():
            line = line.strip()
            if "Marketing Name:" in line:
                current_name = line.split(":", 1)[1].strip()
            if "Size:" in line and "KB" in line and current_name:
                # e.g. Size: 16777216 KB
                try:
                    kb = int(line.split(":")[1].strip().split()[0])
                    current_mem_mb = kb // 1024
                except (ValueError, IndexError):
                    pass
            if current_name and current_mem_mb > 0 and "Device Type" in line:
                # flush previous if we somehow stacked; simple approach:
                pass
            # End of GPU block often marked by next "Agent"
            if line.startswith("*******") and current_name and current_mem_mb > 0:
                result.append(
                    GPUInfo(
                        index=idx,
                        name=current_name,
                        vendor="amd",
                        total_vram_mb=current_mem_mb,
                        backend="rocm",
                        shared_memory=False,
                    )
                )
                idx += 1
                current_name = None
                current_mem_mb = 0

        if current_name and current_mem_mb > 0:
            result.append(
                GPUInfo(
                    index=idx,
                    name=current_name,
                    vendor="amd",
                    total_vram_mb=current_mem_mb,
                    backend="rocm",
                    shared_memory=False,
                )
            )
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# llama.cpp GPU support probe
# ---------------------------------------------------------------------------

def _llama_supports_gpu_offload() -> bool:
    try:
        from llama_cpp.llama_cpp import load_shared_library
        import pathlib
        import llama_cpp

        lib_dir = pathlib.Path(llama_cpp.__file__).resolve().parent / "lib"
        lib = load_shared_library("llama", lib_dir)
        if hasattr(lib, "llama_supports_gpu_offload"):
            return bool(lib.llama_supports_gpu_offload())
    except Exception:
        pass

    try:
        from llama_cpp.llama_cpp import _load_shared_library

        lib = _load_shared_library("llama")
        if hasattr(lib, "llama_supports_gpu_offload"):
            return bool(lib.llama_supports_gpu_offload())
        if hasattr(lib, "ggml_init_cublas"):
            return True
    except Exception:
        pass
    return False

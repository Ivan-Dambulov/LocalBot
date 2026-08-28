# llm/acceleration.py
"""
LocalBot native llama.cpp acceleration manager.

Supported:
    NVIDIA -> CUDA
    AMD    -> HIP/ROCm (Linux) / Vulkan fallback
    Intel  -> SYCL/oneAPI / Vulkan fallback
    Apple  -> Metal
    Other  -> Vulkan when available
    None   -> CPU

Important:
    llama-cpp-python is compiled FROM SOURCE.

The manager:
    1. Detects OS / architecture / GPU.
    2. Detects drivers/toolkits/compilers.
    3. Produces an installation plan.
    4. Can launch required OS-level installers/package managers.
    5. Builds llama-cpp-python in a temporary environment.
    6. Verifies the resulting backend.
    7. Replaces the application's CPU package only after success.
    8. Restores the CPU build if the GPU build fails.

GPU display/kernel drivers are OS-level software. The manager never silently
modifies them. It displays what is required and asks the user before launching
the official installer/package-manager operation.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional


ProgressCallback = Optional[Callable[[str], None]]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GPUInfo:
    vendor: str = "unknown"
    name: str = "Unknown"
    driver: str = ""
    backend: str = ""
    supported: bool = False
    details: str = ""


@dataclass
class Dependency:
    name: str
    component: str
    installed: bool
    required: bool = True
    version: str = ""
    description: str = ""
    install_command: list[str] = field(default_factory=list)
    official_url: str = ""


@dataclass
class AccelerationInfo:
    os_name: str
    os_version: str
    architecture: str
    python: str

    gpu: GPUInfo

    recommended_backend: str

    dependencies: list[Dependency] = field(default_factory=list)

    cmake_available: bool = False
    compiler_available: bool = False
    toolkit_available: bool = False
    driver_available: bool = False

    llama_installed: bool = False
    llama_version: str = ""
    installed_backend: str = "none"

    verified: bool = False
    cpu_fallback: bool = False

    message: str = ""


@dataclass
class BuildResult:
    success: bool
    backend: str
    message: str
    output: str = ""
    verification: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLAMA_PACKAGE = "llama-cpp-python"

OFFICIAL_URLS = {
    "nvidia_driver": "https://www.nvidia.com/Download/index.aspx",
    "cuda": "https://developer.nvidia.com/cuda-downloads",
    "rocm": "https://rocm.docs.amd.com/projects/install-on-linux/en/latest/",
    "amd_driver": "https://www.amd.com/en/support",
    "intel_driver": "https://www.intel.com/content/www/us/en/download-center/home.html",
    "oneapi": "https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html",
    "vulkan": "https://vulkan.lunarg.com/sdk/home",
    "cmake": "https://cmake.org/download/",
    "visualstudio": "https://visualstudio.microsoft.com/downloads/",
    "xcode_cli": "https://developer.apple.com/xcode/resources/",
}


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def _emit(callback: ProgressCallback, text: str) -> None:
    if callback:
        try:
            callback(text)
        except Exception:
            pass


def run_command(
    command: list[str],
    *,
    timeout: int = 120,
    env: Optional[dict] = None,
    cwd: Optional[str | Path] = None,
    callback: ProgressCallback = None,
) -> tuple[int, str]:

    _emit(callback, "$ " + " ".join(command))

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            env=env,
            cwd=str(cwd) if cwd else None,
            bufsize=1,
        )

        lines = []

        assert process.stdout is not None

        for line in process.stdout:
            line = line.rstrip()
            lines.append(line)

            if callback:
                _emit(callback, line)

        rc = process.wait(timeout=timeout)

        return rc, "\n".join(lines)

    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except Exception:
            pass

        return 124, "Command timed out."

    except Exception as exc:
        return 1, str(exc)


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def command_version(command: str, argument: str = "--version") -> str:
    if not command_exists(command):
        return ""

    rc, output = run_command(
        [command, argument],
        timeout=15,
    )

    if rc != 0:
        return ""

    return output.strip().splitlines()[0][:300] if output.strip() else ""


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_apple_silicon() -> bool:
    return is_macos() and platform.machine().lower() in {
        "arm64",
        "aarch64",
    }


def is_admin() -> bool:
    if is_windows():
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    try:
        return os.geteuid() == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def detect_nvidia() -> GPUInfo:
    if not command_exists("nvidia-smi"):
        return GPUInfo()

    rc, output = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version",
            "--format=csv,noheader",
        ],
        timeout=15,
    )

    if rc != 0 or not output.strip():
        return GPUInfo()

    first = output.splitlines()[0]
    parts = [x.strip() for x in first.split(",")]

    name = parts[0] if parts else "NVIDIA GPU"
    driver = parts[1] if len(parts) > 1 else ""

    return GPUInfo(
        vendor="nvidia",
        name=name,
        driver=driver,
        backend="cuda",
        supported=True,
        details=(
            f"NVIDIA GPU detected.\n"
            f"Device: {name}\n"
            f"Driver: {driver or 'unknown'}"
        ),
    )


def detect_amd() -> GPUInfo:
    # Native ROCm/HIP
    if command_exists("rocminfo"):
        rc, output = run_command(
            ["rocminfo"],
            timeout=20,
        )

        if rc == 0:
            name = "AMD GPU"

            for line in output.splitlines():
                if "Marketing Name:" in line:
                    name = line.split(":", 1)[1].strip()
                    break

            return GPUInfo(
                vendor="amd",
                name=name,
                backend="hip",
                supported=True,
                details=(
                    "AMD GPU detected with ROCm/rocminfo.\n"
                    "Preferred backend: HIP."
                ),
            )

    # Windows/Linux Vulkan fallback
    if command_exists("vulkaninfo"):
        rc, output = run_command(
            ["vulkaninfo", "--summary"],
            timeout=20,
        )

        if rc == 0 and "AMD" in output.upper():
            return GPUInfo(
                vendor="amd",
                name="AMD GPU",
                backend="vulkan",
                supported=True,
                details=(
                    "AMD GPU detected through Vulkan.\n"
                    "ROCm/HIP is unavailable; Vulkan is recommended."
                ),
            )

    return GPUInfo()


def detect_intel() -> GPUInfo:
    if command_exists("sycl-ls"):
        rc, output = run_command(
            ["sycl-ls"],
            timeout=20,
        )

        if rc == 0 and "intel" in output.lower():
            return GPUInfo(
                vendor="intel",
                name="Intel GPU",
                backend="sycl",
                supported=True,
                details=(
                    "Intel GPU detected through SYCL.\n"
                    "Preferred backend: Intel oneAPI/SYCL."
                ),
            )

    if command_exists("vulkaninfo"):
        rc, output = run_command(
            ["vulkaninfo", "--summary"],
            timeout=20,
        )

        if rc == 0 and "INTEL" in output.upper():
            return GPUInfo(
                vendor="intel",
                name="Intel GPU",
                backend="vulkan",
                supported=True,
                details=(
                    "Intel GPU detected through Vulkan.\n"
                    "oneAPI/SYCL is unavailable; Vulkan will be used."
                ),
            )

    return GPUInfo()


def detect_vulkan() -> GPUInfo:
    if not command_exists("vulkaninfo"):
        return GPUInfo()

    rc, output = run_command(
        ["vulkaninfo", "--summary"],
        timeout=20,
    )

    if rc != 0:
        return GPUInfo()

    lower = output.lower()

    # Do not consider software Vulkan implementations a usable GPU.
    software = (
        "llvmpipe",
        "lavapipe",
        "softpipe",
        "swiftshader",
    )

    if any(item in lower for item in software):
        return GPUInfo()

    name = "Vulkan GPU"

    for line in output.splitlines():
        if "deviceName" in line:
            name = line.split("=", 1)[-1].strip()
            break

    return GPUInfo(
        vendor="unknown",
        name=name,
        backend="vulkan",
        supported=True,
        details="GPU detected through Vulkan.",
    )


def detect_gpu() -> GPUInfo:
    if is_apple_silicon():
        return GPUInfo(
            vendor="apple",
            name=f"Apple Silicon ({platform.machine()})",
            backend="metal",
            supported=True,
            details="Apple Silicon detected. Metal is the native backend.",
        )

    gpu = detect_nvidia()
    if gpu.supported:
        return gpu

    gpu = detect_amd()
    if gpu.supported:
        return gpu

    gpu = detect_intel()
    if gpu.supported:
        return gpu

    return detect_vulkan()


# ---------------------------------------------------------------------------
# Dependency detection
# ---------------------------------------------------------------------------

def has_cmake() -> bool:
    return command_exists("cmake")


def has_generic_compiler() -> bool:
    if is_windows():
        return (
            command_exists("cl")
            or command_exists("clang")
            or command_exists("gcc")
        )

    return (
        command_exists("clang")
        or command_exists("clang++")
        or command_exists("gcc")
        or command_exists("g++")
    )


def has_cuda() -> bool:
    return command_exists("nvcc") and command_exists("nvidia-smi")


def has_rocm() -> bool:
    return command_exists("rocminfo") and (
        command_exists("hipcc")
        or bool(os.environ.get("ROCM_PATH"))
        or bool(os.environ.get("HIP_PATH"))
    )


def has_sycl() -> bool:
    return (
        command_exists("sycl-ls")
        and command_exists("icx")
        and command_exists("icpx")
    )


def has_metal_toolchain() -> bool:
    return is_macos() and command_exists("xcrun")


def has_vulkan() -> bool:
    return command_exists("vulkaninfo")


def has_ninja() -> bool:
    return command_exists("ninja")


# ---------------------------------------------------------------------------
# Linux dependency commands
# ---------------------------------------------------------------------------

def linux_package_manager() -> Optional[str]:
    for manager in (
        "apt-get",
        "dnf",
        "pacman",
        "zypper",
    ):
        if command_exists(manager):
            return manager

    return None


def linux_build_install_command() -> list[str]:
    manager = linux_package_manager()

    if manager == "apt-get":
        return [
            "sudo",
            "apt-get",
            "update",
        ]

    if manager == "dnf":
        return [
            "sudo",
            "dnf",
            "makecache",
        ]

    if manager == "pacman":
        return [
            "sudo",
            "pacman",
            "-Sy",
        ]

    if manager == "zypper":
        return [
            "sudo",
            "zypper",
            "refresh",
        ]

    return []


def linux_build_packages() -> list[str]:
    manager = linux_package_manager()

    if manager == "apt-get":
        return [
            "build-essential",
            "cmake",
            "ninja-build",
            "git",
            "pkg-config",
            "python3-dev",
        ]

    if manager == "dnf":
        return [
            "gcc-c++",
            "cmake",
            "ninja-build",
            "git",
            "pkgconf-pkg-config",
            "python3-devel",
        ]

    if manager == "pacman":
        return [
            "base-devel",
            "cmake",
            "ninja",
            "git",
        ]

    if manager == "zypper":
        return [
            "gcc-c++",
            "cmake",
            "ninja",
            "git",
            "pkg-config",
        ]

    return []


def get_linux_build_install_commands() -> list[list[str]]:
    manager = linux_package_manager()

    if not manager:
        return []

    packages = linux_build_packages()

    if manager == "apt-get":
        return [
            ["sudo", "apt-get", "update"],
            ["sudo", "apt-get", "install", "-y", *packages],
        ]

    if manager == "dnf":
        return [
            ["sudo", "dnf", "makecache"],
            ["sudo", "dnf", "install", "-y", *packages],
        ]

    if manager == "pacman":
        return [
            ["sudo", "pacman", "-Sy", "--noconfirm"],
            ["sudo", "pacman", "-S", "--needed", "--noconfirm", *packages],
        ]

    if manager == "zypper":
        return [
            ["sudo", "zypper", "refresh"],
            ["sudo", "zypper", "--non-interactive", "install", *packages],
        ]

    return []


# ---------------------------------------------------------------------------
# Windows dependency commands
# ---------------------------------------------------------------------------

def winget_exists() -> bool:
    return command_exists("winget")


def windows_install_build_tools() -> list[list[str]]:
    """
    Visual Studio Build Tools.

    We intentionally use winget rather than downloading an arbitrary EXE
    from a third-party mirror.
    """

    if not winget_exists():
        return []

    return [
        [
            "winget",
            "install",
            "--id",
            "Microsoft.VisualStudio.2022.BuildTools",
            "--exact",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--override",
            "--wait",
            "--passive",
            "--add",
            "Microsoft.VisualStudio.Workload.VCTools",
            "--includeRecommended",
        ]
    ]


def windows_install_cmake() -> list[list[str]]:
    if not winget_exists():
        return []

    return [
        [
            "winget",
            "install",
            "--id",
            "Kitware.CMake",
            "--exact",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    ]


def windows_install_vulkan() -> list[list[str]]:
    if not winget_exists():
        return []

    return [
        [
            "winget",
            "install",
            "--id",
            "LunarG.VulkanSDK",
            "--exact",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    ]


# ---------------------------------------------------------------------------
# macOS dependency commands
# ---------------------------------------------------------------------------

def macos_install_command_line_tools() -> list[list[str]]:
    if not is_macos():
        return []

    if has_metal_toolchain():
        return []

    # xcode-select will open Apple's installer UI.
    return [
        [
            "xcode-select",
            "--install",
        ]
    ]


def macos_install_cmake() -> list[list[str]]:
    if has_cmake():
        return []

    if command_exists("brew"):
        return [
            [
                "brew",
                "install",
                "cmake",
            ]
        ]

    return []


# ---------------------------------------------------------------------------
# Dependency plan
# ---------------------------------------------------------------------------

def dependency_plan(gpu: Optional[GPUInfo] = None) -> list[Dependency]:
    gpu = gpu or detect_gpu()

    deps: list[Dependency] = []

    # Common CMake
    deps.append(
        Dependency(
            name="CMake",
            component="build",
            installed=has_cmake(),
            description="Required to compile llama.cpp.",
            official_url=OFFICIAL_URLS["cmake"],
        )
    )

    # Generic compiler
    deps.append(
        Dependency(
            name="C/C++ Compiler",
            component="compiler",
            installed=has_generic_compiler(),
            description="Required to compile llama-cpp-python.",
            official_url=OFFICIAL_URLS["visualstudio"]
            if is_windows()
            else "",
        )
    )

    if gpu.vendor == "nvidia":
        deps.append(
            Dependency(
                name="NVIDIA Driver",
                component="driver",
                installed=bool(gpu.driver),
                description="Required for CUDA GPU execution.",
                official_url=OFFICIAL_URLS["nvidia_driver"],
            )
        )

        deps.append(
            Dependency(
                name="CUDA Toolkit",
                component="toolkit",
                installed=has_cuda(),
                description="Required to compile the CUDA backend.",
                official_url=OFFICIAL_URLS["cuda"],
            )
        )

    elif gpu.vendor == "amd":
        if gpu.backend == "hip":
            deps.append(
                Dependency(
                    name="AMD ROCm / HIP",
                    component="toolkit",
                    installed=has_rocm(),
                    description="Required for native AMD HIP acceleration.",
                    official_url=OFFICIAL_URLS["rocm"],
                )
            )
        else:
            deps.append(
                Dependency(
                    name="Vulkan Runtime",
                    component="toolkit",
                    installed=has_vulkan(),
                    description="Required for AMD Vulkan acceleration.",
                    official_url=OFFICIAL_URLS["vulkan"],
                )
            )

    elif gpu.vendor == "intel":
        if gpu.backend == "sycl":
            deps.append(
                Dependency(
                    name="Intel oneAPI / SYCL",
                    component="toolkit",
                    installed=has_sycl(),
                    description="Required for Intel SYCL acceleration.",
                    official_url=OFFICIAL_URLS["oneapi"],
                )
            )
        else:
            deps.append(
                Dependency(
                    name="Vulkan Runtime",
                    component="toolkit",
                    installed=has_vulkan(),
                    description="Required for Intel Vulkan acceleration.",
                    official_url=OFFICIAL_URLS["vulkan"],
                )
            )

    elif gpu.backend == "vulkan":
        deps.append(
            Dependency(
                name="Vulkan Runtime",
                component="toolkit",
                installed=has_vulkan(),
                description="Required for Vulkan GPU acceleration.",
                official_url=OFFICIAL_URLS["vulkan"],
            )
        )

    elif gpu.vendor == "apple":
        deps.append(
            Dependency(
                name="Apple Command Line Tools",
                component="compiler",
                installed=has_metal_toolchain(),
                description="Required to compile the Metal backend.",
                official_url=OFFICIAL_URLS["xcode_cli"],
            )
        )

    return deps


# ---------------------------------------------------------------------------
# Human-readable diagnostics
# ---------------------------------------------------------------------------

def collect_info() -> AccelerationInfo:
    gpu = detect_gpu()

    dependencies = dependency_plan(gpu)

    llama_version = installed_llama_version()
    installed_backend = detect_installed_backend()

    driver_available = bool(gpu.driver) or gpu.vendor == "apple"

    toolkit_available = True

    if gpu.backend == "cuda":
        toolkit_available = has_cuda()
    elif gpu.backend == "hip":
        toolkit_available = has_rocm()
    elif gpu.backend == "sycl":
        toolkit_available = has_sycl()
    elif gpu.backend == "vulkan":
        toolkit_available = has_vulkan()
    elif gpu.backend == "metal":
        toolkit_available = has_metal_toolchain()

    compiler = has_generic_compiler()

    return AccelerationInfo(
        os_name=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine(),
        python=sys.version.split()[0],
        gpu=gpu,
        recommended_backend=gpu.backend if gpu.supported else "cpu",
        dependencies=dependencies,
        cmake_available=has_cmake(),
        compiler_available=compiler,
        toolkit_available=toolkit_available,
        driver_available=driver_available,
        llama_installed=bool(llama_version),
        llama_version=llama_version,
        installed_backend=installed_backend,
        verified=False,
        cpu_fallback=not gpu.supported,
    )


def diagnostics_text(info: Optional[AccelerationInfo] = None) -> str:
    info = info or collect_info()

    lines = [
        "LocalBot Acceleration Diagnostics",
        "=" * 40,
        "",
        f"Operating system : {info.os_name}",
        f"OS version      : {info.os_version}",
        f"Architecture    : {info.architecture}",
        f"Python          : {info.python}",
        "",
        "GPU",
        "-" * 40,
        f"Vendor          : {info.gpu.vendor}",
        f"Device          : {info.gpu.name}",
        f"Driver          : {info.gpu.driver or 'not detected'}",
        f"GPU backend     : {info.gpu.backend or 'none'}",
        f"Supported       : {'yes' if info.gpu.supported else 'no'}",
        "",
        "Build environment",
        "-" * 40,
        f"CMake           : {'OK' if info.cmake_available else 'MISSING'}",
        f"Compiler        : {'OK' if info.compiler_available else 'MISSING'}",
        f"Toolkit         : {'OK' if info.toolkit_available else 'MISSING'}",
        "",
        "llama-cpp-python",
        "-" * 40,
        f"Installed       : {'yes' if info.llama_installed else 'no'}",
        f"Version         : {info.llama_version or 'none'}",
        f"Backend         : {info.installed_backend}",
        f"Verified        : {'yes' if info.verified else 'no'}",
        "",
        "Dependencies",
        "-" * 40,
    ]

    for dep in info.dependencies:
        state = "OK" if dep.installed else "MISSING"
        lines.append(
            f"{state:7} {dep.name} [{dep.component}]"
        )

    if info.gpu.details:
        lines.extend(
            [
                "",
                "GPU details",
                "-" * 40,
                info.gpu.details,
            ]
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# llama-cpp-python inspection
# ---------------------------------------------------------------------------

def installed_llama_version() -> str:
    try:
        return importlib.metadata.version(LLAMA_PACKAGE)
    except Exception:
        return ""


def llama_package_location() -> Optional[Path]:
    try:
        package = importlib.import_module("llama_cpp")
        if package.__file__:
            return Path(package.__file__).resolve()
    except Exception:
        pass

    return None


def detect_installed_backend() -> str:
    """
    Heuristic backend inspection.

    llama-cpp-python does not provide one stable public backend-query API
    across all package releases, so inspect its native library names.
    """

    package_file = llama_package_location()

    if not package_file:
        return "none"

    package_dir = package_file.parent

    names: list[str] = []

    try:
        for path in package_dir.rglob("*"):
            if path.is_file():
                names.append(path.name.lower())
    except Exception:
        pass

    text = " ".join(names)

    if "cuda" in text or "cudart" in text:
        return "cuda"

    if "hip" in text or "roc" in text:
        return "hip"

    if "vulkan" in text:
        return "vulkan"

    if "metal" in text:
        return "metal"

    if "sycl" in text:
        return "sycl"

    return "cpu"


def verify_import() -> tuple[bool, str]:
    try:
        importlib.invalidate_caches()

        module = importlib.import_module("llama_cpp")
        version = getattr(module, "__version__", "unknown")

        return True, f"llama_cpp {version}"

    except Exception as exc:
        return False, str(exc)


def verify_backend(backend: str) -> tuple[bool, str]:
    ok, message = verify_import()

    if not ok:
        return False, message

    actual = detect_installed_backend()

    if backend == "cpu":
        return True, f"CPU llama-cpp-python import verified ({actual})."

    if actual != backend:
        return False, (
            f"Python package imported, but expected backend "
            f"{backend!r}; detected {actual!r}."
        )

    if backend == "cuda":
        if not command_exists("nvidia-smi"):
            return False, "CUDA package found but nvidia-smi is unavailable."

    elif backend == "hip":
        if not command_exists("rocminfo"):
            return False, "HIP package found but rocminfo is unavailable."

    elif backend == "sycl":
        if not command_exists("sycl-ls"):
            return False, "SYCL package found but sycl-ls is unavailable."

    elif backend == "vulkan":
        if not command_exists("vulkaninfo"):
            return False, "Vulkan package found but vulkaninfo is unavailable."

    elif backend == "metal":
        if not is_macos():
            return False, "Metal backend is only valid on macOS."

        if not has_metal_toolchain():
            return False, "Metal/Xcode command line tools unavailable."

    return True, f"{backend.upper()} backend verified."


# ---------------------------------------------------------------------------
# Build configuration
# ---------------------------------------------------------------------------

def cmake_args_for_backend(backend: str) -> str:
    common = [
        "-DGGML_NATIVE=ON",
    ]

    if backend == "cuda":
        return " ".join(
            common + [
                "-DGGML_CUDA=ON",
            ]
        )

    if backend == "hip":
        return " ".join(
            common + [
                "-DGGML_HIP=ON",
            ]
        )

    if backend == "vulkan":
        return " ".join(
            common + [
                "-DGGML_VULKAN=ON",
            ]
        )

    if backend == "sycl":
        return " ".join(
            common + [
                "-DGGML_SYCL=ON",
                "-DGGML_SYCL_F16=ON",
                "-DCMAKE_C_COMPILER=icx",
                "-DCMAKE_CXX_COMPILER=icpx",
            ]
        )

    if backend == "metal":
        return " ".join(
            common + [
                "-DGGML_METAL=ON",
            ]
        )

    return " ".join(
        common + [
            "-DGGML_CUDA=OFF",
            "-DGGML_HIP=OFF",
            "-DGGML_VULKAN=OFF",
            "-DGGML_SYCL=OFF",
            "-DGGML_METAL=OFF",
        ]
    )


def build_environment(backend: str) -> dict:
    env = os.environ.copy()

    env["CMAKE_ARGS"] = cmake_args_for_backend(backend)

    # Clear stale backend variables.
    for key in (
        "GGML_CUDA",
        "GGML_HIP",
        "GGML_VULKAN",
        "GGML_SYCL",
        "GGML_METAL",
    ):
        env.pop(key, None)

    if backend == "cuda":
        env["GGML_CUDA"] = "ON"

    elif backend == "hip":
        env["GGML_HIP"] = "ON"

    elif backend == "vulkan":
        env["GGML_VULKAN"] = "ON"

    elif backend == "sycl":
        env["GGML_SYCL"] = "ON"

    elif backend == "metal":
        env["GGML_METAL"] = "ON"

    return env


# ---------------------------------------------------------------------------
# Source build
# ---------------------------------------------------------------------------

def build_from_source(
    backend: str,
    *,
    callback: ProgressCallback = None,
) -> BuildResult:

    if backend not in {
        "cpu",
        "cuda",
        "hip",
        "vulkan",
        "sycl",
        "metal",
    }:
        return BuildResult(
            False,
            backend,
            f"Unsupported backend: {backend}",
        )

    if not has_cmake():
        return BuildResult(
            False,
            backend,
            "CMake is not installed.",
        )

    if not has_generic_compiler() and backend != "sycl":
        return BuildResult(
            False,
            backend,
            "No C/C++ compiler was detected.",
        )

    if backend == "cuda" and not has_cuda():
        return BuildResult(
            False,
            backend,
            "CUDA toolkit/driver is unavailable.",
        )

    if backend == "hip" and not has_rocm():
        return BuildResult(
            False,
            backend,
            "ROCm/HIP toolchain is unavailable.",
        )

    if backend == "sycl" and not has_sycl():
        return BuildResult(
            False,
            backend,
            "Intel oneAPI SYCL compiler/runtime is unavailable.",
        )

    if backend == "vulkan" and not has_vulkan():
        return BuildResult(
            False,
            backend,
            "Vulkan runtime is unavailable.",
        )

    if backend == "metal" and not has_metal_toolchain():
        return BuildResult(
            False,
            backend,
            "Apple command-line tools are unavailable.",
        )

    env = build_environment(backend)

    _emit(
        callback,
        f"Building llama-cpp-python from source using {backend.upper()}...",
    )

    _emit(
        callback,
        f"CMAKE_ARGS={env['CMAKE_ARGS']}",
    )

    # Build in a temporary virtual environment so that the currently
    # working CPU package remains untouched while compilation occurs.
    with tempfile.TemporaryDirectory(
        prefix="localbot-llama-build-"
    ) as temp:

        venv = Path(temp) / "venv"

        rc, output = run_command(
            [
                sys.executable,
                "-m",
                "venv",
                str(venv),
            ],
            timeout=120,
            callback=callback,
        )

        if rc != 0:
            return BuildResult(
                False,
                backend,
                "Could not create temporary build environment.",
                output,
            )

        if is_windows():
            python = venv / "Scripts" / "python.exe"
        else:
            python = venv / "bin" / "python"

        # Upgrade build tools.
        rc, out = run_command(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
                "cmake",
                "ninja",
            ],
            timeout=900,
            callback=callback,
        )

        if rc != 0:
            return BuildResult(
                False,
                backend,
                "Failed to install Python build tools.",
                out,
            )

        # IMPORTANT:
        # --no-binary prevents installation of the normal CPU wheel.
        #
        # The package is compiled locally with CMAKE_ARGS.
        install_cmd = [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-binary",
            "llama-cpp-python",
            "--no-build-isolation",
            "llama-cpp-python",
        ]

        rc, out = run_command(
            install_cmd,
            timeout=3600,
            env=env,
            callback=callback,
        )

        if rc != 0:
            return BuildResult(
                False,
                backend,
                "llama-cpp-python source compilation failed.",
                out,
            )

        # Verify inside the temporary environment.
        verify_script = r"""
import importlib
import sys

try:
    m = importlib.import_module("llama_cpp")
    print("IMPORT_OK")
    print("VERSION:", getattr(m, "__version__", "unknown"))
    print("FILE:", getattr(m, "__file__", "unknown"))
except Exception as e:
    print("IMPORT_FAILED")
    print(type(e).__name__ + ": " + str(e))
    sys.exit(1)
"""

        rc, verify_out = run_command(
            [
                str(python),
                "-c",
                verify_script,
            ],
            timeout=120,
            callback=callback,
        )

        if rc != 0:
            return BuildResult(
                False,
                backend,
                "The compiled llama-cpp-python package could not be imported.",
                out,
                verify_out,
            )

        # Now install the verified source package into the application
        # environment.
        #
        # This is the first point where the existing package is replaced.
        _emit(
            callback,
            "Temporary build verified. Replacing application llama-cpp-python...",
        )

        rc, uninstall_out = run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "uninstall",
                "-y",
                LLAMA_PACKAGE,
            ],
            timeout=300,
            callback=callback,
        )

        if rc != 0:
            return BuildResult(
                False,
                backend,
                "Could not remove the existing llama-cpp-python package.",
                uninstall_out,
            )

        rc, install_out = run_command(
            install_cmd,
            timeout=3600,
            env=env,
            callback=callback,
        )

        combined = (
            out
            + "\n\n"
            + verify_out
            + "\n\n"
            + uninstall_out
            + "\n\n"
            + install_out
        )

        if rc != 0:
            _emit(
                callback,
                "GPU installation failed. Attempting CPU fallback...",
            )

            cpu_result = build_cpu_fallback(callback)

            if cpu_result.success:
                return BuildResult(
                    False,
                    backend,
                    (
                        f"{backend.upper()} build failed. "
                        "CPU fallback was restored."
                    ),
                    combined + "\n\nCPU FALLBACK:\n" + cpu_result.output,
                )

            return BuildResult(
                False,
                backend,
                (
                    f"{backend.upper()} build failed and "
                    "CPU fallback could not be restored."
                ),
                combined,
            )

        # Reload/import verification in the actual application interpreter.
        importlib.invalidate_caches()

        ok, verify_message = verify_backend(backend)

        if not ok:
            _emit(
                callback,
                "Backend verification failed. Restoring CPU backend...",
            )

            cpu_result = build_cpu_fallback(callback)

            if cpu_result.success:
                return BuildResult(
                    False,
                    backend,
                    (
                        f"{backend.upper()} compiled but verification failed. "
                        "CPU fallback restored."
                    ),
                    combined,
                    verify_message,
                )

            return BuildResult(
                False,
                backend,
                "GPU verification failed and CPU fallback failed.",
                combined,
                verify_message,
            )

        return BuildResult(
            True,
            backend,
            f"{backend.upper()} llama-cpp-python successfully installed.",
            combined,
            verify_message,
        )


# ---------------------------------------------------------------------------
# CPU fallback
# ---------------------------------------------------------------------------

def build_cpu_fallback(
    callback: ProgressCallback = None,
) -> BuildResult:

    _emit(
        callback,
        "Building CPU-only llama-cpp-python from source...",
    )

    env = build_environment("cpu")

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        "--no-cache-dir",
        "--no-binary",
        "llama-cpp-python",
        "llama-cpp-python",
    ]

    rc, output = run_command(
        cmd,
        timeout=3600,
        env=env,
        callback=callback,
    )

    if rc != 0:
        return BuildResult(
            False,
            "cpu",
            "CPU fallback build failed.",
            output,
        )

    ok, verify = verify_backend("cpu")

    if not ok:
        return BuildResult(
            False,
            "cpu",
            "CPU fallback was installed but could not be verified.",
            output,
            verify,
        )

    return BuildResult(
        True,
        "cpu",
        "CPU fallback installed successfully.",
        output,
        verify,
    )


# ---------------------------------------------------------------------------
# OS-level dependency installation
# ---------------------------------------------------------------------------

def get_dependency_install_commands(
    info: Optional[AccelerationInfo] = None,
) -> list[list[str]]:

    info = info or collect_info()

    commands: list[list[str]] = []

    # Windows ---------------------------------------------------------------
    if is_windows():

        if not info.cmake_available:
            commands.extend(windows_install_cmake())

        if not info.compiler_available:
            commands.extend(windows_install_build_tools())

        if info.gpu.backend == "vulkan" and not info.toolkit_available:
            commands.extend(windows_install_vulkan())

        return commands

    # macOS -----------------------------------------------------------------
    if is_macos():

        if not info.cmake_available:
            commands.extend(macos_install_cmake())

        if info.gpu.backend == "metal" and not has_metal_toolchain():
            commands.extend(macos_install_command_line_tools())

        return commands

    # Linux -----------------------------------------------------------------
    if is_linux():

        if not info.cmake_available or not info.compiler_available:
            commands.extend(get_linux_build_install_commands())

        return commands

    return commands


def install_missing_build_dependencies(
    callback: ProgressCallback = None,
) -> tuple[bool, str]:

    info = collect_info()

    commands = get_dependency_install_commands(info)

    if not commands:
        return True, "No automatic OS package-manager dependencies are missing."

    for command in commands:
        _emit(
            callback,
            "Installing required build dependency...",
        )

        rc, output = run_command(
            command,
            timeout=1800,
            callback=callback,
        )

        if rc != 0:
            return False, output

    return True, "Build dependencies installed."


# ---------------------------------------------------------------------------
# Official installer launcher
# ---------------------------------------------------------------------------

def open_url(url: str) -> None:
    if is_windows():
        os.startfile(url)  # type: ignore[attr-defined]
        return

    if is_macos():
        subprocess.Popen(["open", url])
        return

    if is_linux():
        subprocess.Popen(["xdg-open", url])
        return


def required_manual_installers(
    info: Optional[AccelerationInfo] = None,
) -> list[Dependency]:

    info = info or collect_info()

    missing = [
        dep
        for dep in info.dependencies
        if not dep.installed
    ]

    return missing


def install_or_open_missing_requirements(
    callback: ProgressCallback = None,
) -> tuple[bool, str, list[Dependency]]:

    """
    Attempts safe package-manager installation first.

    If something cannot be installed automatically, it returns the missing
    dependencies to the UI. The UI can then show official URLs and ask the
    user to install them.

    This is especially important for GPU display/kernel drivers and vendor
    toolkits whose exact version must match the installed GPU/OS.
    """

    info = collect_info()

    commands = get_dependency_install_commands(info)

    for command in commands:
        _emit(
            callback,
            "Installing: " + " ".join(command),
        )

        rc, output = run_command(
            command,
            timeout=1800,
            callback=callback,
        )

        if rc != 0:
            return False, output, required_manual_installers()

    # Re-detect after installation.
    info = collect_info()

    missing = required_manual_installers(info)

    if missing:
        return False, "Some vendor dependencies still need installation.", missing

    return True, "All detected dependencies are installed.", []


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def choose_backend() -> str:
    info = collect_info()

    if not info.gpu.supported:
        return "cpu"

    return info.gpu.backend or "cpu"


def setup_acceleration(
    *,
    backend: Optional[str] = None,
    callback: ProgressCallback = None,
) -> BuildResult:

    info = collect_info()

    backend = backend or choose_backend()

    _emit(
        callback,
        f"Selected backend: {backend.upper()}",
    )

    if backend == "cpu":
        return build_cpu_fallback(callback)

    # First make sure compiler/CMake/toolchain dependencies are present.
    deps_ok, dep_message, missing = install_or_open_missing_requirements(
        callback
    )

    if not deps_ok:
        details = "\n".join(
            f"- {dep.name}: {dep.official_url}"
            for dep in missing
        )

        return BuildResult(
            False,
            backend,
            (
                dep_message
                + (
                    "\n\nMissing vendor dependencies:\n"
                    + details
                    if details
                    else ""
                )
            ),
        )

    # Refresh environment after installer operations.
    info = collect_info()

    # Backend-specific checks.
    if backend == "cuda" and not has_cuda():
        return BuildResult(
            False,
            backend,
            (
                "CUDA is still unavailable after dependency setup. "
                "Install the NVIDIA driver and CUDA Toolkit, then retry."
            ),
        )

    if backend == "hip" and not has_rocm():
        return BuildResult(
            False,
            backend,
            (
                "ROCm/HIP is unavailable. "
                "Install ROCm and retry."
            ),
        )

    if backend == "sycl" and not has_sycl():
        return BuildResult(
            False,
            backend,
            (
                "Intel oneAPI/SYCL is unavailable. "
                "Install Intel oneAPI Base Toolkit and retry."
            ),
        )

    if backend == "vulkan" and not has_vulkan():
        return BuildResult(
            False,
            backend,
            (
                "Vulkan is unavailable. "
                "Install the Vulkan runtime/SDK and retry."
            ),
        )

    if backend == "metal" and not has_metal_toolchain():
        return BuildResult(
            False,
            backend,
            (
                "Apple command-line tools are unavailable. "
                "Install Xcode Command Line Tools and retry."
            ),
        )

    return build_from_source(
        backend,
        callback=callback,
    )


# ---------------------------------------------------------------------------
# Public convenience functions
# ---------------------------------------------------------------------------

def acceleration_summary() -> str:
    info = collect_info()

    if info.gpu.supported:
        return (
            f"{info.gpu.name} · "
            f"{info.recommended_backend.upper()}"
        )

    return "CPU-only"


def backend_is_verified(backend: str) -> bool:
    ok, _ = verify_backend(backend)
    return ok


def save_diagnostics(path: str | Path) -> None:
    info = collect_info()

    payload = asdict(info)

    Path(path).write_text(
        __import__("json").dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )
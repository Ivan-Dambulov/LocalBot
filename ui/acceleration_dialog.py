import platform
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox


def detect_acceleration_support():
    """Return list of missing optional backends that the hardware supports."""
    missing = []
    system = platform.system()
    machine = platform.machine().lower()

    # NVIDIA
    has_nvidia = False
    try:
        import pynvml
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() > 0:
            has_nvidia = True
        pynvml.nvmlShutdown()
    except Exception:
        try:
            if subprocess.run(["nvidia-smi"], capture_output=True, timeout=3).returncode == 0:
                has_nvidia = True
        except Exception:
            pass

    if has_nvidia:
        try:
            from llama_cpp import llama_supports_gpu_offload
            if not llama_supports_gpu_offload():
                missing.append("cuda")
        except Exception:
            missing.append("cuda")

    # Apple Silicon → MLX
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        try:
            import mlx.core  # noqa: F401
        except ImportError:
            missing.append("mlx")

    return missing


class AccelerationDialog(tk.Toplevel):
    def __init__(self, parent, backends: list[str]):
        super().__init__(parent)
        self.title("Optional Acceleration")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._cancel_flag = False

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Faster inference is available on your hardware.",
            font=("", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        descriptions = {
            "cuda": "NVIDIA CUDA support (recommended for your GPU)",
            "mlx": "Apple MLX / Metal acceleration (Apple Silicon)",
        }
        for b in backends:
            ttk.Label(frame, text=f"• {descriptions.get(b, b)}").pack(anchor="w")

        ttk.Label(
            frame,
            text=(
                "\nThis will download extra packages (can be several hundred MB).\n"
                "You can skip and stay on CPU."
            ),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(12, 16))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.status = ttk.Label(frame, text="")

        ttk.Button(
            btn_frame, text="Download & Install", command=self._start
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            btn_frame, text="Cancel / Use CPU", command=self._cancel
        ).pack(side="left")

        self.backends = backends
        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")

    def _cancel(self):
        self._cancel_flag = True
        self.result = None
        self.destroy()

    def _start(self):
        self.progress.pack(fill="x", pady=(12, 4))
        self.status.pack(anchor="w")
        self.progress.start(12)
        self.status.config(text="Installing… this may take a few minutes")

        def worker():
            try:
                if "cuda" in self.backends and not self._cancel_flag:
                    # Change cu124 to the CUDA version you want to support
                    cmd = [
                        sys.executable, "-m", "pip", "install",
                        "--upgrade", "--force-reinstall",
                        "llama-cpp-python",
                        "--extra-index-url",
                        "https://abetlen.github.io/llama-cpp-python/whl/cu124",
                    ]
                    subprocess.check_call(cmd)
                    self.result = "cuda"

                if "mlx" in self.backends and not self._cancel_flag:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "--upgrade", "mlx", "mlx-lm"]
                    )
                    self.result = "mlx"
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Install failed", str(e)))
                self.result = None
            finally:
                self.after(0, self._done)

        import sys
        threading.Thread(target=worker, daemon=True).start()

    def _done(self):
        self.progress.stop()
        self.destroy()


def offer_acceleration_if_needed(root) -> str | None:
    missing = detect_acceleration_support()
    if not missing:
        return None
    dlg = AccelerationDialog(root, missing)
    root.wait_window(dlg)
    return dlg.result
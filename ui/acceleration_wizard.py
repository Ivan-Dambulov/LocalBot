# ui/acceleration_wizard.py
"""
Guided, novice-friendly wizard for enabling GPU acceleration.
Designed to feel simple and calm (Apple-like experience).
"""

from __future__ import annotations

import threading
import customtkinter as ctk
from tkinter import messagebox

from llm.acceleration import (
    collect_info,
    setup_acceleration,
    required_manual_installers,
    open_url,
    has_cuda,
    has_generic_compiler,
    has_cmake,
    OFFICIAL_URLS,
)


class AccelerationWizard(ctk.CTkToplevel):
    def __init__(self, parent, on_finished=None):
        super().__init__(parent)
        self.title("Enable GPU Acceleration")
        self.geometry("640x520")
        self.minsize(580, 480)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color="#FFFFFF")

        self.on_finished = on_finished
        self.backend = "cuda"
        self._cancelled = False
        self._build_result = None

        # Center over parent
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 640) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 520) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self._build_ui()
        self.after(100, self._start_flow)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#F5F5F7", height=70, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Enable GPU Acceleration",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#1C1C1E",
        ).pack(side="left", padx=24, pady=20)

        # Main content area
        self.content = ctk.CTkFrame(self, fg_color="#FFFFFF")
        self.content.pack(fill="both", expand=True, padx=28, pady=20)

        # Progress indicator (simple step dots)
        self.step_label = ctk.CTkLabel(
            self.content,
            text="Step 1 of 4",
            font=ctk.CTkFont(size=12),
            text_color="#8E8E93",
        )
        self.step_label.pack(anchor="w")

        self.title_label = ctk.CTkLabel(
            self.content,
            text="Checking your computer…",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1C1C1E",
            wraplength=560,
            justify="left",
        )
        self.title_label.pack(anchor="w", pady=(8, 12))

        self.body_label = ctk.CTkLabel(
            self.content,
            text="",
            font=ctk.CTkFont(size=14),
            text_color="#3A3A3C",
            wraplength=560,
            justify="left",
        )
        self.body_label.pack(anchor="w")

        # Status / log (friendly)
        self.status_frame = ctk.CTkFrame(self.content, fg_color="#F9F9FB", corner_radius=12)
        self.status_frame.pack(fill="x", pady=(20, 0))

        self.status_text = ctk.CTkLabel(
            self.status_frame,
            text="Preparing…",
            font=ctk.CTkFont(size=13),
            text_color="#8E8E93",
            wraplength=520,
            justify="left",
        )
        self.status_text.pack(anchor="w", padx=16, pady=14)

        self.progress = ctk.CTkProgressBar(self.content, height=6, corner_radius=3)
        self.progress.pack(fill="x", pady=(16, 0))
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")

        # Buttons
        self.btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_row.pack(fill="x", padx=28, pady=(10, 24))

        self.secondary_btn = ctk.CTkButton(
            self.btn_row,
            text="Use CPU Only",
            width=130,
            height=36,
            corner_radius=10,
            fg_color="#F2F2F7",
            text_color="#1C1C1E",
            hover_color="#E5E5EA",
            command=self._use_cpu,
        )
        self.secondary_btn.pack(side="left")

        self.primary_btn = ctk.CTkButton(
            self.btn_row,
            text="Continue",
            width=160,
            height=36,
            corner_radius=10,
            fg_color="#007AFF",
            hover_color="#0062CC",
            command=self._on_primary,
        )
        self.primary_btn.pack(side="right")

        self.primary_btn.configure(state="disabled")

    # ------------------------------------------------------------------ Flow
    def _start_flow(self):
        self._set_step(1, "Checking your computer…",
                       "LocalBot is looking at your graphics card and what is already installed.")
        self.progress.start()
        self.status_text.configure(text="Detecting GPU and tools…")

        def worker():
            info = collect_info()
            self.after(0, lambda: self._after_detect(info))

        threading.Thread(target=worker, daemon=True).start()

    def _after_detect(self, info):
        self.progress.stop()
        self.progress.set(0.15)

        if not info.gpu.supported:
            self._show_cpu_only_message()
            return

        self.backend = info.recommended_backend or "cuda"
        gpu_name = info.gpu.name or "your GPU"

        missing = required_manual_installers(info)
        auto_ok = has_cmake() and has_generic_compiler()

        if self.backend == "cuda" and not has_cuda():
            # Most common path for Windows users
            self._show_cuda_needed(gpu_name, missing)
        elif missing:
            self._show_missing_tools(gpu_name, missing)
        else:
            self._show_ready_to_build(gpu_name)

    def _show_cuda_needed(self, gpu_name, missing):
        self._set_step(2, "One download is needed",
                       f"Your {gpu_name} can run models much faster with GPU acceleration.\n\n"
                       "NVIDIA’s free CUDA Toolkit is required (one-time install, about 3 GB).\n"
                       "After you install it, come back here and click “I’ve finished”.")

        self.status_text.configure(
            text="Missing: CUDA Toolkit  •  (CMake and C++ tools will be handled automatically)"
        )
        self.progress.set(0.25)

        self.primary_btn.configure(text="Download CUDA Toolkit", state="normal")
        self.secondary_btn.configure(text="Use CPU Only")

        self._primary_action = "download_cuda"

    def _show_missing_tools(self, gpu_name, missing):
        names = ", ".join(d.name for d in missing)
        self._set_step(2, "A few tools are needed",
                       f"Your {gpu_name} is ready for acceleration.\n\n"
                       f"LocalBot will try to install the free build tools automatically.\n"
                       f"Still missing: {names}")

        self.status_text.configure(text="Preparing automatic installation…")
        self.progress.set(0.3)

        self.primary_btn.configure(text="Install & Continue", state="normal")
        self._primary_action = "install_tools"

    def _show_ready_to_build(self, gpu_name):
        self._set_step(3, "Ready to build",
                       f"Everything looks good for your {gpu_name}.\n\n"
                       "LocalBot will now compile the accelerated engine. "
                       "This usually takes 3–10 minutes and happens only once.")

        self.status_text.configure(text="All required tools detected.")
        self.progress.set(0.4)

        self.primary_btn.configure(text="Build GPU Engine", state="normal")
        self._primary_action = "build"

    def _show_cpu_only_message(self):
        self._set_step(1, "CPU mode",
                       "No compatible GPU acceleration was found.\n\n"
                       "LocalBot will use the CPU. You can still run models normally.")
        self.progress.set(1.0)
        self.primary_btn.configure(text="OK", state="normal")
        self.secondary_btn.configure(state="disabled")
        self._primary_action = "close"

    # ------------------------------------------------------------------ Button actions
    def _on_primary(self):
        action = getattr(self, "_primary_action", None)

        if action == "download_cuda":
            open_url(OFFICIAL_URLS["cuda"])
            self.primary_btn.configure(text="I’ve finished installing CUDA")
            self._primary_action = "cuda_done"
            self.status_text.configure(
                text="After the NVIDIA installer finishes, click the button above."
            )

        elif action == "cuda_done":
            self.status_text.configure(text="Checking if CUDA is now available…")
            self.primary_btn.configure(state="disabled")
            self.after(300, self._recheck_after_cuda)

        elif action == "install_tools":
            self._run_auto_install_then_build()

        elif action == "build":
            self._start_build()

        elif action == "close":
            self.destroy()

        elif action == "restart_hint":
            self.destroy()
            if self.on_finished:
                self.on_finished(self._build_result)

    def _recheck_after_cuda(self):
        info = collect_info()
        if has_cuda():
            self.status_text.configure(text="CUDA detected! Ready to build.")
            self._show_ready_to_build(info.gpu.name or "your GPU")
        else:
            self.status_text.configure(
                text="CUDA still not found. Make sure you finished the installer and restarted if asked."
            )
            self.primary_btn.configure(
                text="Download CUDA again", state="normal"
            )
            self._primary_action = "download_cuda"
            messagebox.showinfo(
                "CUDA not detected yet",
                "CUDA Toolkit was not found.\n\n"
                "• Make sure the installer completed successfully\n"
                "• Restart your computer if the installer asked you to\n"
                "• Then click the button again",
                parent=self,
            )

    def _run_auto_install_then_build(self):
        self.primary_btn.configure(state="disabled", text="Working…")
        self.secondary_btn.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_text.configure(text="Installing free build tools (CMake + C++ compiler)…")

        def worker():
            from llm.acceleration import install_or_open_missing_requirements

            def progress(msg):
                self.after(0, lambda m=msg: self.status_text.configure(text=m[:120]))

            ok, message, missing = install_or_open_missing_requirements(callback=progress)

            def done():
                self.progress.stop()
                if ok and not missing:
                    self._start_build()
                else:
                    # Still something missing (usually CUDA)
                    info = collect_info()
                    self._show_cuda_needed(info.gpu.name or "your GPU", missing or [])
                    self.primary_btn.configure(state="normal")
                    self.secondary_btn.configure(state="normal")

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _start_build(self):
        self._set_step(4, "Building GPU engine…",
                       "This can take several minutes. You can leave this window open.")
        self.primary_btn.configure(state="disabled", text="Building…")
        self.secondary_btn.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_text.configure(text="Compiling llama-cpp-python with CUDA…")

        def worker():
            def progress(msg):
                # Keep the UI calm – show only short friendly lines
                short = msg
                if len(msg) > 100:
                    short = msg[:97] + "…"
                self.after(0, lambda m=short: self.status_text.configure(text=m))

            result = setup_acceleration(backend=self.backend, callback=progress)
            self.after(0, lambda: self._build_finished(result))

        threading.Thread(target=worker, daemon=True).start()

    def _build_finished(self, result):
        self.progress.stop()
        self._build_result = result

        if result.success:
            self._set_step(4, "Success!",
                           "GPU acceleration is ready.\n\n"
                           "Please restart LocalBot so the new engine is loaded.")
            self.status_text.configure(text=result.message)
            self.progress.set(1.0)
            self.primary_btn.configure(text="Done – Restart LocalBot", state="normal")
            self.secondary_btn.configure(state="disabled")
            self._primary_action = "restart_hint"
        else:
            self._set_step(4, "Something went wrong",
                           "The GPU build could not be completed.\n\n"
                           "You can still use LocalBot in CPU mode.")
            self.status_text.configure(text=result.message[:200])
            self.primary_btn.configure(text="Close", state="normal")
            self.secondary_btn.configure(text="Use CPU Only", state="normal")
            self._primary_action = "close"

            messagebox.showerror(
                "GPU build failed",
                f"{result.message}\n\n"
                "You can continue with CPU mode. "
                "The detailed log was shown during the build.",
                parent=self,
            )

    def _use_cpu(self):
        if messagebox.askyesno(
            "Use CPU only?",
            "Models will run on the CPU (slower but works immediately).\n\n"
            "You can enable GPU acceleration later from the Model Manager.",
            parent=self,
        ):
            self.destroy()
            if self.on_finished:
                self.on_finished(None)  # signal CPU choice

    def _set_step(self, number: int, title: str, body: str):
        self.step_label.configure(text=f"Step {number} of 4")
        self.title_label.configure(text=title)
        self.body_label.configure(text=body)
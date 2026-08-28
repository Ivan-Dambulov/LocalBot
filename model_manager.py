# ui/model_manager.py
"""
Modern Model Manager matching LocalBot Figma design.
- Hardware summary (CPU / RAM / GPU) top-right
- Optional llama-cpp-python GPU / Metal install
- Compatible 4-bit GGUF models with download buttons
"""

from pathlib import Path
import platform
import subprocess
import sys
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog

from llm.hardware import detect_hardware, format_hardware_summary
from llm.model_catalog import (
    CATALOG,
    best_quant_for_hardware,
    score_quant_for_hardware,
)
from ui.settings import load_preferences, save_preferences


class ModelManager(ctk.CTkToplevel):
    def __init__(self, parent, current_model_path: str, models_dir: str, on_apply=None):
        super().__init__(parent)
        self.title("Model Manager")
        self.geometry("980x720")
        self.minsize(860, 600)
        self.configure(fg_color="#FFFFFF")
        self.transient(parent)
        self.grab_set()

        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.current_model_path = current_model_path or ""
        self.on_apply = on_apply
        self.selected_path = None
        self._download_cancel = False

        self.hw = detect_hardware()
        self.vram_mb = self.hw.primary_vram_mb
        self.ram_gb = self.hw.total_ram_gb
        self.shared = bool(self.hw.primary_gpu and self.hw.primary_gpu.shared_memory)

        self._build_ui()
        self._populate_models()
        self._refresh_installed()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # ========== TOP BAR ==========
        top = ctk.CTkFrame(self, height=72, corner_radius=0, fg_color="#F5F5F7")
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top, text="Model Manager",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#1C1C1E",
        ).pack(side="left", padx=20, pady=18)

        # Hardware summary – top right
        hw_frame = ctk.CTkFrame(top, fg_color="transparent")
        hw_frame.pack(side="right", padx=16, pady=10)

        cpu_short = (self.hw.cpu_name or "CPU")[:28]
        ram_txt = f"{self.ram_gb:.0f} GB RAM"

        gpu_txt = "No GPU"
        if self.hw.primary_gpu:
            g = self.hw.primary_gpu
            if g.vendor == "apple":
                gpu_txt = f"Metal · {g.name[:20]}"
            else:
                vram = f"{g.total_vram_mb / 1024:.1f} GB" if g.total_vram_mb else ""
                gpu_txt = f"{g.name[:18]} · {vram}".strip(" ·")

        for label, value in [
            ("CPU", cpu_short),
            ("RAM", ram_txt),
            ("GPU", gpu_txt),
        ]:
            box = ctk.CTkFrame(hw_frame, fg_color="#FFFFFF", corner_radius=8,
                               border_width=1, border_color="#E5E5EA")
            box.pack(side="left", padx=4)
            ctk.CTkLabel(box, text=label, font=ctk.CTkFont(size=10),
                         text_color="#8E8E93").pack(padx=10, pady=(4, 0))
            ctk.CTkLabel(box, text=value, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#1C1C1E").pack(padx=10, pady=(0, 6))

        # ========== ACCELERATION SECTION ==========
        accel = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=0)
        accel.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            accel, text="Acceleration",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1C1C1E",
        ).pack(anchor="w")

        self.accel_status = ctk.CTkLabel(
            accel, text=self._accel_status_text(),
            font=ctk.CTkFont(size=12), text_color="#8E8E93",
            wraplength=700, justify="left",
        )
        self.accel_status.pack(anchor="w", pady=(2, 6))

        accel_btn_row = ctk.CTkFrame(accel, fg_color="transparent")
        accel_btn_row.pack(anchor="w", pady=(0, 4))

        backend = self.hw.recommended_backend
        if backend == "cuda":
            ctk.CTkButton(
                accel_btn_row, text="Install CUDA llama-cpp-python",
                width=220, height=32, corner_radius=10,
                fg_color="#007AFF", hover_color="#0062CC",
                command=lambda: self._install_accel("cuda"),
            ).pack(side="left", padx=(0, 8))
        elif backend == "metal" or self.hw.is_apple_silicon:
            ctk.CTkButton(
                accel_btn_row, text="Install Metal llama-cpp-python",
                width=220, height=32, corner_radius=10,
                fg_color="#007AFF", hover_color="#0062CC",
                command=lambda: self._install_accel("metal"),
            ).pack(side="left", padx=(0, 8))
        else:
            ctk.CTkLabel(
                accel_btn_row, text="CPU-only mode (no GPU acceleration available)",
                font=ctk.CTkFont(size=12), text_color="#8E8E93",
            ).pack(side="left")

        self.accel_progress = ctk.CTkProgressBar(accel, height=6, corner_radius=3)
        self.accel_progress.set(0)
        # shown only while installing

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#E5E5EA").pack(fill="x", padx=16, pady=8)

        # ========== TABS: Recommended / Installed ==========
        self.tabview = ctk.CTkTabview(
            self, fg_color="#FFFFFF",
            segmented_button_fg_color="#F2F2F7",
            segmented_button_selected_color="#007AFF",
            segmented_button_selected_hover_color="#0062CC",
            text_color="#1C1C1E",
            segmented_button_unselected_color="#F2F2F7",
            segmented_button_unselected_hover_color="#E5E5EA",
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self.tab_rec = self.tabview.add("Recommended")
        self.tab_inst = self.tabview.add("Installed")

        # ---- Recommended tab ----
        ctk.CTkLabel(
            self.tab_rec,
            text="4-bit GGUF models that fit your hardware  ·  Qwen · NVIDIA · Mistral · DeepSeek · Llama …",
            font=ctk.CTkFont(size=12), text_color="#8E8E93",
        ).pack(anchor="w", padx=4, pady=(4, 8))

        self.model_list = ctk.CTkScrollableFrame(
            self.tab_rec, fg_color="transparent", corner_radius=0
        )
        self.model_list.pack(fill="both", expand=True)

        # ---- Installed tab ----
        inst_top = ctk.CTkFrame(self.tab_inst, fg_color="transparent")
        inst_top.pack(fill="x", pady=(4, 8))

        ctk.CTkButton(
            inst_top, text="Refresh", width=80, height=28, corner_radius=8,
            fg_color="#F2F2F7", text_color="#1C1C1E", hover_color="#E5E5EA",
            command=self._refresh_installed,
        ).pack(side="left")
        ctk.CTkButton(
            inst_top, text="Browse…", width=80, height=28, corner_radius=8,
            fg_color="#F2F2F7", text_color="#1C1C1E", hover_color="#E5E5EA",
            command=self._browse,
        ).pack(side="left", padx=6)

        self.installed_list = ctk.CTkScrollableFrame(
            self.tab_inst, fg_color="transparent"
        )
        self.installed_list.pack(fill="both", expand=True)

        # Status bar
        self.status = ctk.CTkLabel(
            self, text="Ready", font=ctk.CTkFont(size=12),
            text_color="#8E8E93", anchor="w",
        )
        self.status.pack(fill="x", padx=16, pady=(0, 10))

    def _accel_status_text(self) -> str:
        if self.hw.llama_gpu_offload_supported:
            return f"GPU offload is available (backend: {self.hw.recommended_backend})."
        if self.hw.recommended_backend == "cuda":
            return "NVIDIA GPU detected. Install the CUDA build of llama-cpp-python for acceleration."
        if self.hw.is_apple_silicon or self.hw.recommended_backend == "metal":
            return "Apple Silicon detected. Install the Metal build of llama-cpp-python for acceleration."
        return "No GPU acceleration detected. Models will run on CPU."

    # ------------------------------------------------------------------ Acceleration install
    def _install_accel(self, kind: str):
        self.accel_progress.pack(fill="x", pady=(4, 0))
        self.accel_progress.configure(mode="indeterminate")
        self.accel_progress.start()
        self.accel_status.configure(text=f"Installing {kind} build… this can take several minutes.")

        def worker():
            try:
                if kind == "cuda":
                    # cu124 is a common current wheel; adjust if needed
                    cmd = [
                        sys.executable, "-m", "pip", "install",
                        "--upgrade", "--force-reinstall",
                        "llama-cpp-python",
                        "--extra-index-url",
                        "https://abetlen.github.io/llama-cpp-python/whl/cu121",
                    ]
                else:  # metal / mac
                    cmd = [
                        sys.executable, "-m", "pip", "install",
                        "--upgrade", "--force-reinstall",
                        "llama-cpp-python",
                        "--extra-index-url",
                        "https://abetlen.github.io/llama-cpp-python/whl/metal",
                    ]
                subprocess.check_call(cmd)
                self.after(0, lambda: self._accel_done(True, kind))
            except Exception as e:
                self.after(0, lambda: self._accel_done(False, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _accel_done(self, ok: bool, info: str):
        self.accel_progress.stop()
        self.accel_progress.pack_forget()
        if ok:
            self.accel_status.configure(
                text=f"Installed {info} build successfully. Restart the app for full effect."
            )
            messagebox.showinfo("Installed", f"{info} build installed.\nPlease restart LocalBot.")
        else:
            self.accel_status.configure(text=f"Install failed: {info}")
            messagebox.showerror("Install failed", info)

    # ------------------------------------------------------------------ Recommended models
    def _populate_models(self):
        for w in self.model_list.winfo_children():
            w.destroy()

        # Prefer 4-bit (Q4) quants that fit
        shown = 0
        for model in sorted(CATALOG, key=lambda m: (m.priority, m.params_b)):
            quant = best_quant_for_hardware(
                model, self.vram_mb, self.ram_gb, self.shared
            )
            if quant is None:
                continue

            # Prefer Q4 / lower-bit when available
            q4 = next((q for q in model.quants if "Q4" in q.label.upper()), None)
            if q4:
                comp = score_quant_for_hardware(
                    q4.size_gb, self.vram_mb, self.ram_gb, self.shared
                )
                if comp.score >= 50:
                    quant = q4

            comp = score_quant_for_hardware(
                quant.size_gb, self.vram_mb, self.ram_gb, self.shared
            )
            if comp.score < 40:
                continue

            self._add_model_row(model, quant, comp)
            shown += 1

        if shown == 0:
            ctk.CTkLabel(
                self.model_list,
                text="No compatible models found for this hardware.",
                text_color="#8E8E93",
            ).pack(pady=20)

    def _add_model_row(self, model, quant, comp):
        row = ctk.CTkFrame(
            self.model_list, height=72, corner_radius=12,
            fg_color="#F9F9FB", border_width=1, border_color="#E5E5EA",
        )
        row.pack(fill="x", pady=4, padx=2)
        row.pack_propagate(False)

        # Left text
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=14, pady=8)

        title_line = f"{model.name}  ·  {quant.label}  ·  {quant.size_gb:.1f} GB"
        ctk.CTkLabel(
            left, text=title_line,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#1C1C1E", anchor="w",
        ).pack(anchor="w")

        # Blurb + tags
        tags = ", ".join(model.tags) if model.tags else ""
        blurb = model.blurb or "General purpose"
        if tags:
            blurb = f"{blurb}  ·  {tags}"
        ctk.CTkLabel(
            left, text=blurb,
            font=ctk.CTkFont(size=12), text_color="#8E8E93", anchor="w",
        ).pack(anchor="w")

        # Compatibility badge
        badge_color = {
            "excellent": "#34C759",
            "good": "#30D158",
            "possible": "#FF9F0A",
            "slow": "#FF9500",
            "incompatible": "#FF3B30",
        }.get(comp.level, "#8E8E93")

        badge = ctk.CTkLabel(
            row, text=comp.label, width=90, height=24,
            corner_radius=8, fg_color=badge_color, text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        badge.pack(side="right", padx=(0, 10))

        # Download button
        dl_btn = ctk.CTkButton(
            row, text="Download", width=90, height=32,
            corner_radius=10, fg_color="#007AFF", hover_color="#0062CC",
            command=lambda m=model, q=quant: self._start_download(m, q),
        )
        dl_btn.pack(side="right", padx=6)

    def _start_download(self, model, quant):
        self.status.configure(text=f"Downloading {quant.filename} …")
        self._download_cancel = False

        def worker():
            try:
                from llm.hf_models import download_gguf

                def progress_cb(name, downloaded, total):
                    if total and total > 0:
                        pct = min(100, int(downloaded * 100 / total))
                        self.after(0, lambda: self.status.configure(
                            text=f"Downloading {name}  ·  {pct}%"
                        ))

                local_path = download_gguf(
                    repo_id=model.repo_id,
                    filename=quant.filename,
                    dest_dir=self.models_dir,
                    progress=progress_cb,
                )
                self.after(0, lambda: self._download_finished(local_path))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Download failed", str(e)))
                self.after(0, lambda: self.status.configure(text="Download failed"))

        threading.Thread(target=worker, daemon=True).start()

    def _download_finished(self, local_path: str):
        self.status.configure(text=f"Downloaded: {Path(local_path).name}")
        self.selected_path = local_path
        self._refresh_installed()
        if messagebox.askyesno(
            "Download complete",
            f"Saved to:\n{local_path}\n\nUse this model now?",
        ):
            self._apply()

    # ------------------------------------------------------------------ Installed
    def _refresh_installed(self):
        for w in self.installed_list.winfo_children():
            w.destroy()

        files = sorted(self.models_dir.glob("*.gguf"))
        if not files:
            ctk.CTkLabel(
                self.installed_list, text="No .gguf files found in models folder.",
                text_color="#8E8E93",
            ).pack(pady=20)
            return

        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            is_current = str(f) == self.current_model_path

            row = ctk.CTkFrame(
                self.installed_list, height=52, corner_radius=10,
                fg_color="#E8F0FE" if is_current else "#F9F9FB",
            )
            row.pack(fill="x", pady=3, padx=2)
            row.pack_propagate(False)

            ctk.CTkLabel(
                row, text=f"{f.name}  ({size_mb:.0f} MB)",
                font=ctk.CTkFont(size=13), text_color="#1C1C1E", anchor="w",
            ).pack(side="left", padx=14)

            if is_current:
                ctk.CTkLabel(
                    row, text="In use", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#007AFF",
                ).pack(side="right", padx=12)
            else:
                ctk.CTkButton(
                    row, text="Use", width=70, height=28, corner_radius=8,
                    fg_color="#007AFF", hover_color="#0062CC",
                    command=lambda p=str(f): self._select_and_apply(p),
                ).pack(side="right", padx=10)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select GGUF model",
            initialdir=str(self.models_dir),
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")],
        )
        if path:
            self._select_and_apply(path)

    def _select_and_apply(self, path: str):
        self.selected_path = path
        self._apply()

    def _apply(self):
        if not self.selected_path or not Path(self.selected_path).is_file():
            messagebox.showwarning("No model", "Please select or download a model first.")
            return

        prefs = load_preferences()
        prefs["model_path"] = self.selected_path
        save_preferences(prefs)

        if self.on_apply:
            self.on_apply(self.selected_path)

        self.destroy()
# ui/model_manager.py

from pathlib import Path
import threading

import customtkinter as ctk
from tkinter import messagebox, filedialog

from llm.hardware import detect_hardware
from llm.model_catalog import (
    CATALOG,
    best_quant_for_hardware,
    score_quant_for_hardware,
)
from ui.settings  import load_preferences, save_preferences

# Native acceleration manager
from llm.acceleration import (
    collect_info,
    diagnostics_text,
    acceleration_summary,
    setup_acceleration,
    choose_backend,
    required_manual_installers,
    open_url,
    backend_is_verified,
)


class ModelManager(ctk.CTkToplevel):

    def __init__(
        self,
        parent,
        current_model_path: str,
        models_dir: str,
        on_apply=None,
    ):
        super().__init__(parent)

        self.title("Model Manager")
        self.geometry("1040x780")
        self.minsize(900, 650)

        self.configure(
            fg_color="#FFFFFF"
        )

        self.transient(parent)
        self.grab_set()

        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.current_model_path = (
            current_model_path or ""
        )

        self.on_apply = on_apply

        self.selected_path = None

        self.hw = detect_hardware()

        self.vram_mb = self.hw.primary_vram_mb
        self.ram_gb = self.hw.total_ram_gb

        self.shared = bool(
            self.hw.primary_gpu
            and self.hw.primary_gpu.shared_memory
        )

        self.accel_info = collect_info()

        self._build_ui()

        self._populate_models()

        self._refresh_installed()

        self._refresh_acceleration_ui()

    # ==================================================================
    # UI
    # ==================================================================

    def _build_ui(self):

        # --------------------------------------------------------------
        # Top bar
        # --------------------------------------------------------------

        top = ctk.CTkFrame(
            self,
            height=72,
            corner_radius=0,
            fg_color="#F5F5F7",
        )

        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top,
            text="Model Manager",
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color="#1C1C1E",
        ).pack(
            side="left",
            padx=20,
            pady=18,
        )

        hw_frame = ctk.CTkFrame(
            top,
            fg_color="transparent",
        )

        hw_frame.pack(
            side="right",
            padx=16,
            pady=10,
        )

        cpu_short = (
            self.hw.cpu_name or "CPU"
        )[:28]

        ram_txt = (
            f"{self.ram_gb:.0f} GB RAM"
        )

        gpu_txt = "No GPU"

        if self.hw.primary_gpu:

            g = self.hw.primary_gpu

            if g.vendor == "apple":
                gpu_txt = (
                    f"Metal · {g.name[:20]}"
                )

            else:

                vram = (
                    f"{g.total_vram_mb / 1024:.1f} GB"
                    if g.total_vram_mb
                    else ""
                )

                gpu_txt = (
                    f"{g.name[:18]} · {vram}"
                ).strip(" ·")

        for label, value in [
            ("CPU", cpu_short),
            ("RAM", ram_txt),
            ("GPU", gpu_txt),
        ]:

            box = ctk.CTkFrame(
                hw_frame,
                fg_color="#FFFFFF",
                corner_radius=8,
                border_width=1,
                border_color="#E5E5EA",
            )

            box.pack(
                side="left",
                padx=4,
            )

            ctk.CTkLabel(
                box,
                text=label,
                font=ctk.CTkFont(size=10),
                text_color="#8E8E93",
            ).pack(
                padx=10,
                pady=(4, 0),
            )

            ctk.CTkLabel(
                box,
                text=value,
                font=ctk.CTkFont(
                    size=12,
                    weight="bold",
                ),
                text_color="#1C1C1E",
            ).pack(
                padx=10,
                pady=(0, 6),
            )

        # --------------------------------------------------------------
        # Acceleration section
        # --------------------------------------------------------------

        accel = ctk.CTkFrame(
            self,
            fg_color="#FFFFFF",
            corner_radius=0,
        )

        accel.pack(
            fill="x",
            padx=16,
            pady=(12, 4),
        )

        accel_title_row = ctk.CTkFrame(
            accel,
            fg_color="transparent",
        )

        accel_title_row.pack(
            fill="x"
        )

        ctk.CTkLabel(
            accel_title_row,
            text="Acceleration",
            font=ctk.CTkFont(
                size=14,
                weight="bold",
            ),
            text_color="#1C1C1E",
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            accel_title_row,
            text="Details",
            width=80,
            height=28,
            corner_radius=8,
            fg_color="#F2F2F7",
            text_color="#1C1C1E",
            hover_color="#E5E5EA",
            command=self._show_acceleration_details,
        ).pack(
            side="right"
        )

        self.accel_status = ctk.CTkLabel(
            accel,
            text="Detecting acceleration...",
            font=ctk.CTkFont(size=12),
            text_color="#8E8E93",
            wraplength=850,
            justify="left",
        )

        self.accel_status.pack(
            anchor="w",
            pady=(3, 6),
        )

        self.accel_dependency_status = ctk.CTkLabel(
            accel,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#8E8E93",
            justify="left",
        )

        self.accel_dependency_status.pack(
            anchor="w",
            pady=(0, 6),
        )

        accel_btn_row = ctk.CTkFrame(
            accel,
            fg_color="transparent",
        )

        accel_btn_row.pack(
            anchor="w",
            pady=(0, 4),
        )

        self.accel_install_btn = ctk.CTkButton(
            accel_btn_row,
            text="Install & Build GPU Acceleration",
            width=260,
            height=34,
            corner_radius=10,
            fg_color="#007AFF",
            hover_color="#0062CC",
            command=self._start_acceleration_setup,
        )

        self.accel_install_btn.pack(
            side="left",
            padx=(0, 8),
        )

        self.accel_cpu_btn = ctk.CTkButton(
            accel_btn_row,
            text="Use CPU Only",
            width=110,
            height=34,
            corner_radius=10,
            fg_color="#F2F2F7",
            text_color="#1C1C1E",
            hover_color="#E5E5EA",
            command=self._use_cpu_only,
        )

        self.accel_cpu_btn.pack(
            side="left"
        )

        self.accel_progress = ctk.CTkProgressBar(
            accel,
            height=6,
            corner_radius=3,
        )

        self.accel_progress.set(0)

        # --------------------------------------------------------------
        # Separator
        # --------------------------------------------------------------

        ctk.CTkFrame(
            self,
            height=1,
            fg_color="#E5E5EA",
        ).pack(
            fill="x",
            padx=16,
            pady=8,
        )

        # --------------------------------------------------------------
        # Tabs
        # --------------------------------------------------------------

        self.tabview = ctk.CTkTabview(
            self,
            fg_color="#FFFFFF",
            segmented_button_fg_color="#F2F2F7",
            segmented_button_selected_color="#007AFF",
            segmented_button_selected_hover_color="#0062CC",
            text_color="#1C1C1E",
            segmented_button_unselected_color="#F2F2F7",
            segmented_button_unselected_hover_color="#E5E5EA",
        )

        self.tabview.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=(0, 12),
        )

        self.tab_rec = self.tabview.add(
            "Recommended"
        )

        self.tab_inst = self.tabview.add(
            "Installed"
        )

        # --------------------------------------------------------------
        # Recommended
        # --------------------------------------------------------------

        ctk.CTkLabel(
            self.tab_rec,
            text=(
                "4-bit GGUF models that fit your hardware"
                "  ·  Qwen · NVIDIA · Mistral · "
                "DeepSeek · Llama …"
            ),
            font=ctk.CTkFont(size=12),
            text_color="#8E8E93",
        ).pack(
            anchor="w",
            padx=4,
            pady=(4, 8),
        )

        self.model_list = ctk.CTkScrollableFrame(
            self.tab_rec,
            fg_color="transparent",
            corner_radius=0,
        )

        self.model_list.pack(
            fill="both",
            expand=True,
        )

        # --------------------------------------------------------------
        # Installed
        # --------------------------------------------------------------

        inst_top = ctk.CTkFrame(
            self.tab_inst,
            fg_color="transparent",
        )

        inst_top.pack(
            fill="x",
            pady=(4, 8),
        )

        ctk.CTkButton(
            inst_top,
            text="Refresh",
            width=80,
            height=28,
            corner_radius=8,
            fg_color="#F2F2F7",
            text_color="#1C1C1E",
            hover_color="#E5E5EA",
            command=self._refresh_installed,
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            inst_top,
            text="Browse…",
            width=80,
            height=28,
            corner_radius=8,
            fg_color="#F2F2F7",
            text_color="#1C1C1E",
            hover_color="#E5E5EA",
            command=self._browse,
        ).pack(
            side="left",
            padx=6,
        )

        self.installed_list = ctk.CTkScrollableFrame(
            self.tab_inst,
            fg_color="transparent",
        )

        self.installed_list.pack(
            fill="both",
            expand=True,
        )

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        self.status = ctk.CTkLabel(
            self,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="#8E8E93",
            anchor="w",
        )

        self.status.pack(
            fill="x",
            padx=16,
            pady=(0, 10),
        )

    # ==================================================================
    # Acceleration UI
    # ==================================================================

    def _refresh_acceleration_ui(self):

        self.accel_info = collect_info()

        info = self.accel_info

        if not info.gpu.supported:

            self.accel_status.configure(
                text=(
                    "No compatible GPU acceleration was detected. "
                    "LocalBot will use CPU llama-cpp-python."
                ),
                text_color="#8E8E93",
            )

            self.accel_install_btn.configure(
                text="No GPU Acceleration Available",
                state="disabled",
            )

            self.accel_dependency_status.configure(
                text="CPU-only mode",
            )

            return

        backend = info.recommended_backend.upper()

        gpu_name = info.gpu.name

        verified = (
            backend_is_verified(
                info.recommended_backend
            )
            if info.installed_backend
            else False
        )

        if verified:

            self.accel_status.configure(
                text=(
                    f"✓ {gpu_name}\n"
                    f"Backend: {backend}\n"
                    f"Native llama-cpp-python acceleration "
                    f"is installed and verified."
                ),
                text_color="#248A3D",
            )

            self.accel_install_btn.configure(
                text=f"Rebuild {backend} Backend",
                state="normal",
            )

        else:

            self.accel_status.configure(
                text=(
                    f"{gpu_name}\n"
                    f"Recommended backend: {backend}\n"
                    f"GPU acceleration is not currently verified."
                ),
                text_color="#1C1C1E",
            )

            self.accel_install_btn.configure(
                text=f"Install & Build {backend}",
                state="normal",
            )

        missing = [
            dep
            for dep in info.dependencies
            if not dep.installed
        ]

        if missing:

            names = ", ".join(
                dep.name
                for dep in missing
            )

            self.accel_dependency_status.configure(
                text=f"Missing: {names}",
                text_color="#FF9500",
            )

        else:

            self.accel_dependency_status.configure(
                text=(
                    "Build requirements detected."
                ),
                text_color="#248A3D",
            )

    def _show_acceleration_details(self):

        self.accel_info = collect_info()

        dialog = ctk.CTkToplevel(
            self
        )

        dialog.title(
            "Acceleration Details"
        )

        dialog.geometry(
            "820x650"
        )

        dialog.minsize(
            700,
            500
        )

        dialog.transient(
            self
        )

        dialog.grab_set()

        title = ctk.CTkLabel(
            dialog,
            text="Acceleration Details",
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color="#1C1C1E",
        )

        title.pack(
            anchor="w",
            padx=20,
            pady=(18, 8),
        )

        textbox = ctk.CTkTextbox(
            dialog,
            wrap="word",
            font=("Consolas", 12),
        )

        textbox.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 12),
        )

        textbox.insert(
            "1.0",
            diagnostics_text(
                self.accel_info
            )
        )

        textbox.configure(
            state="disabled"
        )

        button_row = ctk.CTkFrame(
            dialog,
            fg_color="transparent",
        )

        button_row.pack(
            fill="x",
            padx=20,
            pady=(0, 18),
        )

        ctk.CTkButton(
            button_row,
            text="Refresh",
            width=90,
            command=lambda: self._refresh_details(
                textbox
            ),
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            button_row,
            text="Close",
            width=90,
            command=dialog.destroy,
        ).pack(
            side="right"
        )

    def _refresh_details(self, textbox):

        info = collect_info()

        textbox.configure(
            state="normal"
        )

        textbox.delete(
            "1.0",
            "end"
        )

        textbox.insert(
            "1.0",
            diagnostics_text(info)
        )

        textbox.configure(
            state="disabled"
        )

    # ==================================================================
    # Acceleration installation
    # ==================================================================

    def _start_acceleration_setup(self):

        info = collect_info()

        if not info.gpu.supported:

            messagebox.showinfo(
                "CPU Mode",
                (
                    "No compatible GPU was detected.\n\n"
                    "LocalBot will use CPU-only llama-cpp-python."
                ),
                parent=self,
            )

            return

        backend = info.recommended_backend

        missing = required_manual_installers(
            info
        )

        if missing:

            text = (
                f"LocalBot detected:\n\n"
                f"GPU: {info.gpu.name}\n"
                f"Backend: {backend.upper()}\n\n"
                "The following components are missing:\n\n"
            )

            text += "\n".join(
                f"• {dep.name}"
                for dep in missing
            )

            text += (
                "\n\nLocalBot will attempt to install "
                "build dependencies automatically.\n\n"
                "Vendor GPU drivers/toolkits may open "
                "their official installer and may require "
                "administrator permission or a restart."
            )

            if not messagebox.askyesno(
                "GPU acceleration setup",
                text,
                parent=self,
            ):
                return

        else:

            if not messagebox.askyesno(
                "Build GPU acceleration",
                (
                    f"GPU: {info.gpu.name}\n"
                    f"Backend: {backend.upper()}\n\n"
                    "LocalBot will compile "
                    "llama-cpp-python from source and "
                    "replace the current CPU build "
                    "only after the accelerated build "
                    "passes verification.\n\n"
                    "This can take several minutes."
                ),
                parent=self,
            ):
                return

        self._set_acceleration_busy(
            True
        )

        def worker():

            def progress(message):

                self.after(
                    0,
                    lambda m=message:
                    self._append_build_log(m),
                )

            result = setup_acceleration(
                backend=backend,
                callback=progress,
            )

            self.after(
                0,
                lambda r=result:
                self._acceleration_finished(r),
            )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _set_acceleration_busy(
        self,
        busy: bool,
    ):

        if busy:

            self.accel_install_btn.configure(
                state="disabled",
                text="Building…",
            )

            self.accel_cpu_btn.configure(
                state="disabled"
            )

            self.accel_progress.pack(
                fill="x",
                pady=(5, 0),
            )

            self.accel_progress.configure(
                mode="indeterminate"
            )

            self.accel_progress.start()

            self.status.configure(
                text=(
                    "Preparing native GPU build..."
                )
            )

            self._show_build_log()

        else:

            try:
                self.accel_progress.stop()
            except Exception:
                pass

            self.accel_progress.pack_forget()

            self.accel_install_btn.configure(
                state="normal"
            )

            self.accel_cpu_btn.configure(
                state="normal"
            )

    # ==================================================================
    # Build log
    # ==================================================================

    def _show_build_log(self):

        if hasattr(
            self,
            "_build_log_window",
        ):

            try:
                if self._build_log_window.winfo_exists():
                    return
            except Exception:
                pass

        self._build_log_window = ctk.CTkToplevel(
            self
        )

        self._build_log_window.title(
            "llama-cpp-python Build"
        )

        self._build_log_window.geometry(
            "900x600"
        )

        self._build_log_window.transient(
            self
        )

        ctk.CTkLabel(
            self._build_log_window,
            text="Native llama-cpp-python build",
            font=ctk.CTkFont(
                size=16,
                weight="bold",
            ),
        ).pack(
            anchor="w",
            padx=16,
            pady=(14, 6),
        )

        self._build_log = ctk.CTkTextbox(
            self._build_log_window,
            wrap="none",
            font=("Consolas", 10),
        )

        self._build_log.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=(0, 16),
        )

    def _append_build_log(
        self,
        message: str,
    ):

        if not hasattr(
            self,
            "_build_log",
        ):
            self._show_build_log()

        try:

            self._build_log.insert(
                "end",
                message + "\n",
            )

            self._build_log.see(
                "end"
            )

        except Exception:
            pass

        self.status.configure(
            text=message[:200]
        )

    def _acceleration_finished(
        self,
        result,
    ):

        self._set_acceleration_busy(
            False
        )

        if result.success:

            self.status.configure(
                text=result.message
            )

            self.accel_info = collect_info()

            self._refresh_acceleration_ui()

            messagebox.showinfo(
                "GPU acceleration installed",
                (
                    f"{result.message}\n\n"
                    f"{result.verification}\n\n"
                    "Restart LocalBot before loading "
                    "a model so the new native library "
                    "is loaded by the application."
                ),
                parent=self,
            )

        else:

            self.status.configure(
                text="GPU build failed; fallback status checked."
            )

            self.accel_info = collect_info()

            self._refresh_acceleration_ui()

            messagebox.showerror(
                "GPU acceleration failed",
                (
                    f"{result.message}\n\n"
                    "The build log contains the complete "
                    "compiler output.\n\n"
                    "LocalBot attempted CPU fallback "
                    "when possible."
                ),
                parent=self,
            )

    def _use_cpu_only(self):

        if not messagebox.askyesno(
            "CPU-only mode",
            (
                "Build and use the CPU-only "
                "llama-cpp-python backend?\n\n"
                "This disables GPU acceleration."
            ),
            parent=self,
        ):
            return

        self._set_acceleration_busy(
            True
        )

        def worker():

            from llm.acceleration import (
                build_cpu_fallback,
            )

            def progress(message):

                self.after(
                    0,
                    lambda m=message:
                    self._append_build_log(m),
                )

            result = build_cpu_fallback(
                callback=progress
            )

            self.after(
                0,
                lambda r=result:
                self._cpu_finished(r),
            )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _cpu_finished(
        self,
        result,
    ):

        self._set_acceleration_busy(
            False
        )

        self.accel_info = collect_info()

        self._refresh_acceleration_ui()

        if result.success:

            messagebox.showinfo(
                "CPU mode",
                (
                    "CPU-only llama-cpp-python "
                    "was installed and verified."
                ),
                parent=self,
            )

        else:

            messagebox.showerror(
                "CPU installation failed",
                result.message,
                parent=self,
            )

    # ==================================================================
    # Models
    # ==================================================================

    def _populate_models(self):

        for widget in self.model_list.winfo_children():
            widget.destroy()

        shown = 0

        for model in sorted(
            CATALOG,
            key=lambda m: (
                m.priority,
                m.params_b,
            ),
        ):

            quant = best_quant_for_hardware(
                model,
                self.vram_mb,
                self.ram_gb,
                self.shared,
            )

            if quant is None:
                continue

            q4 = next(
                (
                    q
                    for q in model.quants
                    if "Q4" in q.label.upper()
                ),
                None,
            )

            if q4:

                comp = score_quant_for_hardware(
                    q4.size_gb,
                    self.vram_mb,
                    self.ram_gb,
                    self.shared,
                )

                if comp.score >= 50:
                    quant = q4

            comp = score_quant_for_hardware(
                quant.size_gb,
                self.vram_mb,
                self.ram_gb,
                self.shared,
            )

            if comp.score < 40:
                continue

            self._add_model_row(
                model,
                quant,
                comp,
            )

            shown += 1

        if shown == 0:

            ctk.CTkLabel(
                self.model_list,
                text=(
                    "No compatible models found "
                    "for this hardware."
                ),
                text_color="#8E8E93",
            ).pack(
                pady=20
            )

    def _add_model_row(
        self,
        model,
        quant,
        comp,
    ):

        row = ctk.CTkFrame(
            self.model_list,
            height=72,
            corner_radius=12,
            fg_color="#F9F9FB",
            border_width=1,
            border_color="#E5E5EA",
        )

        row.pack(
            fill="x",
            pady=4,
            padx=2,
        )

        row.pack_propagate(False)

        left = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=14,
            pady=8,
        )

        title_line = (
            f"{model.name}  ·  "
            f"{quant.label}  ·  "
            f"{quant.size_gb:.1f} GB"
        )

        ctk.CTkLabel(
            left,
            text=title_line,
            font=ctk.CTkFont(
                size=13,
                weight="bold",
            ),
            text_color="#1C1C1E",
            anchor="w",
        ).pack(
            anchor="w"
        )

        tags = (
            ", ".join(model.tags)
            if model.tags
            else ""
        )

        blurb = (
            model.blurb
            or "General purpose"
        )

        if tags:
            blurb = (
                f"{blurb}  ·  {tags}"
            )

        ctk.CTkLabel(
            left,
            text=blurb,
            font=ctk.CTkFont(size=12),
            text_color="#8E8E93",
            anchor="w",
        ).pack(
            anchor="w"
        )

        badge_color = {
            "excellent": "#34C759",
            "good": "#30D158",
            "possible": "#FF9F0A",
            "slow": "#FF9500",
            "incompatible": "#FF3B30",
        }.get(
            comp.level,
            "#8E8E93",
        )

        ctk.CTkLabel(
            row,
            text=comp.label,
            width=90,
            height=24,
            corner_radius=8,
            fg_color=badge_color,
            text_color="white",
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
        ).pack(
            side="right",
            padx=(0, 10),
        )

        ctk.CTkButton(
            row,
            text="Download",
            width=90,
            height=32,
            corner_radius=10,
            fg_color="#007AFF",
            hover_color="#0062CC",
            command=lambda m=model, q=quant:
            self._start_download(
                m,
                q,
            ),
        ).pack(
            side="right",
            padx=6,
        )

    # ==================================================================
    # Downloads
    # ==================================================================

    def _start_download(
        self,
        model,
        quant,
    ):

        self.status.configure(
            text=f"Downloading {quant.filename} …"
        )

        def worker():

            try:

                from llm.hf_models import (
                    download_gguf
                )

                def progress_cb(
                    name,
                    downloaded,
                    total,
                ):

                    if total and total > 0:

                        pct = min(
                            100,
                            int(
                                downloaded
                                * 100
                                / total
                            ),
                        )

                        self.after(
                            0,
                            lambda:
                            self.status.configure(
                                text=(
                                    f"Downloading {name} "
                                    f"· {pct}%"
                                )
                            ),
                        )

                local_path = download_gguf(
                    repo_id=model.repo_id,
                    filename=quant.filename,
                    dest_dir=self.models_dir,
                    progress=progress_cb,
                )

                self.after(
                    0,
                    lambda p=local_path:
                    self._download_finished(p),
                )

            except Exception as exc:

                self.after(
                    0,
                    lambda e=exc:
                    messagebox.showerror(
                        "Download failed",
                        str(e),
                        parent=self,
                    ),
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _download_finished(
        self,
        local_path,
    ):

        self.status.configure(
            text=(
                f"Downloaded: "
                f"{Path(local_path).name}"
            )
        )

        self.selected_path = local_path

        self._refresh_installed()

        if messagebox.askyesno(
            "Download complete",
            (
                f"Saved to:\n{local_path}\n\n"
                "Use this model now?"
            ),
            parent=self,
        ):
            self._apply()

    # ==================================================================
    # Installed models
    # ==================================================================

    def _refresh_installed(self):

        for widget in self.installed_list.winfo_children():
            widget.destroy()

        files = sorted(
            self.models_dir.glob("*.gguf")
        )

        if not files:

            ctk.CTkLabel(
                self.installed_list,
                text=(
                    "No .gguf files found "
                    "in models folder."
                ),
                text_color="#8E8E93",
            ).pack(
                pady=20
            )

            return

        for file_path in files:

            size_mb = (
                file_path.stat().st_size
                / (
                    1024 * 1024
                )
            )

            is_current = (
                str(file_path)
                == self.current_model_path
            )

            row = ctk.CTkFrame(
                self.installed_list,
                height=52,
                corner_radius=10,
                fg_color=(
                    "#E8F0FE"
                    if is_current
                    else "#F9F9FB"
                ),
            )

            row.pack(
                fill="x",
                pady=3,
                padx=2,
            )

            row.pack_propagate(False)

            ctk.CTkLabel(
                row,
                text=(
                    f"{file_path.name} "
                    f"({size_mb:.0f} MB)"
                ),
                font=ctk.CTkFont(size=13),
                text_color="#1C1C1E",
                anchor="w",
            ).pack(
                side="left",
                padx=14,
            )

            if is_current:

                ctk.CTkLabel(
                    row,
                    text="In use",
                    font=ctk.CTkFont(
                        size=11,
                        weight="bold",
                    ),
                    text_color="#007AFF",
                ).pack(
                    side="right",
                    padx=12,
                )

            else:

                ctk.CTkButton(
                    row,
                    text="Use",
                    width=70,
                    height=28,
                    corner_radius=8,
                    fg_color="#007AFF",
                    hover_color="#0062CC",
                    command=lambda p=str(file_path):
                    self._select_and_apply(p),
                ).pack(
                    side="right",
                    padx=10,
                )

    def _browse(self):

        path = filedialog.askopenfilename(
            title="Select GGUF model",
            initialdir=str(
                self.models_dir
            ),
            filetypes=[
                (
                    "GGUF models",
                    "*.gguf",
                ),
                (
                    "All files",
                    "*.*",
                ),
            ],
        )

        if path:
            self._select_and_apply(
                path
            )

    def _select_and_apply(
        self,
        path,
    ):

        self.selected_path = path

        self._apply()

    def _apply(self):

        if (
            not self.selected_path
            or not Path(
                self.selected_path
            ).is_file()
        ):

            messagebox.showwarning(
                "No model",
                (
                    "Please select or "
                    "download a model first."
                ),
                parent=self,
            )

            return

        prefs = load_preferences()

        prefs["model_path"] = (
            self.selected_path
        )

        save_preferences(
            prefs
        )

        if self.on_apply:
            self.on_apply(
                self.selected_path
            )

        self.destroy()
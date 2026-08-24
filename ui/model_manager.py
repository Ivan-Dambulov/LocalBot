# ui/model_manager.py
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from llm.hardware import detect_hardware, format_hardware_summary
from llm.model_catalog import (
    CATALOG,
    best_quant_for_hardware,
    score_quant_for_hardware,
    models_for_family,
    families,
)
from ui.settings import load_preferences, save_preferences


class ModelManager(tk.Toplevel):
    def __init__(self, parent, current_model_path: str, models_dir: str, on_apply=None):
        super().__init__(parent)
        self.title("Model Manager")
        self.geometry("900x620")
        self.minsize(720, 480)
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
        self._refresh_installed()
        self._populate_catalog()
        self._show_hardware()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # ========== Tab 1: Installed ==========
        tab_installed = ttk.Frame(notebook, padding=8)
        notebook.add(tab_installed, text="Installed")

        ttk.Label(tab_installed, text="Local GGUF models", font=("", 10, "bold")).pack(anchor="w")

        self.installed_list = tk.Listbox(tab_installed, height=14, font=("Consolas", 10))
        self.installed_list.pack(fill="both", expand=True, pady=(4, 8))
        self.installed_list.bind("<<ListboxSelect>>", self._on_select_installed)

        btn_frame = ttk.Frame(tab_installed)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_installed).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Browse…", command=self._browse).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Use / Apply", command=self._apply).pack(side="right")

        # ========== Tab 2: Recommended ==========
        tab_catalog = ttk.Frame(notebook, padding=8)
        notebook.add(tab_catalog, text="Recommended")

        top_row = ttk.Frame(tab_catalog)
        top_row.pack(fill="x", pady=(0, 6))
        ttk.Label(top_row, text="Family:").pack(side="left")
        self.family_var = tk.StringVar(value="All")
        family_cb = ttk.Combobox(
            top_row,
            textvariable=self.family_var,
            values=["All"] + families(),
            state="readonly",
            width=14,
        )
        family_cb.pack(side="left", padx=6)
        family_cb.bind("<<ComboboxSelected>>", lambda e: self._populate_catalog())

        # Treeview for catalog
        columns = ("name", "params", "quant", "size", "compat")
        self.catalog_tree = ttk.Treeview(
            tab_catalog,
            columns=columns,
            show="headings",
            height=16,
            selectmode="browse",
        )
        self.catalog_tree.heading("name", text="Model")
        self.catalog_tree.heading("params", text="Params")
        self.catalog_tree.heading("quant", text="Best Quant")
        self.catalog_tree.heading("size", text="Size")
        self.catalog_tree.heading("compat", text="Compatibility")

        self.catalog_tree.column("name", width=220)
        self.catalog_tree.column("params", width=70, anchor="center")
        self.catalog_tree.column("quant", width=90, anchor="center")
        self.catalog_tree.column("size", width=70, anchor="center")
        self.catalog_tree.column("compat", width=120, anchor="center")

        self.catalog_tree.pack(fill="both", expand=True)
        self.catalog_tree.bind("<<TreeviewSelect>>", self._on_select_catalog)

        # Download controls
        dl_frame = ttk.Frame(tab_catalog)
        dl_frame.pack(fill="x", pady=(8, 0))

        self.dl_status = ttk.Label(dl_frame, text="Select a recommended model")
        self.dl_status.pack(side="left")

        ttk.Button(dl_frame, text="Download", command=self._start_download).pack(side="right", padx=(6, 0))
        ttk.Button(dl_frame, text="Use / Apply", command=self._apply).pack(side="right")

        self.progress = ttk.Progressbar(tab_catalog, mode="determinate")
        self.progress.pack(fill="x", pady=(6, 0))

        # ========== Tab 3: Hardware ==========
        tab_hw = ttk.Frame(notebook, padding=8)
        notebook.add(tab_hw, text="Hardware")

        self.hw_text = tk.Text(tab_hw, height=22, wrap="word", font=("Consolas", 9))
        self.hw_text.pack(fill="both", expand=True)

        # Status bar
        self.status = ttk.Label(self, text="Ready", relief="sunken", anchor="w")
        self.status.pack(fill="x", side="bottom", padx=4, pady=4)

    # ------------------------------------------------------------------ Hardware
    def _show_hardware(self):
        self.hw_text.delete("1.0", "end")
        self.hw_text.insert("1.0", format_hardware_summary(self.hw))

    # ------------------------------------------------------------------ Installed
    def _refresh_installed(self):
        self.installed_list.delete(0, "end")
        self._paths = []

        files = sorted(self.models_dir.glob("*.gguf"))
        if not files:
            self.installed_list.insert("end", "(no .gguf files found)")
            return

        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            display = f"{f.name}   ({size_mb:.0f} MB)"
            self.installed_list.insert("end", display)
            self._paths.append(str(f))

            if str(f) == self.current_model_path:
                idx = len(self._paths) - 1
                self.installed_list.selection_set(idx)
                self.installed_list.see(idx)
                self.selected_path = str(f)

    def _on_select_installed(self, _event=None):
        sel = self.installed_list.curselection()
        if sel and hasattr(self, "_paths") and self._paths:
            idx = sel[0]
            if idx < len(self._paths):
                self.selected_path = self._paths[idx]
                self.status.config(text=f"Selected: {Path(self.selected_path).name}")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select GGUF model",
            initialdir=str(self.models_dir),
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")],
        )
        if path:
            self.selected_path = path
            self.status.config(text=f"Selected: {Path(path).name}")

    # ------------------------------------------------------------------ Catalog (Recommended)
    def _populate_catalog(self):
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)

        family = self.family_var.get()
        models = models_for_family(family)

        self._catalog_rows = []  # store (model, quant)

        for model in models:
            quant = best_quant_for_hardware(model, self.vram_mb, self.ram_gb, self.shared)
            if quant is None:
                continue

            compat = score_quant_for_hardware(quant.size_gb, self.vram_mb, self.ram_gb, self.shared)

            iid = self.catalog_tree.insert(
                "",
                "end",
                values=(
                    model.name,
                    f"{model.params_b}B",
                    quant.label,
                    f"{quant.size_gb:.1f} GB",
                    compat.label,
                ),
            )
            self._catalog_rows.append((model, quant))

    def _on_select_catalog(self, _event=None):
        sel = self.catalog_tree.selection()
        if not sel:
            return
        idx = self.catalog_tree.index(sel[0])
        if idx < len(self._catalog_rows):
            model, quant = self._catalog_rows[idx]
            self._selected_catalog = (model, quant)
            self.dl_status.config(
                text=f"{model.name}  →  {quant.label}  ({quant.size_gb:.1f} GB)  [{model.repo_id}]"
            )

    # ------------------------------------------------------------------ Download
    def _start_download(self):
        if not hasattr(self, "_selected_catalog"):
            messagebox.showwarning("No selection", "Please select a recommended model first.")
            return

        model, quant = self._selected_catalog
        self._download_cancel = False
        self.progress["value"] = 0
        self.dl_status.config(text=f"Downloading {quant.filename} …")

        def worker():
            try:
                from llm.hf_models import download_gguf

                def progress_cb(name, downloaded, total):
                    if total and total > 0:
                        pct = min(100, int(downloaded * 100 / total))
                        self.after(0, lambda: self.progress.configure(value=pct))

                local_path = download_gguf(
                    repo_id=model.repo_id,
                    filename=quant.filename,
                    dest_dir=self.models_dir,
                    progress=progress_cb,
                )
                self.after(0, lambda: self._download_finished(local_path))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Download failed", str(e)))
                self.after(0, lambda: self.dl_status.config(text="Download failed"))

        threading.Thread(target=worker, daemon=True).start()

    def _download_finished(self, local_path: str):
        self.progress["value"] = 100
        self.dl_status.config(text=f"Downloaded: {Path(local_path).name}")
        self.selected_path = local_path
        self._refresh_installed()
        messagebox.showinfo("Download complete", f"Saved to:\n{local_path}\n\nYou can now click Use / Apply.")

    # ------------------------------------------------------------------ Apply
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
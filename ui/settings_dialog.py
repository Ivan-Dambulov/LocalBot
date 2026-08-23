"""
Settings / Model Manager dialog.

Layout philosophy:
  Hardware (compact) → Installed models → Recommended for you → Library
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QWidget,
    QCheckBox,
    QLineEdit,
    QProgressBar,
    QComboBox,
    QScrollArea,
    QFrame,
    QDialogButtonBox,
    QTextEdit,
)

from llm.hardware import (
    HardwareInfo,
    detect_hardware,
    format_hardware_summary,
    recommend_gpu_layers,
    recommend_context_size,
)
from llm.model_manager import scan_models, ModelInfo
from llm.model_catalog import (
    CatalogModel,
    QuantOption,
    Compatibility,
    families,
    models_for_family,
    score_quant_for_hardware,
    best_quant_for_hardware,
    estimate_max_params_b,
)
from llm.hf_models import download_gguf, list_gguf_files


class DownloadWorker(QThread):
    progress = Signal(str, int, object)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, repo_id, filename, dest_dir, token=None, parent=None):
        super().__init__(parent)
        self.repo_id = repo_id
        self.filename = filename
        self.dest_dir = dest_dir
        self.token = token

    def run(self):
        try:
            def cb(name, done, total):
                self.progress.emit(name, done, total)

            path = download_gguf(
                self.repo_id,
                self.filename,
                self.dest_dir,
                token=self.token,
                progress=cb,
            )
            self.finished_ok.emit(path)
        except Exception as exc:
            self.failed.emit(str(exc))


class ResolveFilenameWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, repo_id: str, quant_label: str, hint_filename: str, parent=None):
        super().__init__(parent)
        self.repo_id = repo_id
        self.quant_label = quant_label
        self.hint_filename = hint_filename

    def run(self):
        try:
            files = list_gguf_files(self.repo_id)
            for f in files:
                if f.filename == self.hint_filename:
                    self.finished_ok.emit(f.filename)
                    return
            q = self.quant_label.lower().replace("-", "_")
            for f in files:
                if q in f.filename.lower().replace("-", "_"):
                    self.finished_ok.emit(f.filename)
                    return
            if files:
                self.finished_ok.emit(files[0].filename)
            else:
                self.failed.emit("No GGUF files found in repo.")
        except Exception:
            self.finished_ok.emit(self.hint_filename)


def _card() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.StyledPanel)
    f.setStyleSheet(
        "QFrame { background: palette(base); border: 1px solid palette(mid); "
        "border-radius: 6px; padding: 4px; }"
    )
    return f


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        models_dir: str = "models",
        current_model: str = "",
        current_gpu_layers: int = 0,
        current_context: int = 8192,
    ):
        super().__init__(parent)
        self.setWindowTitle("Model Manager")
        self.resize(820, 700)
        self.setModal(True)

        self.models_dir = models_dir
        self.hardware: HardwareInfo = detect_hardware()
        self.selected_model_path: Optional[str] = current_model or None
        self.gpu_layers = current_gpu_layers
        self.context_size = current_context
        self.use_auto_settings = True

        self._installed: List[ModelInfo] = []
        self._family_filter = "All"
        self._dl_worker: Optional[DownloadWorker] = None
        self._resolve_worker: Optional[ResolveFilenameWorker] = None
        self._quant_combos: Dict[str, QComboBox] = {}

        self._build_ui()
        self._refresh_hardware_strip()
        self._refresh_installed()
        self._rebuild_catalog_list()

        if current_model:
            self._highlight_installed(current_model)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        self.hw_frame = _card()
        hw_layout = QVBoxLayout(self.hw_frame)
        self.hw_summary = QLabel()
        self.hw_summary.setWordWrap(True)
        self.hw_summary.setTextFormat(Qt.RichText)
        hw_layout.addWidget(self.hw_summary)

        hw_btn_row = QHBoxLayout()
        details_btn = QPushButton("View details")
        details_btn.clicked.connect(self._show_hardware_details)
        hw_btn_row.addWidget(details_btn)
        redetect_btn = QPushButton("Re-detect")
        redetect_btn.clicked.connect(self._redetect)
        hw_btn_row.addWidget(redetect_btn)
        hw_btn_row.addStretch()
        hw_layout.addLayout(hw_btn_row)
        root.addWidget(self.hw_frame)

        root.addWidget(self._section_label("Installed models"))
        self.installed_host = QVBoxLayout()
        installed_wrap = QWidget()
        installed_wrap.setLayout(self.installed_host)
        installed_scroll = QScrollArea()
        installed_scroll.setWidgetResizable(True)
        installed_scroll.setWidget(installed_wrap)
        installed_scroll.setMinimumHeight(110)
        installed_scroll.setMaximumHeight(180)
        root.addWidget(installed_scroll)

        root.addWidget(self._section_label("Available models"))

        filter_row = QHBoxLayout()
        self.filter_buttons: Dict[str, QPushButton] = {}
        for name in ["All"] + families():
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "All")
            btn.clicked.connect(lambda checked, n=name: self._set_family(n))
            self.filter_buttons[name] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch()
        root.addLayout(filter_row)

        self.catalog_host = QVBoxLayout()
        catalog_wrap = QWidget()
        catalog_wrap.setLayout(self.catalog_host)
        catalog_scroll = QScrollArea()
        catalog_scroll.setWidgetResizable(True)
        catalog_scroll.setWidget(catalog_wrap)
        catalog_scroll.setMinimumHeight(240)
        root.addWidget(catalog_scroll, 1)

        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(False)
        root.addWidget(self.dl_progress)
        self.dl_status = QLabel("")
        self.dl_status.setStyleSheet("color: gray;")
        root.addWidget(self.dl_status)

        runtime = QGroupBox("Runtime (applied on next launch)")
        form = QFormLayout(runtime)
        self.auto_check = QCheckBox("Auto GPU layers & context from hardware")
        self.auto_check.setChecked(True)
        self.auto_check.toggled.connect(self._on_auto_toggled)
        form.addRow(self.auto_check)

        self.gpu_spin = QSpinBox()
        self.gpu_spin.setRange(-1, 999)
        self.gpu_spin.setSpecialValueText("auto (-1)")
        self.gpu_spin.setValue(self.gpu_layers)
        form.addRow("GPU layers:", self.gpu_spin)

        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 131072)
        self.ctx_spin.setSingleStep(512)
        self.ctx_spin.setValue(self.context_size)
        form.addRow("Context size:", self.ctx_spin)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("HF token (optional, gated models)")
        form.addRow("Token:", self.token_edit)

        root.addWidget(runtime)
        self._on_auto_toggled(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        return QLabel(f"<b>{text}</b>")

    def _hw_budget(self):
        g = self.hardware.primary_gpu
        vram = self.hardware.primary_vram_mb
        shared = bool(g and g.shared_memory)
        return vram, self.hardware.total_ram_gb, shared

    def _refresh_hardware_strip(self):
        h = self.hardware
        g = h.primary_gpu
        if g:
            gpu_line = f"<b>{g.name}</b> · {g.total_vram_mb / 1024:.0f} GB VRAM"
            if g.shared_memory:
                gpu_line += " (unified)"
        else:
            gpu_line = "<b>No GPU detected</b> (CPU only)"

        vram, ram, shared = self._hw_budget()
        max_b = estimate_max_params_b(vram, ram, shared)
        if max_b < 2:
            size_hint = "up to ~1–3B"
        elif max_b < 5:
            size_hint = "up to ~3–7B"
        elif max_b < 10:
            size_hint = "up to ~7–14B"
        elif max_b < 20:
            size_hint = "up to ~14–20B"
        else:
            size_hint = f"up to ~{int(max_b)}B+"

        self.hw_summary.setText(
            f"Hardware detected ✓ &nbsp;&nbsp; {gpu_line}<br>"
            f"CPU {h.cpu_name} · {h.physical_cores}c/{h.logical_cores}t · "
            f"RAM {h.total_ram_gb:.0f} GB<br>"
            f"<span style='color:gray'>Recommended model size: {size_hint} "
            f"(Q4 quant, comfortable)</span>"
        )

        if self.auto_check.isChecked():
            self.gpu_spin.setValue(recommend_gpu_layers(h))
            self.ctx_spin.setValue(recommend_context_size(h))

    def _redetect(self):
        self.hardware = detect_hardware()
        self._refresh_hardware_strip()
        self._refresh_installed()
        self._rebuild_catalog_list()

    def _show_hardware_details(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Hardware details")
        dlg.resize(480, 360)
        lay = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(format_hardware_summary(self.hardware))
        lay.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    def _on_auto_toggled(self, checked: bool):
        self.use_auto_settings = checked
        self.gpu_spin.setEnabled(not checked)
        self.ctx_spin.setEnabled(not checked)
        if checked:
            self.gpu_spin.setValue(recommend_gpu_layers(self.hardware))
            self.ctx_spin.setValue(recommend_context_size(self.hardware))

    def _refresh_installed(self):
        while self.installed_host.count():
            item = self.installed_host.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._installed = scan_models(self.models_dir, self.hardware)

        if not self._installed:
            empty = QLabel(
                f"No GGUF files in <code>{os.path.abspath(self.models_dir)}</code>. "
                "Download one below."
            )
            empty.setWordWrap(True)
            empty.setStyleSheet("color: gray; padding: 8px;")
            self.installed_host.addWidget(empty)
            return

        for m in self._installed:
            self.installed_host.addWidget(self._make_installed_card(m))
        self.installed_host.addStretch()

    def _make_installed_card(self, m: ModelInfo) -> QWidget:
        card = _card()
        row = QHBoxLayout(card)

        is_active = (
            self.selected_model_path
            and Path(self.selected_model_path).resolve() == Path(m.path).resolve()
        )
        status = "● Active" if is_active else "✓ Ready"
        status_color = "#2980b9" if is_active else "#27ae60"

        left = QVBoxLayout()
        title = QLabel(f"<b>{m.filename}</b>")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(title)
        meta = QLabel(
            f"{m.quant} · {m.size_gb:.1f} GB"
            + (f" · {m.param_hint}" if m.param_hint else "")
        )
        meta.setStyleSheet("color: gray;")
        left.addWidget(meta)
        row.addLayout(left, 1)

        status_lab = QLabel(status)
        status_lab.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        row.addWidget(status_lab)

        use_btn = QPushButton("Use")
        use_btn.setEnabled(not is_active)
        use_btn.clicked.connect(lambda checked=False, p=m.path: self._use_model(p))
        row.addWidget(use_btn)
        return card

    def _use_model(self, path: str):
        self.selected_model_path = path
        try:
            size_mb = Path(path).stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = None
        if self.auto_check.isChecked():
            self.gpu_spin.setValue(
                recommend_gpu_layers(self.hardware, model_size_mb=size_mb)
            )
            self.ctx_spin.setValue(recommend_context_size(self.hardware))
        self._refresh_installed()
        self.dl_status.setText(f"Selected: {Path(path).name} (Apply + restart to load)")

    def _highlight_installed(self, path: str):
        self.selected_model_path = path
        self._refresh_installed()

    def _set_family(self, name: str):
        self._family_filter = name
        for n, btn in self.filter_buttons.items():
            btn.setChecked(n == name)
        self._rebuild_catalog_list()

    def _rebuild_catalog_list(self):
        while self.catalog_host.count():
            item = self.catalog_host.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._quant_combos.clear()

        vram, ram, shared = self._hw_budget()
        models = models_for_family(self._family_filter)

        scored = []
        for model in models:
            q = best_quant_for_hardware(model, vram, ram, shared)
            if q is None:
                continue
            comp = score_quant_for_hardware(q.size_gb, vram, ram, shared)
            scored.append((comp.score, -model.priority, model, q, comp))
        scored.sort(key=lambda t: (-t[0], -t[1]))

        shown = 0
        for score, _, model, best_q, comp in scored:
            if comp.level == "incompatible" and self._family_filter == "All":
                continue
            self.catalog_host.addWidget(self._make_catalog_card(model, best_q, comp))
            shown += 1

        if shown == 0:
            empty = QLabel("No models match this filter for your hardware.")
            empty.setStyleSheet("color: gray; padding: 12px;")
            self.catalog_host.addWidget(empty)

        self.catalog_host.addStretch()

    def _make_catalog_card(self, model: CatalogModel, best_q: QuantOption, comp: Compatibility) -> QWidget:
        """Compact row: Name · size · badge | quant dropdown | Download"""
        card = _card()
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)

        # Left: name + short meta
        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel(f"<b>{model.name}</b>")
        left.addWidget(title)
        meta = QLabel(f"{model.params_b:g}B · ~{best_q.size_gb:.1f} GB")
        meta.setStyleSheet("color: gray; font-size: 11px;")
        left.addWidget(meta)
        row.addLayout(left, 1)

        # Badge
        badge = QLabel(comp.label)
        badge.setStyleSheet(
            f"color: {comp.color}; font-weight: bold; font-size: 11px; padding: 0 6px;"
        )
        row.addWidget(badge)

        # Quant dropdown (short labels)
        combo = QComboBox()
        combo.setMinimumWidth(130)
        vram, ram, shared = self._hw_budget()
        default_idx = 0
        for i, q in enumerate(model.quants):
            c = score_quant_for_hardware(q.size_gb, vram, ram, shared)
            # Short: "Q4_K_M · 5.0 GB"
            combo.addItem(f"{q.label} · {q.size_gb:.1f} GB", q)
            if q.label == best_q.label:
                default_idx = i
        combo.setCurrentIndex(default_idx)
        self._quant_combos[model.id] = combo
        row.addWidget(combo)

        # Download / Installed
        already = self._is_installed_approx(model, best_q)
        dl_btn = QPushButton("Installed" if already else "Download")
        dl_btn.setFixedWidth(90)
        dl_btn.setEnabled(not already and comp.level != "incompatible")
        dl_btn.clicked.connect(
            lambda checked=False, m=model, c=combo: self._start_download_for(m, c.currentData())
        )
        row.addWidget(dl_btn)
        return card

    def _is_installed_approx(self, model: CatalogModel, q: QuantOption) -> bool:
        qtoken = q.label.lower().replace("-", "_")
        for m in self._installed:
            name = m.filename.lower().replace("-", "_")
            if qtoken in name and (
                f"{model.params_b:g}b" in name
                or model.family.lower() in name
                or model.id.split("-")[0] in name
            ):
                return True
        return False

    def _start_download_for(self, model: CatalogModel, quant: Optional[QuantOption]):
        if quant is None:
            return
        if self._dl_worker and self._dl_worker.isRunning():
            QMessageBox.information(self, "Busy", "A download is already running.")
            return

        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.dl_status.setText(f"Resolving file in {model.repo_id}…")

        self._resolve_worker = ResolveFilenameWorker(
            model.repo_id, quant.label, quant.filename, parent=self
        )
        self._resolve_worker.finished_ok.connect(
            lambda fn, m=model, q=quant: self._download_resolved(m, q, fn)
        )
        self._resolve_worker.failed.connect(self._on_dl_failed)
        self._resolve_worker.start()

    def _download_resolved(self, model: CatalogModel, quant: QuantOption, filename: str):
        token = self.token_edit.text().strip() or None
        self.dl_status.setText(f"Downloading {filename}…")

        self._dl_worker = DownloadWorker(
            repo_id=model.repo_id,
            filename=filename,
            dest_dir=self.models_dir,
            token=token,
            parent=self,
        )
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.finished_ok.connect(self._on_dl_finished)
        self._dl_worker.failed.connect(self._on_dl_failed)
        self._dl_worker.start()

    def _on_dl_progress(self, name: str, done: int, total):
        if total and total > 0:
            pct = int(min(100, done * 100 / total))
            self.dl_progress.setRange(0, 100)
            self.dl_progress.setValue(pct)
            self.dl_status.setText(
                f"{name}: {done/1024/1024:.0f} / {total/1024/1024:.0f} MB ({pct}%)"
            )
        else:
            self.dl_progress.setRange(0, 0)
            self.dl_status.setText(f"{name}: {done/1024/1024:.0f} MB…")

    def _on_dl_finished(self, path: str):
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setValue(100)
        self.dl_status.setText(f"Downloaded: {Path(path).name}")
        self.selected_model_path = path
        self._refresh_installed()
        self._rebuild_catalog_list()
        QMessageBox.information(
            self,
            "Download complete",
            f"Saved to:\n{path}\n\n"
            "It is selected under Installed models.\n"
            "Click Apply, then restart the app to load it.",
        )

    def _on_dl_failed(self, err: str):
        self.dl_progress.setVisible(False)
        self.dl_status.setText("Download failed.")
        QMessageBox.critical(
            self,
            "Download failed",
            f"{err}\n\n"
            "Tips:\n"
            "• pip install huggingface_hub\n"
            "• Check network / disk space\n"
            "• Gated models need a HF token",
        )

    def _on_apply(self):
        self.use_auto_settings = self.auto_check.isChecked()
        self.gpu_layers = self.gpu_spin.value()
        self.context_size = self.ctx_spin.value()
        self._save_preferences()
        QMessageBox.information(
            self,
            "Saved",
            "Preferences written to data/settings.ini.\n\n"
            "Restart the app to load the selected model.\n\n"
            f"Model: {self.selected_model_path or '(unchanged)'}\n"
            f"GPU layers: {self.gpu_layers}\n"
            f"Context: {self.context_size}",
        )
        self.accept()

    def _save_preferences(self):
        cfg_dir = Path("data")
        cfg_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            f"model_path={self.selected_model_path or ''}",
            f"gpu_layers={self.gpu_layers}",
            f"context_size={self.context_size}",
            f"models_dir={self.models_dir}",
            f"use_auto={1 if self.use_auto_settings else 0}",
        ]
        (cfg_dir / "settings.ini").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_preferences(path: str | Path = "data/settings.ini") -> dict:
    path = Path(path)
    result = {}
    if not path.is_file():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    except OSError:
        pass
    return result

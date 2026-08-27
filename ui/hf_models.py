"""
Hugging Face Hub helpers for searching and downloading GGUF models.

Requires: pip install huggingface_hub
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional

# Progress callback: (filename, bytes_downloaded, total_bytes_or_None)
ProgressCallback = Callable[[str, int, Optional[int]], None]


@dataclass
class HFRepoInfo:
    repo_id: str
    downloads: int = 0
    likes: int = 0
    tags: List[str] = field(default_factory=list)
    last_modified: str = ""

    @property
    def display(self) -> str:
        dl = f"{self.downloads:,}" if self.downloads else "?"
        return f"{self.repo_id}  (↓ {dl})"


@dataclass
class HFFileInfo:
    repo_id: str
    filename: str
    size_bytes: Optional[int] = None

    @property
    def size_gb(self) -> Optional[float]:
        if self.size_bytes is None:
            return None
        return self.size_bytes / (1024 ** 3)

    @property
    def quant(self) -> str:
        m = re.search(
            r"(q[2-8](?:_[k01]|_k_[msxl]+)?|iq[1-4]_[a-z]+|f16|bf16|fp16)",
            self.filename,
            re.IGNORECASE,
        )
        return m.group(1).upper() if m else "unknown"

    @property
    def display(self) -> str:
        size = f"{self.size_gb:.2f} GB" if self.size_gb is not None else "size ?"
        return f"{self.filename}  ·  {self.quant}  ·  {size}"


# Popular GGUF packs that work well with local assistants (curated shortcuts)
CURATED_REPOS = [
    ("Qwen/Qwen2.5-3B-Instruct-GGUF", "Small & fast (3B)"),
    ("Qwen/Qwen2.5-7B-Instruct-GGUF", "Balanced (7B)"),
    ("bartowski/Qwen2.5-7B-Instruct-GGUF", "Qwen 2.5 7B (bartowski quants)"),
    ("bartowski/Qwen2.5-3B-Instruct-GGUF", "Qwen 2.5 3B (bartowski quants)"),
    ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama 3.2 3B"),
    ("bartowski/Llama-3.2-1B-Instruct-GGUF", "Llama 3.2 1B (tiny)"),
    ("microsoft/Phi-3-mini-4k-instruct-gguf", "Phi-3 mini"),
    ("bartowski/Phi-3.5-mini-instruct-GGUF", "Phi-3.5 mini"),
    ("TheBloke/Mistral-7B-Instruct-v0.2-GGUF", "Mistral 7B Instruct"),
    ("liberic/Qwen3-4B-GGUF", "Qwen3 4B (if available)"),
]


def _require_hub():
    try:
        import huggingface_hub  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required for downloads.\n"
            "Install with:  pip install huggingface_hub"
        ) from exc


def search_gguf_repos(
    query: str,
    *,
    limit: int = 25,
    author: Optional[str] = None,
) -> List[HFRepoInfo]:
    """
    Search the Hub for model repos likely to contain GGUF files.
    Uses free-text search + gguf tag filter when possible.
    """
    _require_hub()
    from huggingface_hub import HfApi

    api = HfApi()
    q = (query or "").strip()

    # Prefer models tagged gguf; also allow plain search for "something gguf"
    kwargs = {
        "search": q if q else "gguf",
        "filter": "gguf",
        "sort": "downloads",
        "direction": -1,
        "limit": limit,
    }
    if author:
        kwargs["author"] = author

    results: List[HFRepoInfo] = []
    try:
        for model in api.list_models(**kwargs):
            results.append(
                HFRepoInfo(
                    repo_id=model.id,
                    downloads=getattr(model, "downloads", 0) or 0,
                    likes=getattr(model, "likes", 0) or 0,
                    tags=list(getattr(model, "tags", []) or []),
                    last_modified=str(getattr(model, "lastModified", "") or ""),
                )
            )
    except Exception:
        # Fallback without filter (older API / network quirks)
        kwargs.pop("filter", None)
        for model in api.list_models(**kwargs):
            tags = list(getattr(model, "tags", []) or [])
            mid = model.id.lower()
            if "gguf" in mid or "gguf" in tags:
                results.append(
                    HFRepoInfo(
                        repo_id=model.id,
                        downloads=getattr(model, "downloads", 0) or 0,
                        likes=getattr(model, "likes", 0) or 0,
                        tags=tags,
                    )
                )
            if len(results) >= limit:
                break

    return results


def list_gguf_files(repo_id: str) -> List[HFFileInfo]:
    """List .gguf files in a repo with sizes when available."""
    _require_hub()
    from huggingface_hub import HfApi

    api = HfApi()
    info = api.model_info(repo_id, files_metadata=True)
    files: List[HFFileInfo] = []

    siblings = getattr(info, "siblings", None) or []
    for sib in siblings:
        name = getattr(sib, "rfilename", None) or getattr(sib, "filename", "")
        if not name or not name.lower().endswith(".gguf"):
            continue
        size = getattr(sib, "size", None)
        files.append(
            HFFileInfo(
                repo_id=repo_id,
                filename=name,
                size_bytes=int(size) if size is not None else None,
            )
        )

    # Prefer mid-quality quants near the top for display
    preferred = ("q4_k_m", "q5_k_m", "q4_k_s", "q5_k_s", "q6_k", "q3_k_m")

    def sort_key(f: HFFileInfo):
        q = f.quant.lower()
        try:
            rank = preferred.index(q)
        except ValueError:
            rank = 50
        return (rank, f.size_bytes or 0)

    files.sort(key=sort_key)
    return files


def recommend_file_for_vram(
    files: Iterable[HFFileInfo],
    vram_mb: int,
    *,
    prefer_quant: str = "Q4_K_M",
) -> Optional[HFFileInfo]:
    """
    Pick a GGUF that likely fits in VRAM.
    Uses file size when known; otherwise prefers prefer_quant.
    """
    files = list(files)
    if not files:
        return None

    prefer = prefer_quant.upper()
    usable = max(0, vram_mb - 1800) if vram_mb > 0 else 10**12

    # Exact quant match that fits
    for f in files:
        if f.quant == prefer:
            if f.size_bytes is None or (f.size_bytes / (1024 * 1024)) < usable:
                return f

    # Any file that fits by size
    sized = [f for f in files if f.size_bytes is not None]
    sized.sort(key=lambda f: f.size_bytes or 0)
    for f in sized:
        if (f.size_bytes or 0) / (1024 * 1024) < usable:
            # Prefer higher quality among those that fit
            if f.quant.lower() in ("q4_k_m", "q5_k_m", "q4_k_s", "q5_k_s", "q6_k"):
                return f
    if sized:
        # smallest that exists
        for f in sized:
            if (f.size_bytes or 0) / (1024 * 1024) < usable:
                return f

    # Fallback: preferred quant name even without size
    for f in files:
        if f.quant == prefer:
            return f

    return files[0]


def download_gguf(
    repo_id: str,
    filename: str,
    dest_dir: str | Path,
    *,
    token: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """
    Download a single GGUF file into dest_dir (flat).

    Returns the local path to the downloaded file.
    Uses huggingface_hub resume support via local_dir.
    """
    _require_hub()
    from huggingface_hub import hf_hub_download

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Custom tqdm to report progress into the UI callback
    tqdm_class = None
    if progress is not None:
        tqdm_class = _make_tqdm_bridge(progress, filename)

    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(dest_dir),
        local_dir_use_symlinks=False,
        token=token,
        resume_download=True,
        tqdm_class=tqdm_class,
    )
    return str(Path(local_path).resolve())


def _make_tqdm_bridge(progress: ProgressCallback, default_name: str):
    """Build a tqdm subclass that forwards updates to a ProgressCallback."""
    from tqdm.auto import tqdm as std_tqdm

    class _BridgeTqdm(std_tqdm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._cb_name = kwargs.get("desc") or default_name

        def update(self, n=1):
            r = super().update(n)
            try:
                total = int(self.total) if self.total else None
                progress(self._cb_name, int(self.n), total)
            except Exception:
                pass
            return r

        def close(self):
            try:
                total = int(self.total) if self.total else int(self.n)
                progress(self._cb_name, int(self.n), total)
            except Exception:
                pass
            return super().close()

    return _BridgeTqdm

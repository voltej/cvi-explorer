"""
Download app cache (incl. 100 m cells) when missing — for Streamlit Cloud / HF Spaces.

Set one of (env or st.secrets):
  CVI_CACHE_URL   — https URL to app_cache.tar.gz / .tar.zst / .zip
  CVI_HF_DATASET  — Hugging Face dataset id, e.g. "voltej/cvi-app-cache"
  CVI_HF_FILENAME — archive name (default: app_cache.tar.gz)
  HF_TOKEN        — if the dataset is private
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from lib.paths import APP_CACHE, CELLS_100M, REPO

MARKER = APP_CACHE / ".bootstrap_ok"
DEFAULT_HF_FILE = "app_cache.tar.gz"

ProgressFn = Callable[[str], None]


def _log(msg: str, progress: ProgressFn | None) -> None:
    print(msg, flush=True)
    if progress is not None:
        progress(msg)


def _secret(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if v:
        return v
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return ""


def cache_ready_on_disk() -> bool:
    return CELLS_100M.exists() and CELLS_100M.stat().st_size > 0


def ensure_app_cache(
    force: bool = False,
    progress: ProgressFn | None = None,
) -> bool:
    """Ensure data/app_cache/ is present. Returns True if usable."""
    if cache_ready_on_disk() and not force:
        return True

    url = _secret("CVI_CACHE_URL")
    hf_ds = _secret("CVI_HF_DATASET")
    if not url and not hf_ds:
        _log(
            "No CVI_CACHE_URL / CVI_HF_DATASET secret — cannot download cache.",
            progress,
        )
        return cache_ready_on_disk()

    APP_CACHE.mkdir(parents=True, exist_ok=True)
    _log("Bootstrapping app cache (first boot downloads ~0.5 GB)…", progress)

    try:
        with tempfile.TemporaryDirectory(prefix="cvi_cache_") as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "cache_archive"
            if url:
                _download(url, archive, progress)
            else:
                fname = _secret("CVI_HF_FILENAME") or DEFAULT_HF_FILE
                _download_hf(hf_ds, fname, archive, progress)
            _log("Extracting archive…", progress)
            _extract(archive, REPO, progress)
    except Exception as e:
        _log(f"Bootstrap failed: {type(e).__name__}: {e}", progress)
        return False

    if cache_ready_on_disk():
        MARKER.write_text("ok\n")
        _log(f"App cache ready ({CELLS_100M.stat().st_size / 1e6:.0f} MB cells).", progress)
        return True
    _log("Bootstrap finished but cells_100m.parquet still missing.", progress)
    return False


def _download(url: str, dest: Path, progress: ProgressFn | None) -> None:
    _log(f"Downloading {url[:80]}…", progress)
    token = _secret("HF_TOKEN")
    headers = {"User-Agent": "focal-cvi-explorer/1.0"}
    if token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=1800) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        chunk = 8 * 1024 * 1024
        while True:
            buf = resp.read(chunk)
            if not buf:
                break
            f.write(buf)
            done += len(buf)
            if total:
                _log(f"  download {done / 1e6:.0f} / {total / 1e6:.0f} MB", progress)
            else:
                _log(f"  download {done / 1e6:.0f} MB…", progress)
    _log(f"  saved {dest.stat().st_size / 1e6:.1f} MB", progress)


def _download_hf(
    dataset_id: str,
    filename: str,
    dest: Path,
    progress: ProgressFn | None,
) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        raise RuntimeError(
            "huggingface_hub is not installed. "
            "Use CVI_CACHE_URL or add huggingface_hub to requirements."
        ) from e
    token = _secret("HF_TOKEN") or None
    _log(f"Downloading hf://{dataset_id}/{filename} …", progress)
    path = hf_hub_download(
        repo_id=dataset_id,
        filename=filename,
        repo_type="dataset",
        token=token,
    )
    shutil.copy2(path, dest)
    _log(f"  saved {dest.stat().st_size / 1e6:.1f} MB", progress)


def _extract(archive: Path, dest_root: Path, progress: ProgressFn | None) -> None:
    # Detect format from magic bytes (HF download may have no extension)
    head = archive.read_bytes()[:4]
    is_zip = head[:2] == b"PK"
    is_zst = head[:4] == b"\x28\xb5\x2f\xfd"
    is_gz = head[:2] == b"\x1f\x8b"
    name = archive.name.lower()
    if name.endswith(".zip"):
        is_zip = True
    if name.endswith(".zst"):
        is_zst = True
    if name.endswith(".gz") or name.endswith(".tgz"):
        is_gz = True

    if is_zip:
        _log("Extracting zip…", progress)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest_root)
        return

    if is_zst:
        _log("Extracting tar.zst…", progress)
        try:
            import zstandard as zstd
        except ImportError as e:
            raise RuntimeError(
                "zstandard required for .tar.zst — upload .tar.gz instead "
                "or add zstandard to requirements."
            ) from e
        dctx = zstd.ZstdDecompressor()
        tar_path = archive.parent / "cache.tar"
        with open(archive, "rb") as src, open(tar_path, "wb") as out:
            dctx.copy_stream(src, out)
        with tarfile.open(tar_path, "r:") as tf:
            tf.extractall(dest_root)
        return

    mode = "r:gz" if is_gz else "r:*"
    _log(f"Extracting tar ({mode})…", progress)
    with tarfile.open(archive, mode) as tf:
        tf.extractall(dest_root)

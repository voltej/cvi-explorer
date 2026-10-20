"""
Download app cache (incl. 100 m cells) when missing — for Streamlit Cloud / HF Spaces.

Set one of:
  CVI_CACHE_URL   — https URL to app_cache.tar.zst / .tar.gz / .zip
  CVI_HF_DATASET  — Hugging Face dataset id, e.g. "org/cvi-app-cache"
                    expects a file named app_cache.tar.zst (or .tar.gz) at repo root

Optional:
  CVI_HF_FILENAME — override archive name (default: app_cache.tar.zst)
  HF_TOKEN        — if the dataset is private
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from lib.paths import APP_CACHE, CELLS_100M, REPO


MARKER = APP_CACHE / ".bootstrap_ok"
DEFAULT_HF_FILE = "app_cache.tar.zst"


def cache_ready_on_disk() -> bool:
    return CELLS_100M.exists() and CELLS_100M.stat().st_size > 0


def ensure_app_cache(force: bool = False) -> bool:
    """Ensure data/app_cache/ is present. Returns True if usable."""
    if cache_ready_on_disk() and not force:
        return True

    url = os.environ.get("CVI_CACHE_URL", "").strip()
    hf_ds = os.environ.get("CVI_HF_DATASET", "").strip()
    if not url and not hf_ds:
        return cache_ready_on_disk()

    APP_CACHE.mkdir(parents=True, exist_ok=True)
    print("Bootstrapping app cache…")

    with tempfile.TemporaryDirectory(prefix="cvi_cache_") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "cache_archive"

        if url:
            _download(url, archive)
        else:
            fname = os.environ.get("CVI_HF_FILENAME", DEFAULT_HF_FILE).strip()
            _download_hf(hf_ds, fname, archive)

        _extract(archive, REPO)

    if cache_ready_on_disk():
        MARKER.write_text("ok\n")
        print(f"App cache ready at {APP_CACHE}")
        return True
    print("Bootstrap finished but cells_100m.parquet still missing.")
    return False


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {url} …")
    req = Request(url, headers={"User-Agent": "focal-cvi-explorer/1.0"})
    with urlopen(req, timeout=600) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    print(f"  saved {dest.stat().st_size / 1e6:.1f} MB")


def _download_hf(dataset_id: str, filename: str, dest: Path) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        raise SystemExit(
            "huggingface_hub is required for CVI_HF_DATASET. "
            "Add it to requirements or set CVI_CACHE_URL instead."
        ) from e
    token = os.environ.get("HF_TOKEN") or None
    print(f"Downloading hf://{dataset_id}/{filename} …")
    path = hf_hub_download(
        repo_id=dataset_id,
        filename=filename,
        repo_type="dataset",
        token=token,
    )
    shutil.copy2(path, dest)
    print(f"  saved {dest.stat().st_size / 1e6:.1f} MB")


def _extract(archive: Path, dest_root: Path) -> None:
    name = archive.name.lower()
    # Detect by magic if no extension
    head = archive.read_bytes()[:4]
    is_zip = head[:2] == b"PK" or name.endswith(".zip")
    is_zst = name.endswith(".zst") or name.endswith(".tar.zst")
    is_gz = name.endswith(".gz") or name.endswith(".tgz") or head[:2] == b"\x1f\x8b"

    if is_zip:
        print("Extracting zip…")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest_root)
        return

    if is_zst:
        print("Extracting tar.zst…")
        try:
            import zstandard as zstd
        except ImportError as e:
            raise SystemExit(
                "zstandard package required to extract .tar.zst"
            ) from e
        dctx = zstd.ZstdDecompressor()
        tar_path = archive.with_suffix("")  # strip .zst → .tar
        if not str(archive).endswith(".tar.zst"):
            tar_path = Path(str(archive) + ".tar")
        else:
            tar_path = Path(str(archive)[:-4])  # remove .zst
        with open(archive, "rb") as src, open(tar_path, "wb") as out:
            dctx.copy_stream(src, out)
        with tarfile.open(tar_path, "r:") as tf:
            tf.extractall(dest_root)
        return

    mode = "r:gz" if is_gz else "r:*"
    print(f"Extracting tar ({mode})…")
    with tarfile.open(archive, mode) as tf:
        tf.extractall(dest_root)

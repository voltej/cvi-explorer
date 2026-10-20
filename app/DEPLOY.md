# Publish the CVI explorer (full Germany 100 m cache)

The full cache is ~650 MB (`cells_100m` + aggregates + `cell_admin` + GeoJSON).
That is **too large for git** (GitHub 100 MB file limit). Publish **code** to
GitHub / Hugging Face Spaces, and host the **data archive** separately.

Recommended path for “all data including 100 m”:

1. Package cache locally  
2. Upload archive to a **Hugging Face dataset**  
3. Deploy the app to **Hugging Face Spaces** (Streamlit) *or* Streamlit Community Cloud with the same secrets  

Streamlit Community Cloud free tier is ~1 GB RAM — Kreis/Gemeinde/100 m-for-one-Kreis works; avoid nationwide 1 km without sampling.

---

## Step 0 — Prerequisites

- Hugging Face account: https://huggingface.co/join  
- HF access token (write): https://huggingface.co/settings/tokens  
- Optional: GitHub account if you use Streamlit Community Cloud  

---

## Step 1 — Package the 100 m cache (local)

```bash
cd /Users/vr/projects/cvi
# ensure cache exists
.venv/bin/python app/build_cache.py all   # skip if already built
# copy cell_admin into cache if missing
cp -n experiments/cell_admin_100m.parquet data/app_cache/

chmod +x app/package_cache.sh
./app/package_cache.sh dist
```

Produces e.g. `dist/app_cache.tar.zst` (or `.tar.gz`).

---

## Step 2 — Upload data to Hugging Face (dataset)

```bash
# one-time login
hf auth login
# paste your WRITE token

# create a dataset repo (pick your namespace)
hf repo create YOUR_HF_USER/cvi-app-cache --type dataset --private
# or --public if licenses allow (OSM is ODbL — prefer private)

# upload the archive
hf upload YOUR_HF_USER/cvi-app-cache dist/app_cache.tar.zst \
  --repo-type dataset
```

Note the dataset id: `YOUR_HF_USER/cvi-app-cache`.

---

## Step 3A — Deploy app on Hugging Face Spaces (recommended)

```bash
hf repo create YOUR_HF_USER/cvi-explorer --type space --space_sdk streamlit

# from repo root, upload app code (not the big data/)
hf upload YOUR_HF_USER/cvi-explorer app \
  --repo-type space
hf upload YOUR_HF_USER/cvi-explorer requirements.txt \
  --repo-type space
hf upload YOUR_HF_USER/cvi-explorer .streamlit \
  --repo-type space
# Space entry file: create a root streamlit_app.py that wraps app/
```

Or use the GitHub → Spaces sync UI.

**Space secrets** (Settings → Variables and secrets):

| Name | Value |
|---|---|
| `CVI_HF_DATASET` | `YOUR_HF_USER/cvi-app-cache` |
| `CVI_HF_FILENAME` | `app_cache.tar.zst` |
| `HF_TOKEN` | your read token (if dataset is private) |

**Space settings:**

- SDK: Streamlit  
- App file: `app/streamlit_app.py` (or root wrapper)  
- Hardware: CPU basic is OK to start; upgrade if OOM  

First boot downloads ~0.5–1 GB and extracts under `data/app_cache/`.

---

## Step 3B — Deploy on streamlit.io (Community Cloud)

1. Push **code only** to a GitHub repo (do **not** commit `data/app_cache/*.parquet`).  
2. Go to https://share.streamlit.io → **New app**  
3. Select repo, branch `main`, main file path: `deploy/streamlit_app.py`  
   (Python dependencies file: copy `deploy/requirements.txt` to repo-root `requirements.txt` for Cloud, or configure accordingly)  
4. Advanced settings → Secrets:

```toml
CVI_HF_DATASET = "YOUR_HF_USER/cvi-app-cache"
CVI_HF_FILENAME = "app_cache.tar.zst"
HF_TOKEN = "hf_..."   # if dataset private
```

Or a direct URL:

```toml
CVI_CACHE_URL = "https://huggingface.co/datasets/YOUR_HF_USER/cvi-app-cache/resolve/main/app_cache.tar.zst"
```

5. Deploy. First run will download the cache.

---

## Step 4 — Verify

- Open the app URL  
- **Data sources** page loads  
- Map → Features → e.g. `lst__summer_p90` at Kreis  
- Focus Kreis `Konstanz (08335)` → level **100 m**  
- **CVI outputs** → Demo CVI if bundled  

---

## What this repo already contains for deploy

| File | Role |
|---|---|
| `app/lib/bootstrap.py` | Download + extract cache on boot |
| `app/package_cache.sh` | Build `dist/app_cache.tar.*` |
| `app/requirements-cloud.txt` | Slim runtime deps |
| `requirements.txt` | Points Cloud/Spaces at cloud deps |
| `.streamlit/config.toml` | Headless / no usage stats |
| `data/app_cache/` | Local prebuilt cache (gitignored) |

---

## Status for `voltej` (2026-10-20)

Done:
- Dataset uploaded (private): https://huggingface.co/datasets/voltej/cvi-app-cache  
  File: `app_cache.tar.zst` (~469 MB, full 100 m cache)
- Local package + bootstrap code ready

Blocked without PRO / GitHub:
- Hugging Face **Spaces** (Docker/Gradio) requires a PRO plan on this account  
- Streamlit Community Cloud needs a **GitHub** repo (`gh auth login` not done yet)

### Finish on streamlit.io

1. `gh auth login` (browser)  
2. Create/push a GitHub repo with `app/`, `deploy/`, `.streamlit/` (not `data/` / `dist/`)  
3. https://share.streamlit.io → New app → main file `deploy/streamlit_app.py`  
4. Secrets:

```toml
CVI_HF_DATASET = "voltej/cvi-app-cache"
CVI_HF_FILENAME = "app_cache.tar.zst"
HF_TOKEN = "hf_..."   # read access to the private dataset
```

Or upgrade HF PRO and deploy the Docker Space under `deploy/Dockerfile`.


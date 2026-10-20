# FOCAL CVI — feature map explorer

Streamlit app for exploring FOCAL CVI features (and drop-in CVI outputs) on a map,
including Germany-wide aggregates and **100 m** cells for a selected Kreis.

## Streamlit Community Cloud

1. https://share.streamlit.io → **New app**
2. Repository: `voltej/cvi-explorer`
3. Branch: `main`
4. Main file path: `app/streamlit_app.py`
5. **Advanced settings → Secrets:**

```toml
CVI_HF_DATASET = "voltej/cvi-app-cache"
CVI_HF_FILENAME = "app_cache.tar.zst"
HF_TOKEN = "hf_..."
```

Use a **read** Hugging Face token that can access the private dataset  
https://huggingface.co/datasets/voltej/cvi-app-cache

First boot downloads ~470 MB and extracts `data/app_cache/`.

## Run locally

```bash
pip install -r requirements.txt
# Needs data/app_cache/ built locally, OR the secrets above
streamlit run app/streamlit_app.py
```

# FOCAL CVI — feature map explorer

Streamlit app for exploring FOCAL CVI features (and drop-in CVI outputs) on a map,
including Germany-wide aggregates and **100 m** cells for a selected Kreis.

## Run locally

```bash
pip install -r requirements.txt
# Needs prebuilt cache under data/app_cache/ OR cloud secrets (below)
streamlit run deploy/streamlit_app.py
```

## Streamlit Community Cloud

- Main file: `deploy/streamlit_app.py`
- Secrets (App settings → Secrets):

```toml
CVI_HF_DATASET = "voltej/cvi-app-cache"
CVI_HF_FILENAME = "app_cache.tar.zst"
HF_TOKEN = "hf_..."   # read access to private dataset
```

Data archive (private): https://huggingface.co/datasets/voltej/cvi-app-cache

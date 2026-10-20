---
title: FOCAL CVI Feature Explorer
emoji: 🗺️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: other
---

# FOCAL CVI — feature map explorer

Explores FOCAL CVI dataset features (and drop-in CVI outputs) on a map,
including Germany-wide aggregates and **100 m** cells for a selected Kreis.

## Secrets (Space → Settings → Variables and secrets)

| Name | Value |
|------|--------|
| `CVI_HF_DATASET` | `voltej/cvi-app-cache` |
| `CVI_HF_FILENAME` | `app_cache.tar.zst` |
| `HF_TOKEN` | read token (dataset is private) |

First boot downloads ~470 MB and extracts `data/app_cache/`.

"""Thin entrypoint for Streamlit Cloud / HF Spaces (main file = deploy/streamlit_app.py)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))
runpy.run_path(str(APP / "streamlit_app.py"), run_name="__main__")

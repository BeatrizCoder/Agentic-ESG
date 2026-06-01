"""Light import test for the Streamlit UI module."""

from __future__ import annotations

import importlib


def test_streamlit_app_importable():
    module = importlib.import_module("aamad.streamlit_app")
    assert hasattr(module, "main")

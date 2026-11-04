"""ASGI entrypoint for Vercel. The dashboard itself stays ordinary Streamlit Python."""
import os
from pathlib import Path

# Serverless bundles may omit hidden configuration files. These match config.toml.
for key, value in {
    'STREAMLIT_THEME_BASE': 'dark',
    'STREAMLIT_THEME_PRIMARY_COLOR': '#DDEB91',
    'STREAMLIT_THEME_BACKGROUND_COLOR': '#111113',
    'STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR': '#202024',
    'STREAMLIT_THEME_TEXT_COLOR': '#F1F1F3',
    'STREAMLIT_SERVER_HEADLESS': 'true',
}.items():
    os.environ.setdefault(key, value)

from streamlit import App, config

# An ASGI host can import Streamlit before this module; refresh its cached settings.
config.get_config_options(force_reparse=True)

app = App(Path(__file__).with_name('streamlit_app.py'))

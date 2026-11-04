"""ASGI entrypoint for Vercel. The dashboard itself stays ordinary Streamlit Python."""
from pathlib import Path

from streamlit import App

app = App(Path(__file__).with_name('streamlit_app.py'))

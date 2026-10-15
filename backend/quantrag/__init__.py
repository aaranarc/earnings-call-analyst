"""QuantRAG demo entry points (python -m quantrag.ask)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))  # check_manifest (not a package)

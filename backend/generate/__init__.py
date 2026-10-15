import sys
from pathlib import Path

# scripts/check_manifest.py holds the fiscal-quarter helpers and companies.yaml loader (not a package)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

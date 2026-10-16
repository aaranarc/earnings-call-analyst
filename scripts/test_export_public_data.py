import json

from export_public_data import ROOT, snapshot


def test_bundled_snapshot_matches_committed_inputs():
    from quantrag.api import companies, evaluation, monitor_report
    bundled = json.loads((ROOT / "frontend/lib/public-data.json").read_text())
    assert bundled == snapshot(ROOT)
    assert bundled["coverage"] == companies()
    assert bundled["evaluation"] == evaluation()
    assert bundled["monitor"] == monitor_report()

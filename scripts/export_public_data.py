"""Bundle public, committed coverage/evaluation so the web shell works while the API sleeps.

Run after ingestion/report publication. --check validates synchronization without changing files.
"""
import argparse
import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    entries = yaml.safe_load((root / "data/companies.yaml").read_text())
    stats = json.loads((root / "eval/results/ingest_stats.json").read_text())
    with (root / "data/manifest.csv").open() as f:
        sources = {(r["symbol"], r["fiscal_label"]): r["source_url"] for r in csv.DictReader(f)}
    for company in entries:
        company["documents"] = [dict(d, source_url=sources.get((d["symbol"], d["fiscal_label"])))
                                for d in stats["documents"] if d["symbol"] == company["symbol"]]
    report = root / "eval/results/public_eval.json"
    evaluation = json.loads(report.read_text()) if report.exists() else {
        "status": "pending", "metrics": [], "ablations": [], "failure_cases": [], "agreement": None, "last_run": None}
    from build_company_monitor import validate
    monitor = json.loads((root / "eval/results/company_monitor.json").read_text())
    with (root / "data/manifest.csv").open() as f:
        validate(monitor, list(csv.DictReader(f)))
    return {"coverage": {"companies": entries, "as_of": stats["date"], "source": "committed ingest snapshot"},
            "evaluation": evaluation, "monitor": monitor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "frontend/lib/public-data.json"
    text = json.dumps(snapshot(ROOT), indent=2) + "\n"
    if args.check:
        if not path.exists() or path.read_text() != text:
            raise SystemExit("Public web snapshot is stale. Run python scripts/export_public_data.py")
        print("Public snapshot matches committed coverage and evaluation.")
    else:
        path.write_text(text)
        print("Exported public coverage and evaluation.")


if __name__ == "__main__":
    main()

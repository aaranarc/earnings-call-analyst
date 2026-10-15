"""Validate data/manifest.csv against data/raw/ and data/companies.yaml.

    python scripts/check_manifest.py             # exit 1 on any error, or fewer than --min-rows complete rows
    python scripts/check_manifest.py --init      # write the 96 expected rows (symbol, fiscal_label, period_end)
    python scripts/check_manifest.py --fill-sha  # fill empty sha256 cells from the files in data/raw/

A row is "pending" until its filename is filled in; pending rows are listed, not counted as errors.
fiscal_label is our normalised April-March label: Q1 FY26 = Apr-Jun 2025, so period_end = 2025-06-30.
"""
import argparse
import csv
import hashlib
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["symbol", "fiscal_label", "period_end", "call_date", "source_url", "filename", "sha256"]
WINDOW = ("Q2 FY25", "Q1 FY27")  # docs/DECISIONS.md D8: same 8 quarters for every company
MAX_CALL_LAG = timedelta(days=120)  # calls happen a few weeks after quarter end; 120 days catches typos
LABEL_RE = re.compile(r"^Q([1-4]) FY(\d{2})$")


def parse_label(label):
    m = LABEL_RE.match(label)
    if not m:
        raise ValueError(f"bad fiscal_label {label!r}, expected like 'Q1 FY26'")
    return int(m[1]), 2000 + int(m[2])


def period_end(label):
    q, fy = parse_label(label)
    return {1: date(fy - 1, 6, 30), 2: date(fy - 1, 9, 30), 3: date(fy - 1, 12, 31), 4: date(fy, 3, 31)}[q]


def quarters(first, last):
    q, fy = parse_label(first)
    out = []
    while True:
        out.append(f"Q{q} FY{fy % 100:02d}")
        if out[-1] == last:
            return out
        q, fy = (1, fy + 1) if q == 4 else (q + 1, fy)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def load_companies(path):
    companies, errors, seen = {}, [], {}
    for c in yaml.safe_load(Path(path).read_text()):
        if c["symbol"] in companies:
            errors.append(f"companies.yaml: duplicate symbol {c['symbol']}")
        companies[c["symbol"]] = c
        for alias in c["aliases"]:
            other = seen.setdefault(alias.casefold(), c["symbol"])
            if other != c["symbol"]:
                errors.append(f"companies.yaml: alias {alias!r} used by both {other} and {c['symbol']}")
    return companies, errors


def read_manifest(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"manifest header must be {','.join(COLUMNS)}, got {reader.fieldnames}")
        return list(reader)


def write_manifest(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def check(manifest, companies_path, raw_dir):
    """Returns (complete_count, pending, errors, notes)."""
    companies, errors = load_companies(companies_path)
    window = set(quarters(*WINDOW))
    complete, pending, notes = 0, [], []
    keys, shas, files = set(), {}, set()

    for line, r in enumerate(read_manifest(manifest), start=2):
        where = f"manifest line {line} ({r['symbol']} {r['fiscal_label']})"
        before = len(errors)
        if r["symbol"] not in companies:
            errors.append(f"{where}: unknown symbol (not in companies.yaml)")
        try:
            pe = period_end(r["fiscal_label"])
            if r["fiscal_label"] not in window:
                errors.append(f"{where}: outside window {WINDOW[0]} -> {WINDOW[1]}")
            if r["period_end"] != pe.isoformat():
                errors.append(f"{where}: period_end {r['period_end']!r} should be {pe.isoformat()}")
        except ValueError as e:
            errors.append(f"{where}: {e}")
            pe = None
        key = (r["symbol"], r["fiscal_label"])
        if key in keys:
            errors.append(f"{where}: duplicate symbol + fiscal_label")
        keys.add(key)

        if not r["filename"]:
            pending.append(f"{r['symbol']} {r['fiscal_label']}")
            continue
        files.add(r["filename"])
        try:
            call = date.fromisoformat(r["call_date"])
            if pe and not (pe < call <= pe + MAX_CALL_LAG):
                errors.append(f"{where}: call_date {call} not within 120 days after period_end {pe}")
        except ValueError:
            errors.append(f"{where}: call_date {r['call_date']!r} is not YYYY-MM-DD")
        if not r["source_url"].startswith("https://"):
            errors.append(f"{where}: source_url must be an https:// link to where the PDF was downloaded")
        path = Path(raw_dir) / r["filename"]
        if not path.is_file():
            errors.append(f"{where}: file data/raw/{r['filename']} not found")
        elif sha256(path) != r["sha256"]:
            errors.append(f"{where}: sha256 does not match the file (run --fill-sha if the cell is empty)")
        if r["sha256"]:
            if r["sha256"] in shas:
                errors.append(f"{where}: same sha256 as {shas[r['sha256']]} (duplicate PDF)")
            shas.setdefault(r["sha256"], where)
        if len(errors) == before:
            complete += 1

    expected = {(s, q) for s in companies for q in window}
    missing = sorted(expected - keys)
    if missing:
        notes.append(f"{len(missing)} expected rows absent from manifest: " + ", ".join(f"{s} {q}" for s, q in missing))
    unlisted = sorted(p.name for p in Path(raw_dir).glob("*.pdf") if p.name not in files)
    if unlisted:
        notes.append(f"PDFs in data/raw/ not referenced by the manifest: {', '.join(unlisted)}")
    return complete, pending, errors, notes


def init(manifest, companies_path):
    if Path(manifest).exists():
        sys.exit(f"{manifest} already exists; not overwriting")
    companies, _ = load_companies(companies_path)
    rows = [{c: "" for c in COLUMNS} | {"symbol": s, "fiscal_label": q, "period_end": period_end(q).isoformat()}
            for s in companies for q in quarters(*WINDOW)]
    write_manifest(manifest, rows)
    return len(rows)


def fill_sha(manifest, raw_dir):
    rows, filled = read_manifest(manifest), 0
    for r in rows:
        path = Path(raw_dir) / r["filename"]
        if r["filename"] and not r["sha256"] and path.is_file():
            r["sha256"] = sha256(path)
            filled += 1
    write_manifest(manifest, rows)
    return filled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=ROOT / "data/manifest.csv")
    ap.add_argument("--companies", default=ROOT / "data/companies.yaml")
    ap.add_argument("--raw", default=ROOT / "data/raw")
    ap.add_argument("--min-rows", type=int, default=90)
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--fill-sha", action="store_true")
    a = ap.parse_args()
    if a.init:
        print(f"wrote {init(a.manifest, a.companies)} rows to {a.manifest}")
        return
    if a.fill_sha:
        print(f"filled {fill_sha(a.manifest, a.raw)} sha256 cells")

    complete, pending, errors, notes = check(a.manifest, a.companies, a.raw)
    for e in errors:
        print("ERROR", e)
    for n in notes:
        print("NOTE ", n)
    print(f"\ncomplete rows: {complete} (need {a.min_rows}) · pending: {len(pending)} · errors: {len(errors)}")
    if pending:
        print("pending:", ", ".join(pending))
    sys.exit(1 if errors or complete < a.min_rows else 0)


if __name__ == "__main__":
    main()

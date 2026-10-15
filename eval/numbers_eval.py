"""Score the number checker against human labels.

    python eval/numbers_eval.py [path/to/labelled.csv]     (default: eval/numbers_to_label.csv)

Reads the labelled sheet (built by eval/numbers_label.py; `label` filled in by a human), writes
eval/numbers_gold.jsonl, and writes eval/results/numcheck_<date>_<git sha>.json with, for real / corrupted / all rows:
  - accuracy over the four statuses, and the confusion matrix (gold rows x checker columns)
  - precision and recall of `unverified` (positive = gold label unverified): how often a red badge is right, and how
    many truly unsupported numbers get a red badge
Rows without a label are ignored. Nothing is reported until at least one row is labelled.
"""
import csv
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("verified", "derived", "found_elsewhere", "unverified")


def metrics(pairs):
    """pairs: [(gold, predicted)]"""
    n = len(pairs)
    conf = {g: {p: sum(1 for a, b in pairs if a == g and b == p) for p in LABELS} for g in LABELS}
    tp = conf["unverified"]["unverified"]
    pred_pos = sum(conf[g]["unverified"] for g in LABELS)
    gold_pos = sum(conf["unverified"].values())
    return {"n": n, "accuracy": round(sum(conf[g][g] for g in LABELS) / n, 3) if n else None,
            "unverified_precision": round(tp / pred_pos, 3) if pred_pos else None,
            "unverified_recall": round(tp / gold_pos, 3) if gold_pos else None,
            "gold_unverified": gold_pos, "predicted_unverified": pred_pos, "confusion": conf}


def main():
    sheet = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "eval/numbers_to_label.csv"
    run = json.loads((ROOT / "eval/results/numcheck_answers.json").read_text())
    predicted = {n["id"]: n["status"] for a in run["answers"] for n in a["numbers"]}
    corrupted = {c["id"]: c for c in run["corrupted"]}
    predicted |= {k: c["status"] for k, c in corrupted.items()}
    key = run["sheet_id_to_number_id"]

    gold, bad = [], []
    with open(sheet, newline="") as f:
        for r in csv.DictReader(f):
            label = r["label"].strip().lower()
            if not label:
                continue
            if label not in LABELS:
                bad.append(f"{r['id']}: '{r['label']}'")
                continue
            nid = key[r["id"]]
            gold.append({"sheet_id": r["id"], "number_id": nid, "question": r["question"], "number": r["number"],
                         "answer_sentence": r["answer_sentence"], "label": label, "notes": r["notes"],
                         "corrupted": nid in corrupted, "corruption": corrupted.get(nid, {}).get("kind"),
                         "checker": predicted[nid]})
    if bad:
        sys.exit("unknown labels (use " + " | ".join(LABELS) + "):\n  " + "\n  ".join(bad))
    if not gold:
        sys.exit(f"no labelled rows in {sheet}; fill the `label` column first (see PROGRESS.md labelling guide)")

    (ROOT / "eval/numbers_gold.jsonl").write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in gold))
    result = {
        "git_sha": subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True,
                                  cwd=ROOT).stdout.strip(),
        "date": datetime.date.today().isoformat(), "gemini_model": run["gemini_model"],
        "labelled": len(gold), "of": len(key),
        "real": metrics([(g["label"], g["checker"]) for g in gold if not g["corrupted"]]),
        "corrupted": metrics([(g["label"], g["checker"]) for g in gold if g["corrupted"]]),
        "all": metrics([(g["label"], g["checker"]) for g in gold]),
        "disagreements": [g for g in gold if g["label"] != g["checker"]],
    }
    out = ROOT / f"eval/results/numcheck_{result['date']}_{result['git_sha']}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    for part in ("real", "corrupted", "all"):
        m = result[part]
        print(f"{part:9} n={m['n']:3}  accuracy {m['accuracy']}  unverified precision {m['unverified_precision']} "
              f"recall {m['unverified_recall']}  (gold {m['gold_unverified']}, flagged {m['predicted_unverified']})")
    print(f"{len(result['disagreements'])} disagreements · {result['labelled']}/{result['of']} labelled -> {out}")


if __name__ == "__main__":
    main()

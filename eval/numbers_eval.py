"""Score the number checker against human labels.

    python eval/numbers_eval.py

Inputs: eval/labels/numbers_labels.csv (from eval/label_server.py: supported | not_supported | unsure) and the answer
key eval/private/numcheck_key.json (which rows are corrupted, how, and the checker's status).
Positive class = a human says the number is NOT SUPPORTED by its cited excerpts. Two ways to count a checker flag:
  red   status == unverified
  any   status != verified (unverified, found_elsewhere or derived: anything not shown as a green badge)
For each, precision (how often a flag is right) and recall (how many unsupported numbers get flagged), for real,
corrupted and all rows, plus recall per corruption type. `unsure` rows are left out and counted.

Until EVERY row is labelled, results go to eval/private/numcheck_partial.json only, because gold rows carry key
fields (D33). When labelling is complete, it writes eval/numbers_gold.jsonl and eval/results/numcheck_<date>_<sha>.json.
"""
import csv
import datetime
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAGS = {"red": lambda s: s == "unverified", "any": lambda s: s != "verified"}


def scores(rows):
    out = {"n": len(rows), "not_supported": sum(r["gold_not_supported"] for r in rows)}
    for name, flagged in FLAGS.items():
        tp = sum(1 for r in rows if r["gold_not_supported"] and flagged(r["checker"]))
        fp = sum(1 for r in rows if not r["gold_not_supported"] and flagged(r["checker"]))
        fn = sum(1 for r in rows if r["gold_not_supported"] and not flagged(r["checker"]))
        out[name] = {"flagged": tp + fp, "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                     "recall": round(tp / (tp + fn), 3) if tp + fn else None, "tp": tp, "fp": fp, "fn": fn}
    return out


def main():
    key = json.loads((ROOT / "eval/private/numcheck_key.json").read_text())
    with open(ROOT / "eval/labels/numbers_labels.csv", newline="") as f:
        labels = {r["id"]: r for r in csv.DictReader(f)}
    with open(ROOT / "eval/numbers_to_label.csv", newline="") as f:
        sheet = {r["id"]: r for r in csv.DictReader(f)}

    gold = []
    for sid, lab in sorted(labels.items()):
        k = key["rows"][sid]
        gold.append({"sheet_id": sid, "number_id": k["number_id"], "question": sheet[sid]["question"],
                     "number": sheet[sid]["number"], "answer_sentence": sheet[sid]["answer_sentence"],
                     "label": lab["label"], "notes": lab["notes"], "kind": k["kind"], "corrupted": k["corrupted"],
                     "checker": k["status"], "gold_not_supported": lab["label"] == "not_supported"})
    scored = [g for g in gold if g["label"] != "unsure"]
    by_kind = defaultdict(list)
    for g in scored:
        by_kind[g["kind"]].append(g)
    complete = len(labels) == len(key["rows"])
    result = {
        "git_sha": subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True,
                                  cwd=ROOT).stdout.strip(),
        "date": datetime.date.today().isoformat(), "gemini_model": key["gemini_model"],
        "labelled": len(labels), "of": len(key["rows"]), "unsure": len(gold) - len(scored), "complete": complete,
        "real": scores([g for g in scored if not g["corrupted"]]),
        "corrupted": scores([g for g in scored if g["corrupted"]]),
        "all": scores(scored),
        "recall_by_corruption_type": {kind: {"n": len(rs), "not_supported": sum(r["gold_not_supported"] for r in rs),
                                             "red_recall": scores(rs)["red"]["recall"],
                                             "any_recall": scores(rs)["any"]["recall"]}
                                      for kind, rs in sorted(by_kind.items()) if kind != "real"},
        "disagreements": [g for g in scored if g["gold_not_supported"] != FLAGS["red"](g["checker"])],
    }
    if complete:
        (ROOT / "eval/numbers_gold.jsonl").write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in gold))
        out = ROOT / f"eval/results/numcheck_{result['date']}_{result['git_sha']}.json"
    else:
        out = ROOT / "eval/private/numcheck_partial.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"labelled {result['labelled']}/{result['of']} ({result['unsure']} unsure, left out)"
          + ("" if complete else " · PARTIAL: written to eval/private only"))
    for part in ("real", "corrupted", "all"):
        s = result[part]
        print(f"{part:9} n={s['n']:3} not_supported={s['not_supported']:3}  "
              + "  ".join(f"{f}: precision {s[f]['precision']} recall {s[f]['recall']}" for f in FLAGS))
    for kind, s in result["recall_by_corruption_type"].items():
        print(f"  {kind:16} n={s['n']:2} not_supported={s['not_supported']:2}  recall red {s['red_recall']}  "
              f"any {s['any_recall']}")
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

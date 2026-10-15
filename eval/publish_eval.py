"""Validate human agreement and prepare a public report from completed matching gold runs.

Human CSV: id,faithful,reviewed_by. Labels: supported,not_supported,unsure.
All answered IDs must be reviewed. Publish only with an explicit --out; refuses overwrites.
"""
import argparse
import csv
import json
from pathlib import Path


def agreement(rows, labels):
    answered = {r["id"]: r for r in rows if not r["answer"]["refused"]}
    if len({r["id"] for r in labels}) != len(labels) or {r["id"] for r in labels} != set(answered):
        raise ValueError("Human labels must cover every answered ID exactly once")
    if any(r.get("faithful") not in {"supported", "not_supported", "unsure"} or not r.get("reviewed_by", "").strip()
           for r in labels):
        raise ValueError("Human labels need supported/not_supported/unsure and a reviewer")
    pairs = [(r["faithful"] == "supported", answered[r["id"]]["judge"]["faithful"])
             for r in labels if r["faithful"] != "unsure"]
    if not pairs:
        return {"kappa": None, "sample_size": 0, "unsure": len(labels)}
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return {"kappa": (observed - expected) / (1 - expected) if expected < 1 else None,
            "sample_size": n, "unsure": len(labels) - n, "raw_agreement": observed}


def build_report(generation, retrieval, labels):
    if generation["gold_sha256"] != retrieval["gold_sha256"] or generation["corpus"] != retrieval["corpus"]:
        raise ValueError("Generation and retrieval must use the same frozen gold and corpus")
    if len(generation["rows"]) < 60:
        raise ValueError("Public benchmark requires the planned 60 reviewed questions")
    if generation["judge"]["family"].lower() in {"gemini", "google", ""}:
        raise ValueError("Cross-family judge required")
    agree = agreement(generation["rows"], labels)
    if not agree["sample_size"]:
        raise ValueError("Public report requires usable human agreement labels")
    metrics = [{"name": name, "value": generation["summary"][key], "definition": definition}
               for name, key, definition in [
                   ("Faithfulness", "faithfulness", "Cross-family judge: fraction of answered responses supported by cited text."),
                   ("Correctness", "correctness", "Cross-family judge: complete, correct responses against reviewed gold evidence."),
                   ("Refusal accuracy", "refusal_accuracy", "Answer/refusal decisions matching the gold answerability label.")]
               if generation["summary"][key] is not None]
    default = retrieval["configs"].get("hybrid:rerank=True:router=True")
    if default and default["summary"]["hit_at_5"] is not None:
        metrics.insert(0, {"name": "Hit rate @ 5", "value": default["summary"]["hit_at_5"],
                           "definition": "Global hybrid retrieval with router and reranker: at least one required evidence item in top 5."})
    ablations = [{"name": name, "hit_at_5": config["summary"]["hit_at_5"], "mrr_at_10": config["summary"]["mrr_at_10"]}
                 for name, config in retrieval["configs"].items()]
    failures = [{"question": r["answer"]["question"], "finding": r["judge"]["reason"]}
                for r in generation["rows"] if not r["judge"]["correct"] or (
                    not r["answer"]["refused"] and not r["judge"]["faithful"])]
    return {"status": "published", "metrics": metrics, "ablations": ablations, "agreement": agree,
            "failure_cases": failures[:5], "failure_cases_total": len(failures),
            "last_run": {"date": generation["created_at"], "commit": generation["git_sha"][:12]},
            "provenance": {"gold_sha256": generation["gold_sha256"], "corpus": generation["corpus"],
                           "generator": generation["generator"], "judge": generation["judge"]}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generation", type=Path, required=True)
    p.add_argument("--retrieval", type=Path, required=True)
    p.add_argument("--human-labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error("Output exists; archive it before publishing a new completed run")
    with args.human_labels.open() as f:
        labels = list(csv.DictReader(f))
    report = build_report(json.loads(args.generation.read_text()), json.loads(args.retrieval.read_text()), labels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as f:
        json.dump(report, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

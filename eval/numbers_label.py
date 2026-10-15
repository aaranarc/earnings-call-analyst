"""Build the blind labelling sheet for the number checker.

    cd backend && SUPABASE_DB_URL=... python ../eval/numbers_label.py                  # reuse saved answers
    cd backend && SUPABASE_DB_URL=... GEMINI_API_KEY=... GEMINI_MODEL=... python ../eval/numbers_label.py --regenerate

--regenerate asks Gemini the questions below and saves the answers (with the checker's statuses) to
eval/private/numcheck_answers.json. Without it, the saved answers are reused (no API calls).

Then it writes eval/numbers_to_label.csv: every real number plus deliberately corrupted copies of real answer
sentences (D32, D34), shuffled under neutral ids. The answer key (which rows are corrupted, how, and the checker's
status for each row) goes ONLY to eval/private/numcheck_key.json, git-ignored until labelling is done (D33).
Corruptions:
  value   (35)  one number changed: digit, scale word, % <-> bps, decimal slip
  context (~10) number unchanged, but attributed to the wrong company, quarter or metric
Label with eval/label_server.py.
"""
import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg

import check_manifest as cm
from numcheck.extract import extract
from numcheck.match import CITE, SENTENCE_END, check_text, load_sources

PRIVATE = ROOT / "eval/private"
SEED, N_VALUE, N_CONTEXT = 11, 35, 10  # seed changed from 7 after the first key was pushed (D33)
SMOKE = [json.loads(line)["question"] for line in (ROOT / "eval/smoke.jsonl").read_text().splitlines() if line]
QUESTIONS = SMOKE + [
    "Compare TCS and Infosys on large deal wins",
    "Compare HUL and HDFC Bank on how they described demand in the June 2026 quarter",
    "By how many basis points did TCS's operating margin change sequentially in Q1 FY27?",
    "What were TCS's net margin and DSO in Q1 FY27?",
    "How much free cash flow did Infosys generate in Q2 FY25 and in H1?",
    "What were Infosys's operating margin and attrition in Q2 FY25?",
    "What was Infosys's revenue in dollars in Q2 FY25 and how fast did it grow?",
    "What were HUL's EBITDA and profit after tax in the June 2026 quarter, and how much did they grow?",
    "How much higher was HUL's EBITDA than its profit after tax before exceptional items in the June 2026 quarter?",
    "What share of HUL's turnover was spent on advertising and promotion in the June 2026 quarter?",
    "What was HDFC Bank's business per branch in FY23 versus now, and what is the percentage increase?",
    "What did HDFC Bank say about its borrowing mix and where the industry is?",
    "What dividend did Infosys declare in Q2 FY25 and how much did it increase?",
    "How many employees did Infosys add in Q2 FY25 and what was the headcount?",
    "What utilization did Infosys report in Q2 FY25 and how did it change?",
    "How much AI services revenue does TCS have and how fast is it growing?",
    "What was TCS's revenue in rupees and in dollars in Q1 FY27?",
]
SCALE_SWAP = {"crore": "lakh", "crores": "lakhs", "billion": "million", "bn": "mn", "million": "billion",
              "mn": "bn", "lakh": "crore", "lakhs": "crores", "cr": "lakh"}
METRIC_SWAP = [("operating margin", "net margin"), ("net margin", "operating margin"), ("EBITDA", "PAT"),
               ("profit after tax", "EBITDA"), ("turnover", "profit after tax"), ("revenue", "net profit"),
               ("attrition", "utilization"), ("utilization", "attrition"), ("TCV", "revenue"),
               ("free cash flow", "net profit"), ("headcount", "attrition")]
PERIOD_SWAP = [("Q1 FY27", "Q4 FY26"), ("Q2 FY25", "Q1 FY25"), ("June 2026 quarter", "March 2026 quarter"),
               ("FY25", "FY24"), ("H1", "H2")]


def generate():
    from pgvector.psycopg import register_vector

    from generate.answer import answer
    from retrieve.search import Models
    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    models, answers = Models(rerank=True), []
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        for qi, q in enumerate(QUESTIONS, start=1):
            out = answer(q, conn, models, companies)
            answers.append({"answer_id": f"a{qi:02d}", "question": q, "refused": out["refused"],
                            "answer_markdown": out["answer_markdown"], "comparison_table": out["comparison_table"],
                            "cited_by_n": {i: h.chunk_id for i, h in enumerate(out["hits"], start=1)},
                            "numbers": [{"id": f"a{qi:02d}n{ni:02d}", **n} for ni, n in enumerate(out["numbers"], 1)]})
            print(f"a{qi:02d} {'REFUSED' if out['refused'] else len(out['numbers'])} numbers · {q[:70]}")
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "numcheck_answers.json").write_text(json.dumps(
        {"gemini_model": os.environ.get("GEMINI_MODEL"), "answers": answers}, indent=2, ensure_ascii=False))


def sentence_at(text, pos):
    bounds = [0] + [m.end() for m in SENTENCE_END.finditer(text)] + [len(text)]
    return next((text[a:b].strip() for a, b in pairwise(bounds) if a <= pos < b), text)


def corrupt_value(raw, rng):
    """One deliberate error in a number mention -> (new_raw, kind)."""
    kinds = ["digit", "decimal"]
    if re.search(r"\b(?:crores?|cr|billion|bn|million|mn|lakhs?)\b", raw):
        kinds.append("scale")
    if "%" in raw or "bps" in raw or "basis point" in raw:
        kinds.append("unit")
    kind = rng.choice(kinds)
    if kind == "digit":
        i = max(i for i, ch in enumerate(raw) if ch.isdigit())
        return raw[:i] + str((int(raw[i]) + rng.choice([1, 2, 3])) % 10) + raw[i + 1:], kind
    if kind == "scale":
        m = re.search(r"\b(crores?|cr|billion|bn|million|mn|lakhs?)\b", raw)
        return raw[:m.start()] + SCALE_SWAP[m[1]] + raw[m.end():], kind
    if kind == "unit":
        new = raw.replace("%", " bps", 1) if "%" in raw else re.sub(r"\s?(bps|basis points?)", "%", raw, count=1)
        return new, kind
    m = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
    return raw[:m.start()] + f"{float(m.group(0).replace(',', '')) * 10:g}" + raw[m.end():], kind


def context_swaps(sentence, number_raw, companies):
    """Wrong-attribution edits of a sentence, number untouched: [(new_sentence, kind, detail)]."""
    out = []
    by_sector = {}
    for sym, c in companies.items():
        by_sector.setdefault(c["sector"], []).append(sym)
    for sym, c in companies.items():
        alias = next((al for al in sorted(c["aliases"], key=len, reverse=True)
                      if re.search(rf"(?<!\w){re.escape(al)}(?!\w)", sentence)), None)
        if alias:
            other = next(s for s in by_sector[c["sector"]] if s != sym)
            new = re.sub(rf"(?<!\w){re.escape(alias)}(?!\w)", companies[other]["name"], sentence, count=1)
            out.append((new, "context-company", f"{alias} -> {companies[other]['name']}"))
            break
    for a, b in PERIOD_SWAP:
        if a in sentence:
            out.append((sentence.replace(a, b, 1), "context-period", f"{a} -> {b}"))
            break
    for a, b in METRIC_SWAP:
        if re.search(rf"\b{re.escape(a)}\b", sentence, re.IGNORECASE):
            out.append((re.sub(rf"\b{re.escape(a)}\b", b, sentence, count=1, flags=re.IGNORECASE), "context-metric",
                        f"{a} -> {b}"))
            break
    return [o for o in out if number_raw in o[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true", help="ask Gemini again (~37 calls)")
    a = ap.parse_args()
    if a.regenerate or not (PRIVATE / "numcheck_answers.json").exists():
        generate()
    run = json.loads((PRIVATE / "numcheck_answers.json").read_text())
    answers = run["answers"]
    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    rng = random.Random(SEED)
    rows = []  # each row carries its key fields until the shuffle; only sheet fields are written to the CSV

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        ids = sorted({cid for x in answers for cid in x["cited_by_n"].values()})
        meta = {r[0]: r[1:] for r in conn.execute(
            """select ch.id, co.name, d.fiscal_label, ch.speaker, ch.page, ch.text from chunks ch
               join documents d on d.id = ch.document_id join companies co on co.id = d.company_id
               where ch.id = any(%s)""", (ids,))}

        def excerpts(x, sentence):
            by_n = {int(k): v for k, v in x["cited_by_n"].items()}
            ns = [int(i) for i in CITE.findall(sentence)] or \
                list(dict.fromkeys(int(i) for i in CITE.findall(x["answer_markdown"])))
            return "\n\n".join(f"[c{n}] {meta[by_n[n]][0]} {meta[by_n[n]][1]} · {meta[by_n[n]][2]} (p{meta[by_n[n]][3]})"
                               f": {meta[by_n[n]][4]}" for n in ns if n in by_n)

        def recheck(x, new_text, start):
            by_n = {int(k): v for k, v in x["cited_by_n"].items()}
            chunk_numbers, elsewhere = load_sources(conn, list(by_n.values()))
            found = [c for c in check_text(new_text, by_n, chunk_numbers, elsewhere) if c.start == start]
            return found[0].status if found else None

        def row(x, nid, number, sentence, key):
            return {"number_id": nid, "question": x["question"], "number": number,
                    "answer_sentence": re.sub(r"\s+", " ", sentence), "cited_excerpts": excerpts(x, sentence),
                    "key": key}

        for x in answers:  # real numbers
            for n in x["numbers"]:
                if n["where"] == "answer":
                    sent = sentence_at(x["answer_markdown"], n["start"])
                else:
                    r, k = map(int, n["where"].split(":")[1:])
                    cell = x["comparison_table"][r]["cells"][k]
                    sent = f"[table] {x['comparison_table'][r]['metric']} · {cell['company']}: {cell['value']} " + \
                           "".join(f"[c{i}]" for i in cell["citations"])
                rows.append(row(x, n["id"], n["raw"], sent, {"corrupted": False, "kind": "real", "status": n["status"]}))

        pool = [(x, n) for x in answers for n in x["numbers"] if n["where"] == "answer"]
        for x, n in rng.sample(pool, min(N_VALUE, len(pool))):  # value corruptions
            new_raw, kind = corrupt_value(n["raw"], rng)
            text = x["answer_markdown"][:n["start"]] + x["answer_markdown"][n["start"]:].replace(n["raw"], new_raw, 1)
            status = recheck(x, text, n["start"])
            if status is not None and extract(new_raw):
                rows.append(row(x, f"{n['id']}v", new_raw, sentence_at(text, n["start"]),
                                {"corrupted": True, "kind": f"value-{kind}", "original": n["raw"], "status": status}))

        by_kind = {}  # context swaps, spread across company / period / metric
        for x, n in pool:
            if n["status"] == "verified":
                sent = sentence_at(x["answer_markdown"], n["start"])
                for new_sent, kind, detail in context_swaps(sent, n["raw"], companies):
                    by_kind.setdefault(kind, []).append((x, n, sent, new_sent, kind, detail))
        per_kind = -(-N_CONTEXT // max(len(by_kind), 1))
        picks = [p for kind in sorted(by_kind) for p in rng.sample(by_kind[kind], min(per_kind, len(by_kind[kind])))]
        used = set()
        for x, n, sent, new_sent, kind, detail in picks[:N_CONTEXT]:
            if (n["id"], kind) in used:
                continue
            used.add((n["id"], kind))
            text = x["answer_markdown"].replace(sent, new_sent, 1)
            start = text.find(new_sent) + new_sent.find(n["raw"])
            status = recheck(x, text, start)
            rows.append(row(x, f"{n['id']}c", n["raw"], new_sent,
                            {"corrupted": True, "kind": kind, "detail": detail, "status": status}))

    random.Random(SEED + 1).shuffle(rows)
    key = {}
    for i, r in enumerate(rows, start=1):
        r["id"] = f"n{i:03d}"
        key[r["id"]] = {"number_id": r.pop("number_id"), **r.pop("key")}
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "numcheck_key.json").write_text(json.dumps(
        {"seed": SEED, "gemini_model": run["gemini_model"], "rows": key}, indent=2, ensure_ascii=False))
    with open(ROOT / "eval/numbers_to_label.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "number", "answer_sentence", "cited_excerpts"])
        w.writeheader()
        w.writerows(rows)
    kinds = Counter(k["kind"] for k in key.values())
    print(f"{len(rows)} rows -> eval/numbers_to_label.csv · {dict(kinds)} · key -> eval/private/numcheck_key.json")


if __name__ == "__main__":
    main()

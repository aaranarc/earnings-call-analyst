"""Build the number-checker labelling sheet from real generated answers.

    cd backend && SUPABASE_DB_URL=... GEMINI_API_KEY=... GEMINI_MODEL=... python ../eval/numbers_label.py

Writes
  eval/results/numcheck_answers.json   every answer + the checker's status for each number (kept out of the sheet)
  eval/numbers_to_label.csv            one row per number: question, the answer sentence, the excerpts that sentence
                                       cites, and empty `label` / `notes` columns for a human
The sheet deliberately does NOT show the checker's status, so labels aren't anchored to it.
Labels: verified | derived | found_elsewhere | unverified   (see PROGRESS.md "Labelling guide").

Corrupted copies (D32): the real answers contain almost no wrong numbers, so ~35 copies of real answer sentences get
one number deliberately corrupted (digit changed, wrong scale word, % <-> bps, decimal slip). They're shuffled in
under neutral ids; which rows are corrupted, and how, is recorded only in numcheck_answers.json. Metrics are reported
separately for real and corrupted numbers.
"""
import csv
import json
import os
import random
import re
import sys
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg
from pgvector.psycopg import register_vector

import check_manifest as cm
from generate.answer import answer
from numcheck.extract import extract
from numcheck.match import CITE, SENTENCE_END, check_text, load_sources
from retrieve.search import Models

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


def sentence_at(text, pos):
    bounds = [0] + [m.end() for m in SENTENCE_END.finditer(text)] + [len(text)]
    for a, b in pairwise(bounds):
        if a <= pos < b:
            return text[a:b].strip()
    return text


SEED, N_CORRUPT = 7, 35
SCALE_SWAP = {"crore": "lakh", "crores": "lakhs", "billion": "million", "bn": "mn", "million": "billion",
              "mn": "bn", "lakh": "crore"}


def corrupt(raw, rng):
    """One deliberate error in a number mention. Returns (new_raw, kind) or None if no change applies."""
    kinds = []
    if re.search(r"\d", raw):
        kinds.append("digit")
    if re.search(r"\b(?:crores?|cr|billion|bn|million|mn|lakhs?)\b", raw):
        kinds.append("scale")
    if "%" in raw or "bps" in raw or "basis point" in raw:
        kinds.append("unit")
    if re.search(r"\d\.\d", raw) or re.search(r"\d", raw):
        kinds.append("decimal")
    kind = rng.choice(kinds)
    if kind == "digit":  # bump the last digit
        i = max(i for i, ch in enumerate(raw) if ch.isdigit())
        return raw[:i] + str((int(raw[i]) + rng.choice([1, 2, 3])) % 10) + raw[i + 1:], kind
    if kind == "scale":
        m = re.search(r"\b(crores?|cr|billion|bn|million|mn|lakhs?)\b", raw)
        return raw[:m.start()] + SCALE_SWAP.get(m[1], "lakh") + raw[m.end():], kind
    if kind == "unit":
        if "%" in raw:
            return raw.replace("%", " bps", 1), kind
        return re.sub(r"\s?(bps|basis points?)", "%", raw, count=1), kind
    m = re.search(r"(\d[\d,]*)(\.\d+)?", raw)  # decimal slip: x10
    num = float(m.group(0).replace(",", "")) * 10
    return raw[:m.start()] + f"{num:g}" + raw[m.end():], kind


def main():
    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    models = Models(rerank=True)
    answers, rows = [], []
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        for qi, q in enumerate(QUESTIONS, start=1):
            out = answer(q, conn, models, companies)
            hits = {i: h for i, h in enumerate(out["hits"], start=1)}
            record = {"answer_id": f"a{qi:02d}", "question": q, "refused": out["refused"],
                      "answer_markdown": out["answer_markdown"], "comparison_table": out["comparison_table"],
                      "numbers": []}
            for ni, n in enumerate(out["numbers"], start=1):
                nid = f"a{qi:02d}n{ni:02d}"
                record["numbers"].append({"id": nid, **n})
                if n["where"] == "answer":
                    sent = sentence_at(out["answer_markdown"], n["start"])
                else:  # table cell: show the cell with its citations
                    r, k = map(int, n["where"].split(":")[1:])
                    cell = out["comparison_table"][r]["cells"][k]
                    sent = f"[table] {out['comparison_table'][r]['metric']} · {cell['company']}: {cell['value']} " + \
                           "".join(f"[c{i}]" for i in cell["citations"])
                cites = [int(i) for i in CITE.findall(sent)] or \
                        list(dict.fromkeys(int(i) for i in CITE.findall(out["answer_markdown"])))
                excerpts = "\n\n".join(f"[c{i}] {hits[i].company} {hits[i].fiscal_label} · {hits[i].speaker} "
                                       f"(p{hits[i].page}): {hits[i].text}" for i in cites if i in hits)
                rows.append({"id": nid, "question": q, "number": n["raw"],
                             "answer_sentence": re.sub(r"\s+", " ", sent), "cited_excerpts": excerpts,
                             "label": "", "notes": ""})
            record["cited_by_n"] = {i: h.chunk_id for i, h in hits.items()}
            answers.append(record)
            print(f"{record['answer_id']} {'REFUSED' if out['refused'] else len(out['numbers'])} numbers · {q[:70]}")
        # corrupted copies: one number in a real answer sentence changed; checked against the same citations
        rng = random.Random(SEED)
        pool = [(a, n) for a in answers for n in a["numbers"] if n["where"] == "answer"]
        corrupted = []
        for a, n in rng.sample(pool, min(N_CORRUPT, len(pool))):
            new_raw, kind = corrupt(n["raw"], rng)
            text = a["answer_markdown"][:n["start"]] + a["answer_markdown"][n["start"]:].replace(n["raw"], new_raw, 1)
            cited_by_n = {int(k): v for k, v in a["cited_by_n"].items()}
            chunk_numbers, elsewhere = load_sources(conn, list(cited_by_n.values()))
            checks = [c for c in check_text(text, cited_by_n, chunk_numbers, elsewhere) if c.start == n["start"]]
            if not checks or not extract(new_raw):
                continue
            nid = f"{n['id']}x"
            corrupted.append({"id": nid, "of": n["id"], "kind": kind, "original": n["raw"], "raw": new_raw,
                              "status": checks[0].status})
            src = next(r for r in rows if r["id"] == n["id"])
            rows.append({**src, "id": nid, "number": new_raw,
                         "answer_sentence": src["answer_sentence"].replace(n["raw"], new_raw, 1)})
    # neutral, shuffled ids so real and corrupted rows can't be told apart while labelling
    rng = random.Random(SEED + 1)
    rng.shuffle(rows)
    key = {}
    for i, r in enumerate(rows, start=1):
        key[f"q{i:03d}"] = r["id"]
        r["id"] = f"q{i:03d}"
    (ROOT / "eval/results/numcheck_answers.json").write_text(json.dumps(
        {"gemini_model": os.environ.get("GEMINI_MODEL"), "answers": answers, "corrupted": corrupted,
         "sheet_id_to_number_id": key}, indent=2, ensure_ascii=False))
    with open(ROOT / "eval/numbers_to_label.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "number", "answer_sentence", "cited_excerpts", "label",
                                          "notes"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows ({len(rows) - len(corrupted)} real, {len(corrupted)} corrupted) from {len(answers)} "
          "answers -> eval/numbers_to_label.csv")


if __name__ == "__main__":
    main()

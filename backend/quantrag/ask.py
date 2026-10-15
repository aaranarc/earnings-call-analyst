"""One-command demo: ask a question, get a cited answer with every number checked.

    python -m quantrag.ask "Compare TCS and Infosys on large deal wins"

Reads SUPABASE_DB_URL, GEMINI_API_KEY and GEMINI_MODEL from the environment, or from the repo's .env.
Badges after each number: ✅ verified in the cited excerpt · 🟡 derived or found elsewhere in the transcript ·
🔴 unverified (check it yourself).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BADGE = {"verified": "✅", "derived": "🟡", "found_elsewhere": "🟡", "unverified": "🔴"}
BOLD, DIM, RESET = ("\033[1m", "\033[2m", "\033[0m") if sys.stdout.isatty() else ("", "", "")


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def with_badges(text, numbers):
    """Insert a badge after each checked number in the answer text (right to left so offsets stay valid)."""
    for n in sorted((n for n in numbers if n["where"] == "answer"), key=lambda n: -n["end"]):
        text = text[:n["end"]] + " " + BADGE[n["status"]] + text[n["end"]:]
    return text


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    question = " ".join(sys.argv[1:])
    load_env()
    for var in ("SUPABASE_DB_URL", "GEMINI_API_KEY", "GEMINI_MODEL"):
        if not os.environ.get(var):
            sys.exit(f"{var} is not set (put it in .env; see .env.example)")

    import psycopg
    from pgvector.psycopg import register_vector

    import check_manifest as cm
    from generate.answer import answer
    from retrieve.search import Models

    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    models = Models(rerank=True)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        out = answer(question, conn, models, companies)

    r = out["route"]
    print(f"{BOLD}Q:{RESET} {question}")
    print(f"{DIM}route: {r['kind']} · companies: {', '.join(r['companies']) or 'all'} · "
          f"periods: {', '.join(r['periods']) or 'all'}{RESET}\n")
    if out["refused"]:
        print(f"{BOLD}Not answered:{RESET} {out['refusal_reason']}")
        return
    print(with_badges(out["answer_markdown"], out["numbers"]), "\n")
    if out["comparison_table"]:
        cells = {n["where"]: BADGE[n["status"]] for n in out["numbers"] if n["where"].startswith("table")}
        for ri, row in enumerate(out["comparison_table"]):
            print(f"  {BOLD}{row['metric']}{RESET}")
            for ci, c in enumerate(row["cells"]):
                cite = "".join(f"[c{i}]" for i in c["citations"])
                print(f"    {c['company']}: {c['value']} {cells.get(f'table:{ri}:{ci}', '')} {cite}".rstrip())
        print()
    print(f"{BOLD}Sources{RESET}")
    for c in out["citations"]:
        print(f"  [c{c['n']}] {c['symbol']} {c['fiscal_label']} · {c['speaker']} ({c['role']}) · page {c['page']}")
    counts = {s: sum(n["status"] == s for n in out["numbers"]) for s in BADGE}
    print(f"\n{BOLD}Number check{RESET}  ✅ {counts['verified']} verified · "
          f"🟡 {counts['derived'] + counts['found_elsewhere']} derived/elsewhere · 🔴 {counts['unverified']} unverified")
    t = out["timing_s"]
    print(f"{DIM}{os.environ['GEMINI_MODEL']} · retrieve {t.get('retrieve', 0):.2f}s · "
          f"generate {t.get('generate', 0):.2f}s · total {t.get('total', 0):.2f}s{RESET}")


if __name__ == "__main__":
    main()

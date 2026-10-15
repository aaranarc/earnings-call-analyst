"""Route -> retrieve -> Gemini (structured output) -> validated, cited answer or a refusal.

The model sees numbered context chunks [c1]..[cN] and must cite every claim. Citations are then checked in code:
markers that don't point at a provided chunk are removed, and a non-refused answer with no valid citation is
turned into a refusal. Numbers are never extracted by the LLM: numcheck extracts every number from the final answer
(and each table cell) and checks it against the cited chunks (Phase 5).
"""
import os
import re
import time

from pydantic import BaseModel, Field

from generate.router import route
from numcheck.match import check_text, load_sources
from retrieve.search import retrieve

CITE = re.compile(r"\[c(\d+)\]")

PROMPT = """You are an equity research assistant answering questions about Indian companies' earnings calls.
Answer ONLY from the numbered transcript excerpts below. Each excerpt shows company, quarter, speaker, role and page.

Rules:
- Cite every sentence that states a fact with the excerpt marker(s) it comes from, like [c2] or [c1][c4].
- Copy figures exactly as written in the excerpts (same number, unit and scale). Do not calculate new figures.
- Say which quarter a figure refers to. Attribute views to the speaker's role (management vs analyst).
- If the excerpts do not contain the answer, set refused=true and explain briefly what is missing. Do not guess
  and do not use outside knowledge.
- {kind_rule}
- Keep the answer short: a few sentences or bullets in Markdown.

Question: {question}

Excerpts:
{context}
"""
KIND_RULES = {
    "comparison": "This is a comparison: also fill comparison_table with one row per metric and one cell per "
                  "company; every cell needs at least one citation. Leave a cell's value as 'not discussed' "
                  "(with no citation) if the excerpts don't cover it.",
    "risk": "This is a risk question: answer from what management and analysts said on the call only.",
}


class Cell(BaseModel):
    company: str
    value: str
    citations: list[int] = Field(default_factory=list, description="excerpt numbers, e.g. [2] for [c2]")


class Row(BaseModel):
    metric: str
    cells: list[Cell]


class LLMAnswer(BaseModel):
    answer_markdown: str = Field(description="the answer, with [cN] citation markers")
    comparison_table: list[Row] | None = None
    refused: bool = False
    refusal_reason: str | None = None


def make_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    model = os.environ.get("GEMINI_MODEL")
    if not model:
        raise RuntimeError("GEMINI_MODEL is not set (model IDs come from the environment, never the code)")
    llm = ChatGoogleGenerativeAI(model=model, temperature=0, api_key=os.environ["GEMINI_API_KEY"], max_retries=1, timeout=60, max_output_tokens=4096)
    return llm.with_structured_output(LLMAnswer)


def format_context(hits):
    return "\n\n".join(
        f"[c{i}] {h.company} · {h.fiscal_label} · {h.speaker} ({h.role}, "
        f"{'prepared remarks' if h.section == 'prepared' else 'Q&A' if h.section == 'qa' else 'call'}) · page {h.page}"
        f"\n{h.text}" for i, h in enumerate(hits, start=1))


def validate(ans: LLMAnswer, n):
    """Drop citation markers outside 1..n. Returns (answer, cited excerpt numbers in order of first use)."""
    text = CITE.sub(lambda m: m.group(0) if 1 <= int(m[1]) <= n else "", ans.answer_markdown)
    cited = list(dict.fromkeys(int(i) for i in CITE.findall(text)))
    table = None
    if ans.comparison_table:
        table = [Row(metric=r.metric, cells=[Cell(company=c.company, value=c.value if any(1 <= i <= n for i in c.citations)
                                                  else "not discussed", citations=[i for i in c.citations if 1 <= i <= n])
                                             for c in r.cells]) for r in ans.comparison_table]
        cited += [i for r in table for c in r.cells for i in c.citations if i not in cited]
    return ans.model_copy(update={"answer_markdown": text, "comparison_table": table}), cited


def coverage(conn, symbols=None):
    """{symbol: [fiscal labels ingested]} for refusals: say what *is* available."""
    rows = conn.execute("""select co.symbol, d.fiscal_label, d.period_end from documents d
                           join companies co on co.id = d.company_id
                           where %(s)s::text[] is null or co.symbol = any(%(s)s) order by co.symbol, d.period_end""",
                        {"s": symbols or None}).fetchall()
    out = {}
    for sym, label, _ in rows:
        out.setdefault(sym, []).append(label)
    return out


def latest_periods(conn):
    return {s: labels[-1] for s, labels in coverage(conn).items()}


def _refusal(reason, conn, companies, symbols):
    cov = coverage(conn, symbols)
    names = {s: companies[s]["name"] for s in companies}
    if symbols:
        avail = "; ".join(f"{names[s]}: {', '.join(cov[s]) if s in cov else 'no transcripts ingested yet'}"
                          for s in symbols)
    else:
        avail = "; ".join(f"{names[s]} ({', '.join(v)})" for s, v in cov.items())
    return f"{reason} Available transcripts: {avail}."


def answer(question, conn, models, companies, llm=None, use_rerank=True):
    """Returns a dict the CLI, the eval and the API all use."""
    t0 = time.perf_counter()
    rt = route(question, companies, latest_periods(conn))
    timing = {"route": time.perf_counter() - t0}
    out = {"question": question, "route": rt.__dict__, "hits": [], "answer_markdown": "", "comparison_table": None,
           "citations": [], "numbers": [], "refused": False, "refusal_reason": None, "timing_s": timing}
    if rt.kind == "out_of_scope":
        out.update(refused=True, refusal_reason=_refusal(
            "I can only answer questions about the earnings calls I cover.", conn, companies, None))
        return out

    if rt.companies:
        available = coverage(conn, rt.companies)
        missing = [f"{companies[s]['name']} ({', '.join(p for p in rt.periods if p not in available.get(s, []))})"
                   if available.get(s) else companies[s]["name"]
                   for s in rt.companies
                   if not available.get(s) or any(p not in available[s] for p in rt.periods)]
        if missing:
            out.update(refused=True, refusal_reason=_refusal(
                "The requested coverage is incomplete for " + "; ".join(missing) + ".", conn, companies, rt.companies))
            return out

    t = time.perf_counter()
    hits = retrieve(conn, models, question, rt.companies or None, rt.periods or None, use_rerank=use_rerank)
    timing["retrieve"] = time.perf_counter() - t
    out["hits"] = hits
    floor = os.environ.get("REFUSAL_MIN_RERANK")  # tuned in Phase 6; unset = only the model decides
    if not hits or (floor and use_rerank and max(h.scores.get("rerank", float("-inf")) for h in hits) < float(floor)):
        out.update(refused=True, refusal_reason=_refusal(
            "I couldn't find this in the transcripts I have.", conn, companies, rt.companies))
        return out

    t = time.perf_counter()
    llm = llm or make_llm()
    raw = llm.invoke(PROMPT.format(question=question, context=format_context(hits),
                                   kind_rule=KIND_RULES.get(rt.kind, "Answer directly.")))
    timing["generate"] = time.perf_counter() - t
    if rt.kind != "comparison":  # the model sometimes adds a table anyway; only comparisons get one
        raw = raw.model_copy(update={"comparison_table": None})
    ans, cited = validate(raw, len(hits))
    if not ans.refused and not cited:
        ans = ans.model_copy(update={"refused": True,
                                     "refusal_reason": "The model's answer had no valid citations, so it was withheld."})
    if ans.refused:
        out.update(refused=True, refusal_reason=_refusal(
            (ans.refusal_reason or "The transcripts don't contain this.").rstrip(".") + ".", conn, companies,
            rt.companies))
        return out
    md = ans.answer_markdown
    if rt.kind == "risk":
        md += "\n\n_Risk scores from the early-warning system aren't connected yet; this answer uses transcripts only._"
    out.update(answer_markdown=md, comparison_table=[r.model_dump() for r in ans.comparison_table or []] or None,
               citations=[{"n": i, "chunk_id": hits[i - 1].chunk_id, "symbol": hits[i - 1].symbol,
                           "fiscal_label": hits[i - 1].fiscal_label, "speaker": hits[i - 1].speaker,
                           "role": hits[i - 1].role, "page": hits[i - 1].page} for i in cited])
    t = time.perf_counter()
    out["numbers"] = check_numbers(conn, hits, ans)
    timing["numcheck"] = time.perf_counter() - t
    timing["total"] = time.perf_counter() - t0
    return out


def check_numbers(conn, hits, ans):
    """Every number in the answer text and in each table cell, with its status (numcheck/match.py)."""
    cited_by_n = {i: h.chunk_id for i, h in enumerate(hits, start=1)}
    chunk_numbers, elsewhere = load_sources(conn, [h.chunk_id for h in hits])
    found = [("answer", c) for c in check_text(ans.answer_markdown, cited_by_n, chunk_numbers, elsewhere)]
    for r, row in enumerate(ans.comparison_table or []):
        for k, cell in enumerate(row.cells):
            if cell.citations:  # "not discussed" cells have none
                text = cell.value + " " + "".join(f"[c{i}]" for i in cell.citations)
                found += [(f"table:{r}:{k}", c) for c in check_text(text, cited_by_n, chunk_numbers, elsewhere)]
    return [{"where": where, "raw": c.raw, "value": c.value, "unit": c.unit, "status": c.status,
             "start": c.start, "end": c.end, "formula": c.formula,
             "source": None if not c.source else {"chunk_id": c.source.chunk_id, "raw": c.source.raw}}
            for where, c in found]

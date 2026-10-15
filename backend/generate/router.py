"""Rule-based question router. Explainable and free: no LLM call.

    kind: single | comparison | risk | out_of_scope     (+ numeric flag when a figure is asked for)

Companies come from data/companies.yaml aliases (word-boundary, case-insensitive, longest alias first).
Periods: "Q1 FY27" / "Q1FY'27" / "FY26" (all four quarters) / "last quarter" / "last N quarters", resolved
against the latest ingested period per company. ROUTER_ENABLED=false routes everything as `single` with no
filters (for the Phase 6 ablation).
"""
import os
import re
from dataclasses import dataclass, field

import check_manifest as cm

COMPARE = re.compile(r"\b(?:vs\.?|versus|compare[ds]?|comparison|better|worse|against|relative to)\b", re.IGNORECASE)
RISK = re.compile(r"\b(?:risks?|risky|distress(?:ed)?|default(?:s|ed)?|downgrades?|debt stress|insolven\w*|"
                  r"bankrupt\w*|credit stress)\b", re.IGNORECASE)
FINANCE = re.compile(r"\b(?:revenue|sales|margin|growth|guidance|outlook|deals?|tcv|profit|pat|ebitda|ebit|"
                     r"earnings|results|quarter|fy\d*|q[1-4]|deposits?|loans?|advances|npa|provisions?|casa|"
                     r"attrition|headcount|employees|hiring|demand|pricing|prices?|volume|dividend|capex|cash|"
                     r"cost|inflation|tax|segment|clients?|management|ceo|cfo|chairman|strategy|ai|said|say)\b",
                     re.IGNORECASE)
NUMERIC = re.compile(r"\b(?:how (?:much|many|fast)|what (?:was|is|were) the (?:\w+ ){0,3}(?:rate|margin|ratio|"
                     r"revenue|growth|share|number|figure|amount|percentage)|percent(?:age)?|crores?|bps|"
                     r"basis points)\b|%|₹|\$", re.IGNORECASE)
PERIOD = re.compile(r"\bQ([1-4])\s*FY\s*'?(\d{2})\b", re.IGNORECASE)
FY_ONLY = re.compile(r"(?<!Q[1-4] )\bFY\s*'?(\d{2})\b", re.IGNORECASE)
LAST_N = re.compile(r"\blast\s+(?:(\d+|two|three|four)\s+)?quarters?\b", re.IGNORECASE)
WORDS = {"two": 2, "three": 3, "four": 4}


@dataclass
class Route:
    kind: str
    companies: list[str] = field(default_factory=list)   # NSE symbols
    periods: list[str] = field(default_factory=list)     # fiscal labels, e.g. "Q1 FY27"; empty = all
    numeric: bool = False
    reason: str = ""


def find_companies(question, companies):
    """Symbols in order of first mention."""
    hits = {}
    aliases = sorted(((a, sym) for sym, c in companies.items() for a in c["aliases"]), key=lambda x: -len(x[0]))
    taken = []
    for alias, sym in aliases:
        for m in re.finditer(rf"(?<![\w]){re.escape(alias)}(?![\w])", question, re.IGNORECASE):
            if not any(s <= m.start() < e for s, e in taken):  # "HDFC Bank" wins over "HDFC"
                taken.append((m.start(), m.end()))
                hits.setdefault(sym, m.start())
    return sorted(hits, key=hits.get)


def _previous(label, n):
    q, fy = cm.parse_label(label)
    out = []
    for _ in range(n):
        out.append(f"Q{q} FY{fy % 100:02d}")
        q, fy = (4, fy - 1) if q == 1 else (q - 1, fy)
    return out


def find_periods(question, symbols, latest):
    """latest: {symbol: latest ingested fiscal_label}. Returns fiscal labels (empty = no period filter)."""
    periods = [f"Q{q} FY{fy}" for q, fy in PERIOD.findall(question)]
    for fy in FY_ONLY.findall(question):
        periods += [f"Q{q} FY{fy}" for q in range(1, 5)]
    if m := LAST_N.search(question):
        n = int(WORDS.get((m[1] or "1").lower(), m[1] or 1))
        for sym in symbols or latest:
            if sym in latest:
                periods += _previous(latest[sym], n)
    return sorted(set(periods), key=lambda p: cm.period_end(p))


def route(question, companies, latest, enabled=None):
    """companies: {symbol: companies.yaml entry}; latest: {symbol: latest ingested fiscal_label}."""
    if enabled is None:
        enabled = os.environ.get("ROUTER_ENABLED", "true").lower() != "false"
    numeric = bool(NUMERIC.search(question))
    if not enabled:
        return Route("single", numeric=numeric, reason="router disabled (ROUTER_ENABLED=false)")
    symbols = find_companies(question, companies)
    periods = find_periods(question, symbols, latest)
    if not symbols and not FINANCE.search(question) and not RISK.search(question):
        return Route("out_of_scope", reason="no covered company and no earnings-call topic")
    if RISK.search(question):
        kind, why = "risk", "risk wording"
    elif len(symbols) >= 2 or COMPARE.search(question):
        kind, why = "comparison", f"{len(symbols)} companies" if len(symbols) >= 2 else "comparison wording"
    else:
        kind, why = "single", "one company" if symbols else "no company named: search all transcripts"
    return Route(kind, symbols, periods, numeric, why)

"""Check every number in a generated answer against the numbers stored for the transcripts.

    verified         the same quantity is in a chunk the answer cites for that sentence
    found_elsewhere  not in the cited chunks, but in another chunk of the same transcript(s)
    derived          recomputable from two numbers in ONE cited chunk (difference, % change, share, pp -> bps);
                     the formula is shown
    unverified       none of the above: treat as possibly wrong

"Same quantity" = same value at the precision the answer states it ("24%" matches 24.0; "$2.4 billion" matches
"$2.4 bn"), with a compatible unit. Two deliberate loosenings for known extraction gaps (D13, D18): a stored number
with no unit matches on value alone, and a dropped direction word ("130 bps" for "down 130 bps") still matches.
"derived" only uses numbers from a single cited chunk, so a made-up number is rarely explained away by a coincidental
calculation across many numbers (D31): when unsure, the checker says unverified.
"""
import re
from dataclasses import dataclass
from itertools import pairwise, permutations

from numcheck.extract import SCALES, extract

CITE = re.compile(r"\[c(\d+)\]")
# A sentence ends at . ! ? followed by space + capital/digit/marker (not after Rs./Mr./Ms./Dr.), or at a newline.
SENTENCE_END = re.compile(r"(?<!\bRs\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bMrs\.)(?<=[.!?])\s+(?=[A-Z“\"(₹$0-9\[*-])|\n")
EPS = 1e-9


@dataclass(frozen=True)
class Source:
    chunk_id: int
    raw: str
    value: float
    unit: str | None
    scale: str | None


@dataclass
class Check:
    raw: str
    value: float
    unit: str | None
    status: str
    start: int
    end: int
    source: Source | None = None
    formula: str | None = None


def _tolerance(n):
    """Half a unit of the last digit the answer states, on the canonical scale."""
    return 0.5 * 10 ** -n.decimals * (SCALES[n.scale] if n.scale else 1.0) + EPS


def _same(n, value, tol):
    return abs(n.value - value) <= tol or abs(abs(n.value) - abs(value)) <= tol


def _matches(n, s):
    unit_ok = s.unit == n.unit or s.unit is None
    return unit_ok and _same(n, s.value, _tolerance(n))


def _derive(n, sources):
    """Try arithmetic on pairs of numbers from one chunk. Returns (source, formula) or None."""
    tol = _tolerance(n)
    for a, b in permutations(sources, 2):
        if a.unit != b.unit:
            continue
        if n.unit == a.unit and _same(n, a.value - b.value, tol):
            return a, f"{a.raw} − {b.raw} = {a.value - b.value:g}"
        if a.unit == "%" and n.unit == "bps" and _same(n, (a.value - b.value) * 100, tol):
            return a, f"({a.raw} − {b.raw}) × 100 = {(a.value - b.value) * 100:g} bps"
        if a.unit == "%" and n.unit == "pp" and _same(n, a.value - b.value, tol):
            return a, f"{a.raw} − {b.raw} = {a.value - b.value:g} pp"
        if a.unit != "%" and b.value and n.unit == "%":
            change = (a.value / b.value - 1) * 100
            if _same(n, change, tol):
                return a, f"({a.raw} ÷ {b.raw} − 1) × 100 = {change:.4g}%"
            share = a.value / b.value * 100
            if _same(n, share, tol):
                return a, f"{a.raw} ÷ {b.raw} × 100 = {share:.4g}%"
    return None


def check_text(text, cited_by_n, chunk_numbers, elsewhere):
    """
    text          answer markdown with [cN] markers
    cited_by_n    {N: chunk_id} for the excerpts the answer could cite
    chunk_numbers {chunk_id: [Source]} for every cited chunk
    elsewhere     [Source] from other chunks of the same documents
    Numbers are checked against the citations in their own sentence; a sentence without markers uses all of them.
    """
    all_cited = list(dict.fromkeys(int(i) for i in CITE.findall(text)))
    out = []
    bounds = [0] + [m.end() for m in SENTENCE_END.finditer(text)] + [len(text)]
    for begin, stop in pairwise(bounds):
        sentence = text[begin:stop]
        ns = [int(i) for i in CITE.findall(sentence)] or all_cited
        chunks = [cited_by_n[i] for i in ns if i in cited_by_n]
        for n in extract(sentence):
            start, end = begin + n.start, begin + n.end
            hit = next((s for c in chunks for s in chunk_numbers.get(c, []) if _matches(n, s)), None)
            if hit:
                out.append(Check(n.raw, n.value, n.unit, "verified", start, end, hit))
                continue
            hit = next((s for s in elsewhere if _matches(n, s)), None)
            if hit:
                out.append(Check(n.raw, n.value, n.unit, "found_elsewhere", start, end, hit))
                continue
            derived = next((d for c in chunks if (d := _derive(n, chunk_numbers.get(c, [])))), None)
            if derived:
                out.append(Check(n.raw, n.value, n.unit, "derived", start, end, derived[0], derived[1]))
                continue
            out.append(Check(n.raw, n.value, n.unit, "unverified", start, end))
    return out


def load_sources(conn, chunk_ids):
    """({chunk_id: [Source]} for the given chunks, [Source] for the other chunks of their documents)."""
    rows = conn.execute("""select n.chunk_id, n.raw, n.value, n.unit, n.scale, n.chunk_id = any(%(ids)s)
                           from chunk_numbers n join chunks c on c.id = n.chunk_id
                           where c.document_id in (select document_id from chunks where id = any(%(ids)s))""",
                        {"ids": list(chunk_ids)}).fetchall()
    cited, elsewhere = {}, []
    for chunk_id, raw, value, unit, scale, is_cited in rows:
        s = Source(chunk_id, raw, value, unit, scale)
        if is_cited:
            cited.setdefault(chunk_id, []).append(s)
        else:
            elsewhere.append(s)
    return cited, elsewhere

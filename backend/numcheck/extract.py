"""Find numbers in text and normalise them to (value, unit, scale).

The same extractor runs on transcript chunks at ingest (stored in quantrag.chunk_numbers) and,
from Phase 5, on generated answers, so both sides are normalised identically.

    value  the number on a canonical scale: "₹72,275 crore" -> 7.2275e11, "24%" -> 24.0, "130 bps" -> 130.0
    unit   "INR" | "USD" | "%" | "bps" | "x" | None (a plain count)
    scale  the scale word as written, normalised: "crore" | "lakh" | "million" | "billion" | "trillion" | None
"""
import re
from dataclasses import dataclass

SCALES = {"crore": 1e7, "lakh": 1e5, "million": 1e6, "billion": 1e9, "trillion": 1e12}
SCALE_WORDS = {"crore": "crore", "crores": "crore", "cr": "crore", "lakh": "lakh", "lakhs": "lakh",
               "million": "million", "mn": "million", "billion": "billion", "bn": "billion", "trillion": "trillion"}
CURRENCY = {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "$": "USD", "us$": "USD", "usd": "USD"}
UNITS = {"%": "%", "per cent": "%", "percent": "%", "bps": "bps", "basis points": "bps", "basis point": "bps",
         "x": "x", "times": "x"}
NEGATIVE_CUES = re.compile(r"\b(?:decline[sd]?|declining|down|fell|fall(?:ing|s)?|drop(?:ped|s)?|decrease[sd]?|"
                           r"contraction|contracted|lower by|negative)\b(?:\s+\w+){0,2}\s*$", re.IGNORECASE)
MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"

NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"
PATTERN = re.compile(
    rf"(?:(?P<cur>₹|(?<![A-Za-z])(?:Rs\.?|INR|US\$|USD)|\$)\s?)?"
    rf"(?P<neg>[-−–](?=\d))?(?P<a>{NUM})"
    rf"(?:\s*(?:-|–|—|to)\s*(?P<b>{NUM}))?"
    rf"(?:\s?(?P<scale>crores?|cr|lakhs?|million|mn|billion|bn|trillion)\b)?"
    rf"(?:\s?(?P<unit>%|per cent|percent|bps|basis points?|x\b|times\b))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Number:
    raw: str
    value: float
    unit: str | None
    scale: str | None
    start: int
    end: int


def _skip(text, m):
    """Years, fiscal labels (Q1, FY27, 2H), dates and ordinals are not financial figures."""
    a, before, after = m["a"], text[max(0, m.start() - 12):m.start()], text[m.end():m.end() + 3]
    if m["cur"] or m["scale"] or m["unit"]:
        return False
    if re.search(r"(?:\bQ|\bFY\s?'?|\bH|\bCY\s?'?)$", before, re.IGNORECASE) or re.match(r"[HQ]\b", after):
        return True  # Q1, FY27, FY '25, 2H, H1
    if re.fullmatch(r"(?:19|20)\d{2}", a):
        return True  # a year
    if before.endswith(":") and before[-2:-1].isdigit() or re.match(r":\d", after):
        return True  # a time: 5:00 PM
    if re.match(r"[A-Za-z]", after) or re.search(r"['’/]$", before):
        return True  # inside a name or shorthand: S/4HANA, full year '27
    if re.match(r"-[A-Za-z]", after):
        return True  # compound adjective: 360-degree, 5-year
    if re.search(r"\b(?:Fortune|Global|Nifty|Sensex|Forbes)\s*$", before):
        return True  # index or list name: Fortune 50, Nifty 50
    if not m["b"] and re.fullmatch(r"\d{1,2}", a) and re.match(r"\.(?:\s+[A-Z]|\s*$)", text[m.end():]):
        return True  # list marker: "...growth. 6. Overall pipeline..."
    if re.search(rf"\b{MONTHS}\s*$", before, re.IGNORECASE) or re.match(rf"\s*(?:st|nd|rd|th)?,?\s*{MONTHS}", text[m.end():], re.IGNORECASE):
        return True  # July 18 / 18th July
    return bool(re.match(r"(?:st|nd|rd|th)\b", after, re.IGNORECASE))  # 6th


def extract(text: str) -> list[Number]:
    out = []
    for m in PATTERN.finditer(text):
        if not m["a"] or (m.start() > 0 and (text[m.start() - 1].isalnum() or text[m.start() - 1] in "._")):
            continue  # part of a word or identifier, e.g. "Q1", "v1.5", "COVID19"
        if _skip(text, m):
            continue
        cur = CURRENCY[m["cur"].lower()] if m["cur"] else None
        unit = cur or (UNITS[m["unit"].lower()] if m["unit"] else None)
        scale = SCALE_WORDS[m["scale"].lower()] if m["scale"] else None
        mult = SCALES[scale] if scale else 1.0
        sign = -1 if m["neg"] or NEGATIVE_CUES.search(text[max(0, m.start() - 40):m.start()]) else 1
        raw = m.group(0).strip()
        for g in ("a", "b"):
            if m[g]:
                out.append(Number(raw, sign * float(m[g].replace(",", "")) * mult, unit, scale, m.start(), m.end()))
    return out

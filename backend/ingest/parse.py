"""Transcript PDF -> speaker turns, each tagged with role and section.

    pdf_pages -> strip_headers -> segment -> drop_boilerplate

Handles both speaker styles seen in Indian transcripts: "Name: text" on one line (TCS, HDFC Bank, HUL)
and the name alone on its own line (Infosys).
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import pdfplumber
import pypdf

TITLE = r"(?:(?:Mr|Ms|Mrs|Dr)\.?\s+)?"
NAME = r"[A-Z][A-Za-z.'’-]*(?:\s+[A-Z][A-Za-z.'’-]*){0,4}"
COLON_LINE = re.compile(rf"^{TITLE}({NAME})\s*:\s*(.*)$")
# The moderator introduces each analyst: "...question is from the line of Gaurav Rateria from Morgan Stanley."
INTRO = re.compile(rf"(?:line of|question (?:is |comes )?from)\s+{TITLE}({NAME}?)\s+(?:from|with|of)\b")
QA_START = re.compile(r"question[- ]and[- ]answer|first question", re.IGNORECASE)
NOT_SPEAKERS = {"disclaimer", "note", "speakers", "management", "corporate participants", "participants",
                "analysts", "moderator note"}
SAFE_HARBOUR = re.compile(r"forward[- ]looking|safe harbou?r|risks and uncertainties|sec\.gov", re.IGNORECASE)
PAGE_NO = re.compile(r"^page \d+ of \d+$", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<!\bMr\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bMrs\.)(?<!\bRs\.)(?<=[.!?])\s+(?=[A-Z“\"(₹$0-9])")


@dataclass
class Turn:
    speaker: str
    role: str = "unknown"      # management | analyst | moderator | unknown
    section: str = "unknown"   # prepared | qa | unknown
    page: int = 0              # page the turn starts on (1-based)
    text: str = ""
    pages: list[tuple[int, int]] = field(default_factory=list)  # (char offset in text, page) where each page starts

    def page_at(self, offset):
        return max((p for o, p in self.pages if o <= offset), default=self.page)


def pdf_pages(path):
    """Text per page: pdfplumber, falling back to pypdf for pages with (cid:N) glyph codes (seen in TCS PDFs)."""
    reader, out = None, []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "(cid:" in text or not text.strip():
                reader = reader or pypdf.PdfReader(path)
                text = reader.pages[i].extract_text() or ""
            # NFKC turns ligatures into letters ("ﬁnancial" -> "financial") so keyword search matches.
            # ponytail: pypdf maps the "ff" ligature in TCS's font to "Ư"; a per-glyph fix, extend if new fonts break
            out.append(unicodedata.normalize("NFKC", text).replace("Ư", "ff"))
    return out


def _norm(line):
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_headers(pages, edge=3, share=0.5):
    """[(page, line)] without page numbers and running headers/footers (lines repeated at page edges)."""
    split = [[ln.strip() for ln in p.splitlines() if ln.strip()] for p in pages]
    counts = Counter(k for lines in split for k in {_norm(ln) for ln in lines[:edge] + lines[-edge:]})
    repeated = {k for k, n in counts.items() if len(pages) >= 3 and n >= share * len(pages)}
    out = []
    for page, lines in enumerate(split, start=1):
        for j, ln in enumerate(lines):
            at_edge = j < edge or j >= len(lines) - edge
            if not PAGE_NO.match(ln) and not (at_edge and _norm(ln) in repeated):
                out.append((page, ln))
    return out


def _key(name):
    return re.sub(r"\s+", " ", re.sub(rf"^{TITLE}", "", name.strip())).casefold()


def _colon_speaker(line, extra_names):
    m = COLON_LINE.match(line)
    if not m:
        return None
    name = m[1].strip()
    if name.casefold() in NOT_SPEAKERS:
        return name, m[2]  # a labelled non-speaker block (e.g. "Disclaimer:"), dropped later
    if name.isupper() or not (name == "Moderator" or len(name.split()) >= 2 or _key(name) in extra_names):
        return None
    return name, m[2]


def segment(lines):
    """[(page, line)] -> [Turn] with speaker, role and section. Lines before the first speaker are the cover."""
    flat = " ".join(ln for _, ln in lines)
    analysts = {_key(n) for n in INTRO.findall(flat)}
    colon_names = {_key(m[1]) for _, ln in lines if (m := COLON_LINE.match(ln))}
    def is_speaker(ln):
        hit = _colon_speaker(ln, analysts)
        return (hit and hit[0].casefold() not in NOT_SPEAKERS) or ln.strip() == "Moderator"
    cover_end = next((i for i, (_, ln) in enumerate(lines) if is_speaker(ln)), len(lines))
    cover = [re.split(r"\s[–-]\s", re.sub(rf"^{TITLE}", "", ln, flags=re.IGNORECASE))[0] for _, ln in lines[:cover_end]]
    cover_names = {_key(c) for c in cover}
    standalone = {"moderator"} | analysts | colon_names | cover_names

    turns = []
    for page, ln in lines[cover_end:]:
        hit = _colon_speaker(ln, analysts)
        if not hit and _key(ln) in standalone and len(ln.split()) <= 5:
            hit = (ln.strip(), "")
        if hit:
            turns.append(Turn(speaker=hit[0], page=page, pages=[(0, page)]))
            ln = hit[1]
        if not turns or not ln:
            continue
        t = turns[-1]
        if t.pages[-1][1] != page:
            t.pages.append((len(t.text) + 1, page))
        if t.text.endswith("-") and ln[:1].islower():
            t.text = t.text[:-1] + ln  # re-join a word hyphenated across lines
        else:
            t.text = f"{t.text} {ln}" if t.text else ln

    cover_text = " ".join(cover).casefold()
    qa_start = next((i for i, t in enumerate(turns) if t.speaker == "Moderator" and QA_START.search(t.text)), None)
    # management = named on the cover, or speaks before Q&A opens (TCS has no participant list)
    prepared = {_key(t.speaker) for t in turns[:qa_start or 0]}
    for i, t in enumerate(turns):
        t.text = re.sub(r"[-]", "•", t.text)  # private-use bullet glyphs
        t.section = "unknown" if qa_start is None else ("qa" if i >= qa_start else "prepared")
        k = _key(t.speaker)
        if t.speaker == "Moderator":
            t.role = "moderator"
        elif k in analysts:
            t.role = "analyst"
        elif k in cover_text or k in prepared:
            t.role = "management"
    return turns


def drop_boilerplate(turns, min_words=5):
    """Remove operator turns, labelled disclaimers/notes, safe-harbour sentences and near-empty turns."""
    out = []
    for t in turns:
        if t.role == "moderator" or t.speaker.casefold() in NOT_SPEAKERS:
            continue
        sentences = SENTENCE_END.split(t.text)
        if any(SAFE_HARBOUR.search(s) for s in sentences):
            kept = [s for s in sentences if not SAFE_HARBOUR.search(s)]
            t.text = " ".join(kept)  # ponytail: page offsets drift slightly after removal; off by at most a page
        if len(t.text.split()) >= min_words:
            out.append(t)
    return out


def parse_transcript(path):
    return drop_boilerplate(segment(strip_headers(pdf_pages(path))))

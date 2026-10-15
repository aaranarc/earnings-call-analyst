"""Speaker turns -> chunks. A chunk never mixes speakers: each turn is one chunk, or, if it is longer than
max_tokens, several chunks split at sentence boundaries with a 1-sentence overlap.
"""
import re
from dataclasses import dataclass

SENTENCE = re.compile(r".+?(?:(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bMrs)[.!?](?=\s+[A-Z“\"(₹$0-9])|$)", re.DOTALL)
MAX_TOKENS = 450  # bge-small truncates at 512; leaves room for the context header added at embed time


@dataclass
class Chunk:
    speaker: str
    role: str
    section: str
    page: int
    text: str
    tokens: int


def _sentences(text):
    """[(start offset, sentence)]"""
    out = []
    for m in SENTENCE.finditer(text):
        s = m.group(0)
        if s.strip():
            out.append((m.start() + len(s) - len(s.lstrip()), s.strip()))  # offset of the first character
    return out


def chunk_turns(turns, count_tokens, max_tokens=MAX_TOKENS):
    out = []
    for t in turns:
        n = count_tokens(t.text)
        if n <= max_tokens:
            out.append(Chunk(t.speaker, t.role, t.section, t.page, t.text, n))
            continue
        sents = _sentences(t.text)
        # a single sentence over the limit (rare: run-on transcription) is cut into word windows
        sents = [piece for off, s in sents for piece in _hard_split(off, s, count_tokens, max_tokens)]
        i = 0
        while i < len(sents):
            j, size = i, 0
            while j < len(sents) and (j == i or size + count_tokens(sents[j][1]) <= max_tokens):
                size += count_tokens(sents[j][1])
                j += 1
            text = " ".join(s for _, s in sents[i:j])
            out.append(Chunk(t.speaker, t.role, t.section, t.page_at(sents[i][0]), text, count_tokens(text)))
            overlap = j - 1 > i and j < len(sents) and \
                count_tokens(sents[j - 1][1]) + count_tokens(sents[j][1]) <= max_tokens
            i = j - 1 if overlap else j  # repeat the last sentence once as overlap, when it fits
    return out


def _hard_split(offset, sentence, count_tokens, max_tokens):
    if count_tokens(sentence) <= max_tokens:
        return [(offset, sentence)]
    words, out, cur = sentence.split(), [], []
    for w in words:
        if cur and count_tokens(" ".join(cur + [w])) > max_tokens:
            out.append((offset, " ".join(cur)))
            cur = []
        cur.append(w)
    return out + [(offset, " ".join(cur))]

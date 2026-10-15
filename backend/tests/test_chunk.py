from ingest.chunk import chunk_turns
from ingest.parse import Turn


def words(text):
    return len(text.split())


def turn(speaker, text, pages=None):
    return Turn(speaker=speaker, role="management", section="qa", page=1, text=text, pages=pages or [(0, 1)])


def test_short_turns_are_one_chunk_each_and_never_merge_speakers():
    chunks = chunk_turns([turn("A", "One two three."), turn("B", "Four five six.")], words, max_tokens=50)
    assert [(c.speaker, c.text) for c in chunks] == [("A", "One two three."), ("B", "Four five six.")]


def test_long_turn_splits_at_sentences_with_one_sentence_overlap():
    text = " ".join(f"Sentence number {i} has five." for i in range(1, 7))  # 6 sentences x 5 words
    chunks = chunk_turns([turn("A", text)], words, max_tokens=12)
    assert all(c.speaker == "A" and c.tokens <= 12 for c in chunks)
    assert [c.text for c in chunks] == [
        "Sentence number 1 has five. Sentence number 2 has five.",
        "Sentence number 2 has five. Sentence number 3 has five.",
        "Sentence number 3 has five. Sentence number 4 has five.",
        "Sentence number 4 has five. Sentence number 5 has five.",
        "Sentence number 5 has five. Sentence number 6 has five.",
    ]


def test_every_sentence_is_kept():
    text = " ".join(f"Point {i} is made here clearly." for i in range(20))
    chunks = chunk_turns([turn("A", text)], words, max_tokens=20)
    joined = " ".join(c.text for c in chunks)
    assert all(f"Point {i} is" in joined for i in range(20))


def test_sentence_longer_than_limit_is_cut_into_word_windows():
    chunks = chunk_turns([turn("A", " ".join(["word"] * 25))], words, max_tokens=10)
    assert [c.tokens for c in chunks] == [10, 10, 5]


def test_split_chunk_takes_the_page_where_it_starts():
    first = "This sentence is on page one."
    t = turn("A", f"{first} This one starts page two.", pages=[(0, 1), (len(first) + 1, 2)])
    chunks = chunk_turns([t], words, max_tokens=6)
    assert [c.page for c in chunks] == [1, 2]


def test_mr_and_ms_do_not_end_sentences():
    chunks = chunk_turns([turn("A", "We thank Mr. Rao and Ms. Iyer today. Next point here.")], words, max_tokens=8)
    assert chunks[0].text == "We thank Mr. Rao and Ms. Iyer today."

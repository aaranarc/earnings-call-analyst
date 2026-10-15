from pathlib import Path

import pytest

from ingest.parse import drop_boilerplate, parse_transcript, segment, strip_headers

RAW = Path(__file__).resolve().parents[2] / "data/raw"


def lines(*pages):
    return [(i, ln) for i, page in enumerate(pages, start=1) for ln in page.strip().splitlines()]


COLON_STYLE = lines("""
Acme Limited Q1 FY27 Earnings Call
MANAGEMENT: MR. ASHA RAO – CHIEF FINANCIAL OFFICER – ACME LIMITED
Moderator: Ladies and gentlemen, welcome. Please note this conference is being recorded.
Asha Rao: Thank you. Revenue grew 12% this quarter and margins expanded by 40 bps. Statements about the
future are forward-looking statements subject to risk. Our deal pipeline is strong.
Moderator: We will now begin the question-and-answer session. The first question is from the line of
Vikram Shah from Alpha Capital. Please go ahead.
""", """
Vikram Shah: Thanks. What is the margin outlook for the full year and the second half?
Asha Rao: We expect margins in the 20-22% band. Second: hiring will moder-
ate in the coming quarters.
Disclaimer: This transcript has been edited for readability and accuracy purposes.
""")

STANDALONE_STYLE = lines("""
Beta Limited
CORPORATE PARTICIPANTS:
Ravi Iyer
Chief Executive Officer
ANALYSTS
Neha Gupta
Kappa Securities
Moderator
Welcome to the Beta Limited earnings call. I now hand over to Ravi.
Ravi Iyer
Good evening. We grew revenue by 8% in constant currency and signed large deals.
Moderator
We will now begin the question-and-answer session. The first question is from the line of Neha Gupta
from Kappa Securities.
Neha Gupta
How should we think about pricing in the coming quarters for your clients?
Ravi Iyer
Pricing is stable and we see no pressure on renewals so far this year.
""")


def by_speaker(turns):
    return [(t.speaker, t.role, t.section) for t in turns]


def test_colon_style_speakers_roles_and_sections():
    turns = segment(COLON_STYLE)
    assert by_speaker(turns) == [
        ("Moderator", "moderator", "prepared"),
        ("Asha Rao", "management", "prepared"),
        ("Moderator", "moderator", "qa"),
        ("Vikram Shah", "analyst", "qa"),
        ("Asha Rao", "management", "qa"),
        ("Disclaimer", "unknown", "qa"),
    ]


def test_standalone_name_style_uses_cover_and_moderator_intro():
    turns = drop_boilerplate(segment(STANDALONE_STYLE))
    assert by_speaker(turns) == [
        ("Ravi Iyer", "management", "prepared"),
        ("Neha Gupta", "analyst", "qa"),
        ("Ravi Iyer", "management", "qa"),
    ]


def test_cover_headings_are_not_speakers():
    names = {t.speaker for t in segment(COLON_STYLE)}
    assert "MANAGEMENT" not in names
    assert "Second" not in names  # "Second:" inside a turn is not a one-word speaker label


def test_boilerplate_dropped_and_hyphenation_rejoined():
    turns = drop_boilerplate(segment(COLON_STYLE))
    text = " ".join(t.text for t in turns)
    assert {t.role for t in turns} == {"management", "analyst"}  # moderator turns gone
    assert "forward-looking" not in text and "Disclaimer" not in text
    assert "Our deal pipeline is strong." in text  # the rest of the turn survives
    assert "moderate in the coming quarters" in text


def test_turn_pages_track_where_text_starts():
    turns = segment(COLON_STYLE)
    asha_qa = turns[4]
    assert asha_qa.page == 2
    assert asha_qa.page_at(len(asha_qa.text) - 1) == 2


def test_running_headers_and_page_numbers_removed():
    body = ["Revenue grew in the quarter.", "Margins were stable overall.", "Deal wins were strong.",
            "Hiring stayed muted.", "Pricing held up well.", "Attrition kept falling.", "Cash flow improved again."]
    seg = ["alpha", "beta", "gamma", "delta"]  # real pages differ in words, not just digits
    pages = ["\n".join(["Acme Limited", "July 18, 2026", *[f"{s} ({seg[p]})" for s in body], f"Page {p + 1} of 4"])
             for p in range(4)]
    kept = [ln for _, ln in strip_headers(pages)]
    assert kept == [f"{s} ({seg[p]})" for p in range(4) for s in body]


EXPECTED = {
    "TCS_Q1FY27": {"Nehal Shah", "K Krithivasan", "Aarthi Subramanian", "Samir Seksaria", "Sudeep Kunnumal"},
    "HDFCBANK_Q1FY27": {"Srinivasan Vaidyanathan", "Sashidhar Jagdishan", "Kaizad Bharucha"},
    "HINDUNILVR_Q1FY27": {"Priya Nair", "Niranjan Gupta", "Yogesh Mulgaonkar"},
    "INFY_Q2FY25": {"Salil Parekh", "Jayesh Sanghrajka", "Sandeep Mahindroo"},
}


@pytest.mark.parametrize("name, management", EXPECTED.items())
def test_real_transcript(name, management):
    pdf = RAW / f"{name}.pdf"
    if not pdf.exists():
        pytest.skip(f"{pdf.name} not downloaded (data/raw is git-ignored)")
    turns = parse_transcript(pdf)
    assert {t.speaker for t in turns if t.role == "management"} == management
    assert {t.role for t in turns} == {"management", "analyst"}  # no moderator, no unknown
    assert len({t.speaker for t in turns if t.role == "analyst"}) >= 5
    sections = [t.section for t in turns]
    assert sections[0] == "prepared" and sections[-1] == "qa" and sorted(sections) == sections  # prepared, then qa
    text = " ".join(t.text for t in turns)
    assert not any(bad in text for bad in ("(cid:", "Ư", "ﬁ", "forward-looking", "Page 2 of"))

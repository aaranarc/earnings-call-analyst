"""Number checker: statuses, precision, units, signs, derivations. Pure functions, no DB."""
import pytest

from numcheck.match import Source, check_text

C1 = [Source(1, "24%", 24.0, "%", None), Source(1, "130 bps", -130.0, "bps", None),
      Source(1, "₹72,275 crore", 7.2275e11, "INR", "crore"), Source(1, "$2.4 bn", 2.4e9, "USD", "billion"),
      Source(1, "25.3%", 25.3, "%", None), Source(1, "40", 40.0, None, None)]
C2 = [Source(2, "INR17,184 crores", 1.7184e11, "INR", "crore"), Source(2, "INR15,000 crores", 1.5e11, "INR", "crore"),
      Source(2, "10%", 10.0, "%", None)]
ELSEWHERE = [Source(9, "93%", 93.0, "%", None)]
CITED = {1: 1, 2: 2}
NUMS = {1: C1, 2: C2}


def statuses(text):
    return [(c.raw, c.status) for c in check_text(text, CITED, NUMS, ELSEWHERE)]


@pytest.mark.parametrize("text, expected", [
    ("Operating margin was 24% [c1].", [("24%", "verified")]),
    ("Operating margin was 24.0% [c1].", [("24.0%", "verified")]),
    ("Revenue was ₹72,275 crores [c1].", [("₹72,275 crores", "verified")]),
    ("Revenue was Rs. 72,275 cr [c1].", [("Rs. 72,275 cr", "verified")]),
    ("TCV was $2.4 billion [c1].", [("$2.4 billion", "verified")]),        # bn vs billion
    ("TCV was $2,400 million [c1].", [("$2,400 million", "verified")]),    # same value, different scale word
    ("Margin fell 130 bps [c1].", [("130 bps", "verified")]),              # direction on both sides
    ("Margin moved 130 bps [c1].", [("130 bps", "verified")]),             # direction word dropped
    ("Margin was down 1.3 percentage points to 24% [c1].", [("1.3 percentage points", "derived"), ("24%", "verified")]),
    ("About 40 basis points of change [c1].", [("40 basis points", "verified")]),  # stored number lost its unit
])
def test_verified(text, expected):
    assert statuses(text) == expected


def test_stated_precision_is_respected():
    assert statuses("Margin was about 25% [c1].") == [("25%", "verified")]     # 25.3 rounds to 25 (brief's rule)
    assert statuses("Margin was about 26% [c1].") == [("26%", "unverified")]
    assert statuses("Margin was 25.3% [c1].") == [("25.3%", "verified")]
    assert statuses("Margin was 25.30% [c1].") == [("25.30%", "verified")]
    assert statuses("Margin was 25.35% [c1].") == [("25.35%", "unverified")]  # more precise than the source


def test_unit_must_match():
    assert statuses("It was 24 bps [c1].") == [("24 bps", "unverified")]       # 24% is not 24 bps
    assert statuses("Revenue was $72,275 crore [c1].")[0][1] == "unverified"  # USD vs INR


def test_number_checked_against_its_own_sentence_citations():
    assert statuses("Turnover was INR17,184 crores [c2]. Margin was 24% [c2].") == [
        ("INR17,184 crores", "verified"), ("24%", "unverified")]               # 24% is in c1, not c2


def test_sentence_without_marker_uses_all_citations():
    assert statuses("Margin was 24%.\nBoth figures are from the call [c1][c2].")[0] == ("24%", "verified")


def test_found_elsewhere_in_same_document():
    assert statuses("Cash conversion was 93% [c1].") == [("93%", "found_elsewhere")]


def test_derived_difference_in_bps_with_formula():
    (c,) = check_text("Margin narrowed by 130 bps [c1].", CITED,
                      {1: [Source(1, "25.3%", 25.3, "%", None), Source(1, "24%", 24.0, "%", None)]}, [])
    assert (c.status, c.formula) == ("derived", "(25.3% − 24%) × 100 = 130 bps")


def test_derived_growth_percent():
    (c,) = check_text("Turnover grew 14.56% [c2].", CITED, NUMS, [])
    assert c.status == "derived" and "INR17,184 crores ÷ INR15,000 crores − 1" in c.formula


def test_derived_needs_both_numbers_in_one_chunk():
    split = {1: [Source(1, "a", 1.7184e11, "INR", "crore")], 2: [Source(2, "b", 1.5e11, "INR", "crore")]}
    (c,) = check_text("Turnover grew 14.56% [c1][c2].", CITED, split, [])
    assert c.status == "unverified"


def test_made_up_number_is_unverified():
    assert statuses("Net profit was ₹12,345 crore [c1][c2].") == [("₹12,345 crore", "unverified")]


def test_range_checks_both_ends():
    nums = {1: [Source(1, "20%", 20.0, "%", None), Source(1, "22%", 22.0, "%", None)]}
    assert [c.status for c in check_text("Guidance is 20–22% [c1].", CITED, nums, [])] == ["verified", "verified"]
    assert [c.status for c in check_text("Guidance is 20–23% [c1].", CITED, nums, [])] == ["verified", "unverified"]


def test_citation_markers_and_labels_are_not_numbers():
    assert statuses("In Q1 FY27 the margin was 24% [c1][c2].") == [("24%", "verified")]


def test_offsets_point_into_the_answer():
    text = "Revenue was ₹72,275 crore and margin 24% [c1]."
    for c in check_text(text, CITED, NUMS, []):
        assert text[c.start:c.end].strip() == c.raw

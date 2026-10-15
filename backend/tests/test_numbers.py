import pytest

from numcheck.extract import extract


def one(text):
    nums = extract(text)
    assert len(nums) == 1, nums
    n = nums[0]
    return n.value, n.unit, n.scale


@pytest.mark.parametrize("text, expected", [
    # currency + Indian scale words
    ("Our Q1 revenue stood at ₹72,275 crore, growing", (7.2275e11, "INR", "crore")),
    ("Turnover for the quarter stood at INR17,184 crores", (1.7184e11, "INR", "crore")),
    ("revenue of Rs. 1,200 cr this quarter", (1.2e10, "INR", "crore")),
    ("Rs 45 lakh in fees", (4.5e6, "INR", "lakh")),
    ("an Indian-grouped 1,23,456 crore book", (1.23456e12, None, "crore")),
    # dollars + Western scale words
    ("We delivered a TCV of $9.5 billion, including", (9.5e9, "USD", "billion")),
    ("US$ 800 million mega deal with SKF", (8e8, "USD", "million")),
    ("crossed US$2.6 billion.", (2.6e9, "USD", "billion")),
    ("deal value of USD 1.5 bn", (1.5e9, "USD", "billion")),
    ("a 123,456 strong workforce", (123456.0, None, None)),
    ("$10 million+ revenue band", (1e7, "USD", "million")),
    ("about 50 mn subscribers", (5e7, None, "million")),
    # percentages and basis points
    ("operating margins stood at 24%, down", (24.0, "%", None)),
    ("growing 2.2% sequentially", (2.2, "%", None)),
    ("margin of 21.5 per cent", (21.5, "%", None)),
    ("grew 7 percent", (7.0, "%", None)),
    ("an improvement of 40 bps", (40.0, "bps", None)),
    ("expansion of 25 basis points", (25.0, "bps", None)),
    # negatives
    ("EBIT margin was -1.2% this quarter", (-1.2, "%", None)),
    ("a decline of 1.2% in volumes", (-1.2, "%", None)),
    ("operating margins were down 130 bps sequentially", (-130.0, "bps", None)),
    ("attrition fell to 12.3%", (-12.3, "%", None)),
    # multiples
    ("trading at 3.5x book", (3.5, "x", None)),
    ("pipeline is 2 times last year", (2.0, "x", None)),
    # plain counts survive
    ("50,000 licenses for the team", (50000.0, None, None)),
])
def test_single_number(text, expected):
    value, unit, scale = one(text)
    assert value == pytest.approx(expected[0])
    assert (unit, scale) == expected[1:]


@pytest.mark.parametrize("text, values, unit", [
    ("guidance of 20–22% for the year", [20.0, 22.0], "%"),
    ("margin band of 26-28%", [26.0, 28.0], "%"),
    ("growth of 4.5 to 5% in constant currency", [4.5, 5.0], "%"),
    ("deals worth $1-2 billion", [1e9, 2e9], "USD"),
])
def test_range_gives_two_numbers_with_shared_unit(text, values, unit):
    nums = extract(text)
    assert [n.value for n in nums] == pytest.approx(values)
    assert {n.unit for n in nums} == {unit}
    assert len({n.raw for n in nums}) == 1  # both come from the same mention


@pytest.mark.parametrize("text", [
    "results for Q1 FY27 and FY2027",
    "the call on July 18, 2026",
    "held on 9th July",
    "our 6th mega deal in a row",
    "in 2H of the year and H1",
    "Q2 FY '25 Earnings Conference Call",
    "COVID19 and model v1.5",
    # found in the Phase 2 spot-check (PROGRESS.md)
    "deepening 360-degree partnership with clients",
    "a deal with a Global Fortune 50 European firm",
    "volume growth. 6. Overall deal pipeline remains strong.",
    "We will look to end the call by 5:00 PM.",
    "S/4HANA transformation is a big part of this deal",
    "full year '27 will be ahead of full year ’26",
])
def test_labels_dates_years_and_ordinals_are_ignored(text):
    assert extract(text) == []


def test_offsets_point_at_the_mention():
    text = "revenue was ₹72,275 crore and margin 24%"
    for n in extract(text):
        assert text[n.start:n.end].strip() == n.raw


def test_several_numbers_in_one_sentence():
    nums = extract("TCV of $9.5 billion, revenue ₹72,275 crore, margin 24%, up 130 bps")
    assert [(n.unit, n.scale) for n in nums] == [("USD", "billion"), ("INR", "crore"), ("%", None), ("bps", None)]


def test_spot_check_fixes_keep_real_figures():
    assert [n.value for n in extract("a 5-year CAGR of 12% and the top 10 clients")] == [12.0, 10.0]
    assert [n.value for n in extract("revenue grew 6.5% in Q2. 6 new logos were added.")] == [6.5, 6.0]

from quantrag.ask import with_badges


def test_badges_inserted_after_each_answer_number():
    text = "Revenue rose 5% to ₹100 crore."
    nums = [{"where": "answer", "end": 15, "status": "verified"},
            {"where": "answer", "end": 29, "status": "unverified"},
            {"where": "table:0:0", "end": 3, "status": "derived"}]
    assert with_badges(text, nums) == "Revenue rose 5% ✅ to ₹100 crore 🔴."

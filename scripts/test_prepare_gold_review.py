from collections import Counter

import pytest
from prepare_gold_review import make_draft


def test_draft_is_balanced_and_never_claims_human_review():
    records = []
    for quarter in range(1, 5):
        for company in range(9):
            records.append({"symbol": f"C{company}", "name": f"Company {company}", "sector": "it_services",
                            "topic": "operating margin", "period": f"Q{quarter} FY26",
                            "ordinal": 26 * 4 + quarter, "period_end": f"2025-{quarter:02d}-30",
                            "text": "Operating margin was 20% this quarter.", "speaker": "A Person",
                            "role": "management", "page": 3, "source_url": "https://www.tcs.com/a.pdf",
                            "sha256": "a" * 64, "chunk_id": len(records) + 1})
    items, notes = make_draft(records)
    assert len(items) == len({r["question"] for r in items}) == 60
    assert all(r["human_verified"] is False and r["reviewed_by"] == "" for r in items)
    assert Counter(n["category"] for n in notes) == {"single": 30, "comparison": 15, "trend": 10, "refusal": 5}
    assert all(len(item["evidence"]) == 2 for item, note in zip(items, notes, strict=True)
               if note["category"] in {"comparison", "trend"})
    assert sum(not r["answerable"] for r in items) == 5


def test_insufficient_evidence_cannot_produce_full_packet():
    with pytest.raises(ValueError, match="Insufficient"):
        make_draft([])

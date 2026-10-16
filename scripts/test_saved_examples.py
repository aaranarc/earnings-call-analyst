import copy
import json

import pytest
from save_example_answers import OUTPUT, validate


def test_saved_examples_have_real_manifest_provenance():
    validate(json.loads(OUTPUT.read_text()))


@pytest.mark.parametrize('field', ['saved_at', 'sha256', 'answer_markdown'])
def test_examples_reject_missing_date_or_source_or_citation(field):
    rows = copy.deepcopy(json.loads(OUTPUT.read_text()))
    if field == 'sha256':
        rows[0]['sources'][0][field] = 'x' * 64
    else:
        rows[0][field] = ''
    with pytest.raises(ValueError):
        validate(rows)

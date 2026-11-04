import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ui.client import AnalystError, ask
from ui.research import note, project_payoff, read_notes

ROOT = Path(__file__).resolve().parents[2]


def app():
    return AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=15).run()


@pytest.mark.parametrize('page', ['Home', 'Ask the analyst', 'QuarterLens', 'Growth Payoff',
                                  'Saved research', 'Evaluation', 'How it works'])
def test_all_pages_render_without_api(page):
    test = app()
    test.sidebar.radio[0].set_value(page).run()
    assert not test.exception


def test_note_save_export_validation_delete():
    test = app()
    test.sidebar.radio[0].set_value('Saved research').run()
    assert test.session_state['notes'] == []
    test.text_input[0].set_value('TCS margins')
    next(a for a in test.text_area if a.label == 'Your note').set_value('Check wage impact against the original source.')
    next(b for b in test.button if b.label == 'Add note').click().run()
    assert test.session_state['notes'][0]['title'] == 'TCS margins'
    assert not test.exception
    next(b for b in test.button if b.label == 'Delete note').click().run()
    assert test.session_state['notes'] == []


def test_roundtrip_and_reject_malformed_import():
    rows = [note('Question', 'Evidence', [{'source_url': 'https://example.com/report.pdf'}])]
    assert read_notes(json.dumps(rows)) == rows
    for content in ['{}', '[{}]', json.dumps(rows + rows), 'x' * 2_000_001]:
        with pytest.raises(ValueError):
            read_notes(content)


def test_scenario_ramp_and_negative_return():
    data = project_payoff(100, 10, 2, 1, 5)
    assert [r['Annual incremental operating profit (₹ crore)'] for r in data] == [0, 5, 10, 10, 10, 10]
    assert project_payoff(100, -10, 1, 2, 3)[2]['Annual incremental operating profit (₹ crore)'] == -10
    with pytest.raises(ValueError):
        project_payoff(float('nan'), 10, 2, 1, 5)


def test_client_stream_and_server_token(monkeypatch):
    monkeypatch.setenv('API_ACCESS_TOKEN', 'server-secret')
    statuses = []
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer server-secret'
        assert json.loads(request.content)['question'] == 'What margin?'
        return httpx.Response(200, text='event: status\ndata: "Retrieving"\n\n'
                              'event: answer\ndata: {"answer_markdown":"Sourced answer", "refused": false}\n\n')
    result = ask('What margin?', statuses.append, httpx.MockTransport(handler))
    assert result['answer_markdown'] == 'Sourced answer'
    assert statuses == ['Retrieving']


@pytest.mark.parametrize('status', [401, 422, 429, 503])
def test_client_http_errors_are_redacted(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text='secret database password'))
    with pytest.raises(AnalystError) as err:
        ask('What margin?', transport=transport)
    assert 'password' not in str(err.value)


@pytest.mark.parametrize('body', ['event: error\ndata: "secret provider response"\n\n',
                                 'event: answer\ndata: invalid json\n\n', ''])
def test_client_rejects_error_malformed_and_truncated_stream(body):
    with pytest.raises(AnalystError):
        ask('What margin?', transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)))


def test_failed_ask_shows_dated_examples():
    test = app()
    test.sidebar.radio[0].set_value('Ask the analyst').run()
    test.text_area[0].set_value('What margin?')
    with patch('ui.client.ask', side_effect=AnalystError('Please retry.')):
        next(b for b in test.button if b.label == 'Ask the analyst').click().run()
    assert not test.exception
    assert any('Example answer, saved' in e.label for e in test.expander)
    assert test.error[0].value == 'Please retry.'


def test_successful_ask_renders_and_saves():
    test = app()
    test.sidebar.radio[0].set_value('Ask the analyst').run()
    test.text_area[0].set_value('What margin?')
    result = {'answer_markdown': 'Margin is 24% [c1].', 'refused': False, 'hits': [
        {'chunk_id': 1, 'symbol': 'TCS', 'fiscal_label': 'Q1 FY27', 'text': 'Margin was 24%.',
         'speaker': 'CFO', 'page': 1, 'source_url': 'https://example.com/source.pdf', 'scores': {}}],
        'citations': [{'n': 1, 'chunk_id': 1, 'symbol': 'TCS', 'fiscal_label': 'Q1 FY27'}],
        'numbers': [{'raw': '24%', 'status': 'verified'}]}
    with patch('ui.client.ask', return_value=result):
        next(b for b in test.button if b.label == 'Ask the analyst').click().run()
    assert not test.exception
    next(b for b in test.button if b.label == 'Save answer').click().run()
    assert test.session_state['notes'][0]['text'] == result['answer_markdown']


def test_all_company_and_project_choices_render():
    test = app()
    test.sidebar.radio[0].set_value('QuarterLens').run()
    choices = test.selectbox[0].options
    for i in range(len(choices)):
        test.selectbox[0].select_index(i).run()
        assert not test.exception, choices[i]
    test.sidebar.radio[0].set_value('Growth Payoff').run()
    for i in range(len(test.selectbox[0].options)):
        test.selectbox[0].select_index(i).run()
        assert not test.exception


def test_research_check_does_not_change_assessment():
    test = app()
    test.sidebar.radio[0].set_value('Saved research').run()
    next(a for a in test.text_area if a.label == 'Your research idea').set_value('Margins are under pressure')
    test.multiselect[0].select('Q1 FY27')
    result = {'symbol': 'TCS', 'thesis': 'Margins are under pressure', 'suggestions': [
        {'period': 'Q1 FY27', 'relation': 'challenges', 'reason': 'Read source', 'evidence': []}]}
    with patch('ui.client.check_research', return_value=result):
        next(b for b in test.button if b.label == 'Find source-backed suggestions').click().run()
    assert not test.exception
    assert test.session_state['notes'] == []


def test_research_client_request_and_redaction(monkeypatch):
    from ui.client import check_research
    monkeypatch.setenv('API_ACCESS_TOKEN', 'server-secret')
    def respond(request):
        assert request.url.path == '/thesis/check'
        assert request.headers['Authorization'] == 'Bearer server-secret'
        assert json.loads(request.content)['periods'] == ['Q1 FY27']
        return httpx.Response(200, json={'suggestions': []})
    assert check_research('TCS', 'Margins are under pressure', ['Q1 FY27'],
                          httpx.MockTransport(respond)) == {'suggestions': []}
    with pytest.raises(AnalystError):
        check_research('TCS', 'Margins are under pressure', ['Q1 FY27'],
                        httpx.MockTransport(lambda r: httpx.Response(503, text='secret')))


def test_vercel_and_local_ui_dependencies_match():
    import tomllib
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    local = [line for line in (ROOT / 'ui/requirements.txt').read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    assert project['project']['dependencies'] == local


def test_existing_ask_link_opens_question_without_auto_submitting():
    test = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=15)
    test.query_params['page'] = 'ask'
    test.query_params['q'] = 'What margin?'
    with patch('ui.client.ask') as request:
        test.run()
    assert not test.exception
    assert test.sidebar.radio[0].value == 'Ask the analyst'
    assert test.text_area[0].value == 'What margin?'
    request.assert_not_called()


def test_home_primary_action_opens_ask():
    test = app()
    next(b for b in test.button if b.label == 'Ask the analyst').click().run()
    assert test.sidebar.radio[0].value == 'Ask the analyst'
    assert not test.exception


def test_paste_import_and_direct_export_keep_user_content():
    import base64
    import re
    test = app()
    test.sidebar.radio[0].set_value('Saved research').run()
    rows = [note('Imported research', 'A source quote with <angle brackets>.')]
    next(a for a in test.text_area if a.label == 'Paste a research JSON export').set_value(json.dumps(rows)).run()
    next(b for b in test.button if b.label == 'Import notes').click().run()
    assert not test.exception
    assert test.session_state['notes'][0]['title'] == 'Imported research'
    link = next(m.value for m in test.markdown if 'download="quantrag-research.json"' in m.value)
    encoded = re.search(r'base64,([A-Za-z0-9+/=]+)', link)[1]
    assert json.loads(base64.b64decode(encoded)) == rows
    assert '<angle brackets>' not in link

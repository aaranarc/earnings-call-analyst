import pytest

from generate import provider


class Failure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__('secret-provider-details')


class Model:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def invoke(self, prompt):
        self.calls.append(prompt)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(provider.time, 'sleep', lambda _: None)


def test_transient_failure_recovers_with_same_prompt():
    model = Model([Failure(503), 'cited-result'])
    assert provider.ResilientModel(model).invoke('source excerpts') == 'cited-result'
    assert model.calls == ['source excerpts', 'source excerpts']


@pytest.mark.parametrize('code', [429, 500, 502, 503, 504])
def test_retries_are_bounded_and_redacted(code, caplog):
    model = Model([Failure(code), Failure(code)])
    with pytest.raises(provider.ProviderUnavailable, match='provider is busy') as error:
        provider.ResilientModel(model).invoke('private-question')
    assert len(model.calls) == 2
    assert 'secret-provider-details' not in str(error.value) + caplog.text
    assert 'private-question' not in caplog.text


@pytest.mark.parametrize('code', [400, 401, 403, 404])
def test_permanent_errors_do_not_retry_or_fallback(code):
    model, fallback = Model([Failure(code)]), Model(['wrong'])
    with pytest.raises(Failure):
        provider.ResilientModel(model, fallback).invoke('prompt')
    assert len(model.calls) == 1 and fallback.calls == []


def test_explicit_fallback_is_second_and_final_attempt():
    model, fallback = Model([Failure(503)]), Model(['fallback-result'])
    assert provider.ResilientModel(model, fallback).invoke('same excerpts') == 'fallback-result'
    assert model.calls == fallback.calls == ['same excerpts']


def test_provider_busy_stream_releases_lock(monkeypatch):
    from fastapi.testclient import TestClient

    from quantrag import api
    for key in ('SUPABASE_DB_URL', 'GEMINI_API_KEY', 'GEMINI_MODEL'):
        monkeypatch.setenv(key, 'test-only')
    monkeypatch.setattr(api, 'reserve_budget', lambda *args: None)
    def fail(_):
        raise provider.ProviderUnavailable(provider.BUSY_MESSAGE)
    monkeypatch.setattr(api, 'run_answer', fail)
    response = TestClient(api.app).post('/ask', json={'question': 'TCS margins?'})
    assert 'event: error' in response.text and provider.BUSY_MESSAGE in response.text
    assert not api.lock.locked()


def test_timeout_retries_once():
    model = Model([provider.httpx.ReadTimeout('private endpoint'), 'recovered'])
    assert provider.ResilientModel(model).invoke('prompt') == 'recovered'
    assert len(model.calls) == 2


def test_sdk_has_one_attempt_and_optional_fallback(monkeypatch):
    import langchain_google_genai
    calls = []
    class Stub:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def with_structured_output(self, schema):
            return self
    monkeypatch.setattr(langchain_google_genai, 'ChatGoogleGenerativeAI', Stub)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    monkeypatch.setenv('GEMINI_MODEL', 'primary')
    monkeypatch.setenv('GEMINI_FALLBACK_MODEL', '')
    assert provider.make_model(dict).fallback is None
    assert len(calls) == 1 and calls[0]['max_retries'] == 1 and calls[0]['timeout'] == 25
    monkeypatch.setenv('GEMINI_FALLBACK_MODEL', 'explicit-fallback')
    assert provider.make_model(dict).fallback is not None
    assert [c['model'] for c in calls[1:]] == ['primary', 'explicit-fallback']

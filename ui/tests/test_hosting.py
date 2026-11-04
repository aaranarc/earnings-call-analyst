import pytest

from ui import client


def test_binding_selected_explicitly_and_keeps_base_path(monkeypatch):
    monkeypatch.setenv('API_PROVIDER', 'vercel')
    monkeypatch.setenv('ANALYST_INTERNAL_URL', 'https://private.example/service/')
    monkeypatch.setenv('API_ORIGIN', 'https://old.example')
    assert client.api_origin() == 'https://private.example/service'


def test_missing_binding_never_falls_back_to_render(monkeypatch):
    monkeypatch.setenv('API_PROVIDER', 'vercel')
    monkeypatch.delenv('ANALYST_INTERNAL_URL', raising=False)
    with pytest.raises(client.AnalystError):
        client.api_origin()
    assert client.health()['configured'] is False


def test_local_api_origin(monkeypatch):
    monkeypatch.delenv('API_PROVIDER', raising=False)
    monkeypatch.setenv('API_ORIGIN', 'http://127.0.0.1:8000/')
    assert client.api_origin() == 'http://127.0.0.1:8000'

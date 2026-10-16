import json

from fastapi.testclient import TestClient
from quantrag import api

client = TestClient(api.app)


def test_health_and_coverage_do_not_need_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/health").json()["configured"] is False
    coverage = client.get("/companies").json()
    assert coverage["source"] == "committed ingest snapshot"
    assert sum(len(c["documents"]) for c in coverage["companies"]) == 8
    assert all(d["source_url"].startswith("https://") for c in coverage["companies"] for d in c["documents"])


def test_missing_eval_returns_no_fake_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
    data = client.get("/eval/latest").json()
    assert data["status"] == "pending"
    assert data["metrics"] == []
    assert data["last_run"] is None


def test_public_eval_reads_only_designated_report(tmp_path, monkeypatch):
    path = tmp_path / "eval/results"
    path.mkdir(parents=True)
    (path / "public_eval.json").write_text(json.dumps({"status": "published", "metrics": []}))
    monkeypatch.setattr(api, "ROOT", tmp_path)
    assert client.get("/eval/latest").json()["status"] == "published"


def test_ask_rejects_blank_or_oversized_input():
    for question in ("   ", "x" * 2001):
        assert client.post("/ask", json={"question": question}).status_code == 422


def test_ask_unconfigured_is_actionable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.post("/ask", json={"question": "Test question"}).status_code == 503


def configure(monkeypatch):
    for key in ("SUPABASE_DB_URL", "GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.setenv(key, "test-only")


def test_checked_answer_stream_and_busy_rejection(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(api, "run_answer", lambda q: {"question": q, "refused": True})
    result = client.post("/ask", json={"question": " Test question "})
    assert "event: status" in result.text
    assert '"question": "Test question"' in result.text
    assert "event: answer" in result.text
    assert not api.lock.locked()

    class Busy:
        def locked(self):
            return True
    monkeypatch.setattr(api, "lock", Busy())
    result = client.post("/ask", json={"question": "Test question"})
    assert result.status_code == 429
    assert result.headers["retry-after"] == "10"


def test_provider_errors_are_redacted_and_lock_released(monkeypatch):
    configure(monkeypatch)

    def fail(_):
        raise RuntimeError("secret-connection-details")
    monkeypatch.setattr(api, "run_answer", fail)
    response = client.post("/ask", json={"question": "Test question"})
    assert "event: error" in response.text
    assert "secret-connection-details" not in response.text
    assert not api.lock.locked()


def test_access_token_is_required_when_configured(monkeypatch):
    monkeypatch.setenv("API_ACCESS_TOKEN", "a" * 32)
    assert client.post("/ask", json={"question": "A question"}).status_code == 401
    assert client.post("/ask", json={"question": "A question"}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/health").status_code == 200


def test_production_fails_closed_without_token(monkeypatch):
    import pytest
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="API_ACCESS_TOKEN"), TestClient(api.app):
        pass
    assert client.post("/ask", json={"question": "A question"}).status_code == 401


def test_budget_exhaustion_rejects_before_model_call(tmp_path, monkeypatch):
    from quantrag.usage import reserve
    configure(monkeypatch)
    monkeypatch.setenv("USAGE_DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "1")
    reserve()
    monkeypatch.setattr(api, "run_answer", lambda q: (_ for _ in ()).throw(AssertionError("must not run")))
    response = client.post("/ask", json={"question": "A question"})
    assert response.status_code == 429
    assert "budget" in response.json()["detail"]
    assert not api.lock.locked()


def test_thesis_check_schema_coverage_and_response(tmp_path, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("USAGE_DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(api, "run_thesis", lambda body: {"assessment": "Unresolved", "automatic_status_change": False})
    body = {"symbol": "TCS", "thesis": "Margins recover", "periods": ["Q1 FY27"]}
    assert client.post("/thesis/check", json=body).json()["assessment"] == "Unresolved"
    assert client.post("/thesis/check", json=dict(body, periods=["Q4 FY26"])).status_code == 200
    assert client.post("/thesis/check", json=dict(body, periods=["Q1 FY26"])).status_code == 422
    assert client.post("/thesis/check", json=dict(body, periods=["Q1 FY27"] * 2)).status_code == 422
    assert client.post("/thesis/check", json=dict(body, thesis="   ")).status_code == 422

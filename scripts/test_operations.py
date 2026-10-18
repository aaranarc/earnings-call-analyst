import hashlib

import httpx
import operations as op
import pytest

PDF = b"%PDF-1.4 reviewed source"


def row():
    return {"filename": "TCS_Q1FY27.pdf", "source_url": "https://www.tcs.com/source.pdf",
            "sha256": hashlib.sha256(PDF).hexdigest()}


def test_restore_verifies_hash_and_reuses_local(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=PDF))) as client:
        assert op.restore(row(), tmp_path, client) == "downloaded_verified"
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected network"))) as client:
        assert op.restore(row(), tmp_path, client) == "verified_local"
        (tmp_path / row()["filename"]).write_bytes(b"tampered")
        with pytest.raises(ValueError, match="hash mismatch"):
            op.restore(row(), tmp_path, client)


@pytest.mark.parametrize("body", [b"HTML login", b"%PDF-1.4 different source"])
def test_bad_source_never_written(tmp_path, body):
    with (httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client,
          pytest.raises(ValueError, match="does not match")):
        op.restore(row(), tmp_path, client)
    assert not list(tmp_path.iterdir())


def test_redirect_does_not_contact_unapproved_host(tmp_path):
    seen = []

    def respond(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with (httpx.Client(transport=httpx.MockTransport(respond)) as client,
          pytest.raises(ValueError, match="approved")):
        op.restore(row(), tmp_path, client)
    assert seen == ["www.tcs.com"]


@pytest.mark.parametrize("changes", [
    {"filename": "../x.pdf"}, {"sha256": ""}, {"source_url": "https://evil.example/x.pdf"},
    {"source_url": "https://user:secret@www.tcs.com/x.pdf"},
])
def test_unreviewed_source_rejected_before_network(tmp_path, changes):
    with (httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected request"))) as client,
          pytest.raises(ValueError)):
        op.restore(row() | changes, tmp_path, client)


def test_size_limit_leaves_no_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "MAX_PDF_BYTES", 4)
    with (httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=PDF))) as client,
          pytest.raises(ValueError, match="size limit")):
        op.restore(row(), tmp_path, client)
    assert not list(tmp_path.iterdir())


def test_verified_private_archive_restores_without_contacting_blocked_issuer(tmp_path):
    archive = lambda _: (row()["source_url"], PDF)
    assert op.restore(row(), tmp_path, None, archive) == "restored_verified_archive"
    assert (tmp_path / row()["filename"]).read_bytes() == PDF


def test_corrupt_private_archive_cannot_replace_reviewed_source(tmp_path):
    with pytest.raises(ValueError, match="Archived PDF"):
        op.restore(row(), tmp_path, None, lambda _: (row()["source_url"], b"%PDF-tampered"))
    assert not list(tmp_path.iterdir())


def test_pending_evaluation_and_cold_models_are_healthy():
    def respond(request):
        if request.url.path == "/":
            return httpx.Response(200, text="QuantRAG")
        if request.url.path.endswith("companies"):
            return httpx.Response(200, json={"companies": [{"documents": [{"fiscal_label": "Q1 FY27"}]}]})
        if request.url.path.endswith("latest"):
            return httpx.Response(200, json={"status": "pending"})
        return httpx.Response(200, json={"status": "ok", "configured": True, "models_loaded": False})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = op.health(client)
    assert result["ok"] is True
    assert result["checks"][-1]["models_loaded"] is False


def test_health_fails_for_malformed_or_down_services():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))) as client:
        result = op.health(client)
    assert not result["ok"]
    assert all(not item["ok"] for item in result["checks"])

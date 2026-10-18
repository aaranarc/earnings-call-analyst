"""Bounded production checks and restoration of reviewed source PDFs. No generation calls.

python scripts/operations.py health --out /tmp/health.json
python scripts/operations.py sources --out /tmp/sources.json
Sources are accepted only from approved official hosts and against committed SHA-256 hashes.
This does not discover, approve or silently replace new versions of documents.
"""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

import check_manifest as cm

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_HOSTS = {
    "www.tcs.com", "www.infosys.com", "www.hcltech.com", "www.wipro.com", "www.hul.co.in",
    "www.hdfcbank.com", "www.hdfc.bank.in", "www.icicibank.com", "www.icici.bank.in",
    "www.axisbank.com", "www.axis.bank.in",
    "www.kotak.com", "www.kotak.bank.in", "www.asianpaints.com", "itcportal.com", "www.itcportal.com",
}
MAX_PDF_BYTES = 30 * 1024 * 1024


def checked_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Source must use an approved official HTTPS host")
    return url


def restore(row, raw_dir, client, archive_lookup=None):
    """Validate cache or fetch to a temporary file; never overwrite a different registered source."""
    filename = row["filename"]
    if not re.fullmatch(r"(?:results/)?[A-Za-z0-9_-]+\.pdf", filename):
        raise ValueError("Source filename must be a PDF basename or a file in results/")
    if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
        raise ValueError("Source needs a reviewed SHA-256")
    url = checked_url(row["source_url"])
    path = raw_dir / filename
    if path.exists():
        if cm.sha256(path) != row["sha256"]:
            raise ValueError("Local source hash mismatch; refusing replacement")
        return "verified_local"
    if archive_lookup:
        archived = archive_lookup(row["sha256"])
        if archived and archived[0] == url:
            body = bytes(archived[1])
            if (not body.startswith(b"%PDF-") or len(body) > MAX_PDF_BYTES
                    or hashlib.sha256(body).hexdigest() != row["sha256"]):
                raise ValueError("Archived PDF does not match the reviewed source")
            write_pdf(path, body)
            return "restored_verified_archive"
    if client is None:
        raise ValueError("Archiving requires the reviewed PDF locally")
    # Redirects are checked individually before the next request, including scheme/host/credentials.
    for _ in range(6):
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                url = checked_url(str(response.url.join(response.headers["location"])))
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_PDF_BYTES:
                    raise ValueError("Source exceeds PDF size limit")
        if not body.startswith(b"%PDF-") or hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ValueError("Downloaded PDF does not match the reviewed source")
        write_pdf(path, body)
        return "downloaded_verified"
    raise ValueError("Too many source redirects")


def write_pdf(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pdf.part")
    try:
        temporary.write_bytes(body)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def registered_rows(root):
    rows = cm.read_manifest(root / "data/manifest.csv")
    extra = root / "data/results_manifest.csv"
    if extra.exists():
        import csv
        with extra.open() as stream:
            rows += list(csv.DictReader(stream))
    return [r for r in rows if r["filename"]]


def archive_sources(conn, root=ROOT):
    rows = registered_rows(root)
    payloads = []
    for row in rows:
        # The restore path validates basename, host and hash without making a request for a local PDF.
        restore(row, root / "data/raw", None)
        body = (root / "data/raw" / row["filename"]).read_bytes()
        if not body.startswith(b"%PDF-") or len(body) > MAX_PDF_BYTES:
            raise ValueError("Invalid source PDF")
        payloads.append((row["sha256"], row["source_url"], body))
    conn.execute((root / "db/schema.sql").read_text())
    with conn.cursor() as cur:
        cur.executemany("""insert into source_pdfs (sha256,source_url,content) values (%s,%s,%s)
            on conflict (sha256) do nothing""", payloads)
    # Verify read-back including RLS rather than treating successful writes as recovery proof.
    for sha, url, body in payloads:
        archived = conn.execute("select source_url,content from source_pdfs where sha256=%s", (sha,)).fetchone()
        if not archived or archived[0] != url or bytes(archived[1]) != body:
            raise ValueError("Source archive read-back mismatch")
    rls = conn.execute("select relrowsecurity from pg_class where oid='quantrag.source_pdfs'::regclass").fetchone()[0]
    policies = conn.execute("select count(*) from pg_policies where schemaname='quantrag' and tablename='source_pdfs'").fetchone()[0]
    if not rls or policies:
        raise ValueError("Private source archive requires row-level security with no public policies")
    return {"ok": True, "archived_documents": len(payloads), "bytes": sum(len(p[2]) for p in payloads),
            "rls_enabled": rls, "access_policies": policies}


def sources(client, root=ROOT, archive_lookup=None):
    rows = registered_rows(root)
    results = []
    for row in rows:
        if not row["filename"]:
            continue
        result = {"symbol": row["symbol"], "period": row["fiscal_label"], "filename": row["filename"]}
        try:
            result["status"] = restore(row, root / "data/raw", client, archive_lookup)
        except (ValueError, httpx.HTTPError) as exc:
            # No raw exceptions: URLs from a redirect could contain sensitive query parameters.
            result.update(status="blocked", category=type(exc).__name__)
        results.append(result)
    return {"ok": bool(results) and all(r["status"] != "blocked" for r in results), "sources": results}


def health(client):
    results = []
    for name, url in [
        ("dashboard", "https://quantrag.vercel.app/"),
        ("coverage", "https://quantrag.vercel.app/api/companies"),
        ("evaluation", "https://quantrag.vercel.app/api/eval/latest"),
        ("api", "https://quantrag-api.onrender.com/health"),
    ]:
        started = time.monotonic()
        item = {"check": name, "ok": False}
        try:
            response = client.get(url)
            response.raise_for_status()
            if name == "coverage":
                data = response.json()
                if not any(c.get("documents") for c in data["companies"]):
                    raise ValueError("No covered documents")
            elif name == "evaluation":
                data = response.json()
                if data["status"] not in {"pending", "published"}:
                    raise ValueError("Unknown evaluation state")
                item["evaluation_status"] = data["status"]
            elif name == "api":
                data = response.json()
                if data.get("status") != "ok" or data.get("configured") is not True:
                    raise ValueError("API is not configured")
                item["models_loaded"] = data.get("models_loaded")
            elif "QuantRAG" not in response.text:
                raise ValueError("Unexpected dashboard")
            item["ok"] = True
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            item["category"] = type(exc).__name__
        item["elapsed_s"] = round(time.monotonic() - started, 3)
        results.append(item)
    return {"ok": all(r["ok"] for r in results), "checks": results,
            "note": "HTTP readiness timing, not proof of an idle cold start or model-answer quality."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["health", "sources", "archive"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    timeout = 120 if args.mode == "health" else 30
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=15), follow_redirects=False) as client:
        if args.mode == "archive" or (args.mode == "sources" and os.getenv("SUPABASE_DB_URL")):
            import psycopg
            with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=15,
                                 options="-c search_path=quantrag,public,extensions") as conn:
                if args.mode == "archive":
                    report = archive_sources(conn)
                else:
                    conn.execute("set transaction read only")
                    exists = conn.execute("select to_regclass('quantrag.source_pdfs')").fetchone()[0]
                    def lookup(sha):
                        return conn.execute("select source_url,content from source_pdfs where sha256=%s", (sha,)).fetchone()
                    report = sources(client, archive_lookup=lookup if exists else None)
        else:
            report = health(client) if args.mode == "health" else sources(client)
    report["checked_at"] = datetime.now(UTC).isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

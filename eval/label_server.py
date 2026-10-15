"""Local labelling page for the number-checker sheet. Local only: binds 127.0.0.1.

    python eval/label_server.py            # then open http://127.0.0.1:8765

One row at a time: the answer sentence with the number highlighted, the cited excerpts with every number of the same
value highlighted (any unit, so you can spot unit/scale swaps), and Supported / Not supported / Unsure + notes.
Keys: 1 / 2 / 3 to label (saves and moves on), ← / → to move, N for the next unlabelled row.
Saves after every click to eval/labels/numbers_labels.csv (id, label, notes, labelled_at).
Reads only eval/numbers_to_label.csv, never the answer key in eval/private/ (D33).
"""
import csv
import datetime
import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from numcheck.extract import SCALES, extract

SHEET = ROOT / "eval/numbers_to_label.csv"
LABELS_FILE = ROOT / "eval/labels/numbers_labels.csv"
CHOICES = ("supported", "not_supported", "unsure")


def same_value_spans(text, number_raw):
    """Spans in `text` of numbers equal in value to `number_raw` (at its stated precision; any unit, any sign)."""
    targets = extract(number_raw)
    spans = []
    for n in extract(text):
        for t in targets:
            tol = 0.5 * 10 ** -t.decimals * (SCALES[t.scale] if t.scale else 1.0) + 1e-9
            if abs(abs(n.value) - abs(t.value)) <= tol:
                spans.append([n.start, n.end])
                break
    return spans


def load_rows():
    with open(SHEET, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        i = r["answer_sentence"].find(r["number"])
        r["sentence_spans"] = [[i, i + len(r["number"])]] if i >= 0 else []
        r["excerpt_spans"] = same_value_spans(r["cited_excerpts"], r["number"])
    return rows


def load_labels():
    if not LABELS_FILE.exists():
        return {}
    with open(LABELS_FILE, newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def save_labels(labels):
    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=LABELS_FILE.parent, suffix=".csv")
    with os.fdopen(fd, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "notes", "labelled_at"])
        w.writeheader()
        w.writerows(sorted(labels.values(), key=lambda r: r["id"]))
    os.replace(tmp, LABELS_FILE)  # atomic: a crash never leaves a half-written file


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Number labelling</title>
<style>
:root{--bg:#0f1115;--panel:#181b22;--text:#e8e8ec;--muted:#9aa0ab;--line:#2a2e38;--mark:#5b4a00;--markt:#ffe08a;
--ok:#1f7a45;--bad:#a33434;--unsure:#6b5a1f;--focus:#7c9cff}
@media (prefers-color-scheme: light){:root{--bg:#f6f7f9;--panel:#fff;--text:#1b1d22;--muted:#5d6370;--line:#dde0e6;
--mark:#ffe58a;--markt:#1b1d22;--ok:#1f7a45;--bad:#b42d2d;--unsure:#8a6d12;--focus:#3557d6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
header{display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:space-between}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;flex:1;min-width:160px}
.bar>div{height:100%;background:var(--focus)}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-top:12px}
h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
.num{font:600 20px/1.3 ui-monospace,monospace}
mark{background:var(--mark);color:var(--markt);padding:0 2px;border-radius:3px}
#excerpts{white-space:pre-wrap;max-height:46vh;overflow:auto;font-size:14px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
button{font:inherit;padding:10px 14px;border-radius:8px;border:1px solid var(--line);background:var(--panel);
color:var(--text);cursor:pointer}button:focus-visible,textarea:focus-visible{outline:2px solid var(--focus)}
button.sup{background:var(--ok);color:#fff;border-color:transparent}
button.bad{background:var(--bad);color:#fff;border-color:transparent}
button.uns{background:var(--unsure);color:#fff;border-color:transparent}
button.chosen{box-shadow:0 0 0 3px var(--focus)}
textarea{width:100%;min-height:56px;font:inherit;background:var(--bg);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:8px}
.muted{color:var(--muted)}details{margin-top:12px}kbd{font:12px ui-monospace,monospace;border:1px solid var(--line);
border-radius:4px;padding:0 4px}
</style></head><body><main>
<header><strong id="pos">…</strong><div class="bar" aria-label="progress"><div id="prog" style="width:0"></div></div>
<span id="count" class="muted"></span></header>
<section><h2>Question</h2><div id="question"></div></section>
<section><h2>Number</h2><div class="num" id="number"></div>
<h2 style="margin-top:10px">Answer sentence</h2><div id="sentence"></div></section>
<section><h2>Cited excerpts <span class="muted" id="hits"></span></h2><div id="excerpts"></div></section>
<section><div class="actions">
<button class="sup" data-l="supported">1 · Supported</button>
<button class="bad" data-l="not_supported">2 · Not supported</button>
<button class="uns" data-l="unsure">3 · Unsure</button>
<span style="flex:1"></span><button id="prev">← Prev</button><button id="next">Next →</button>
<button id="todo">N · Next unlabelled</button></div>
<label for="notes" class="muted" style="display:block;margin-top:10px">Notes (saved with the label)</label>
<textarea id="notes" placeholder="e.g. right number, wrong metric; not a figure; found on p.7 of the PDF"></textarea>
<div id="saved" class="muted" aria-live="polite"></div></section>
<details><summary>Labelling guide</summary><ul>
<li><b>Supported</b>: the cited excerpts state this number as the sentence uses it: same value at the precision written
(rounding like 25% for 25.3% is fine), same unit and scale (bn = billion), <i>and</i> the same company, quarter and
metric. A number you can compute exactly from figures in one excerpt also counts.</li>
<li><b>Not supported</b>: wrong value, unit or scale; right number but wrong company / quarter / metric; or not in the
cited excerpts at all (even if it appears elsewhere in the transcript, so note it).</li>
<li><b>Unsure</b>: you can't tell from what's shown. Say why in notes. Unsure rows are left out of the scores.</li>
<li>Highlights are a search aid: every number in the excerpts with the same value, in any unit. A highlight is not a
verdict.</li></ul></details>
</main><script>
let rows=[], labels={}, i=0;
const $=id=>document.getElementById(id);
function marked(el,text,spans){el.textContent="";let p=0;for(const [a,b] of spans.sort((x,y)=>x[0]-y[0])){
 if(a<p)continue;el.append(text.slice(p,a));const m=document.createElement("mark");m.textContent=text.slice(a,b);
 el.append(m);p=b}el.append(text.slice(p))}
function show(){const r=rows[i];$("pos").textContent=`${r.id} · ${i+1} / ${rows.length}`;
 const done=Object.keys(labels).length;$("count").textContent=`${done} labelled`;
 $("prog").style.width=(100*done/rows.length)+"%";$("question").textContent=r.question;$("number").textContent=r.number;
 marked($("sentence"),r.answer_sentence,r.sentence_spans);marked($("excerpts"),r.cited_excerpts,r.excerpt_spans);
 $("hits").textContent=`(${r.excerpt_spans.length} same-value match${r.excerpt_spans.length==1?"":"es"})`;
 const l=labels[r.id];$("notes").value=l?l.notes:"";
 document.querySelectorAll("[data-l]").forEach(b=>b.classList.toggle("chosen",!!l&&l.label===b.dataset.l));
 $("saved").textContent=l?`saved: ${l.label.replace("_"," ")} at ${l.labelled_at}`:"not labelled yet";
 const m=$("excerpts").querySelector("mark");if(m)m.scrollIntoView({block:"center"});else $("excerpts").scrollTop=0}
async function label(l){const r=rows[i];const res=await fetch("/api/label",{method:"POST",
 headers:{"Content-Type":"application/json"},body:JSON.stringify({id:r.id,label:l,notes:$("notes").value})});
 if(!res.ok){$("saved").textContent="save failed: "+await res.text();return}labels[r.id]=await res.json();
 if(i<rows.length-1)i++;show()}
function nextTodo(){const j=rows.findIndex((r,k)=>k>i&&!labels[r.id]);const k=j>=0?j:rows.findIndex(r=>!labels[r.id]);
 if(k>=0){i=k;show()}else $("saved").textContent="all rows labelled"}
document.querySelectorAll("[data-l]").forEach(b=>b.onclick=()=>label(b.dataset.l));
$("prev").onclick=()=>{if(i>0){i--;show()}};$("next").onclick=()=>{if(i<rows.length-1){i++;show()}};
$("todo").onclick=nextTodo;
document.addEventListener("keydown",e=>{if(e.target.tagName==="TEXTAREA")return;
 if(e.key==="1")label("supported");else if(e.key==="2")label("not_supported");else if(e.key==="3")label("unsure");
 else if(e.key==="ArrowLeft")$("prev").click();else if(e.key==="ArrowRight")$("next").click();
 else if(e.key.toLowerCase()==="n")nextTodo()});
fetch("/api/rows").then(r=>r.json()).then(d=>{rows=d.rows;labels=d.labels;i=Math.max(0,rows.findIndex(r=>!labels[r.id]));
 show()});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html")
        if self.path == "/api/rows":
            return self._send(200, json.dumps({"rows": ROWS, "labels": load_labels()}))
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/label":
            return self._send(404, "not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if body.get("id") not in IDS or body.get("label") not in CHOICES:
            return self._send(400, "bad id or label", "text/plain")
        labels = load_labels()
        labels[body["id"]] = {"id": body["id"], "label": body["label"], "notes": str(body.get("notes", ""))[:2000],
                              "labelled_at": datetime.datetime.now().isoformat(timespec="seconds")}
        save_labels(labels)
        self._send(200, json.dumps(labels[body["id"]]))

    def log_message(self, *args):  # keep the terminal quiet
        pass


ROWS = load_rows()
IDS = {r["id"] for r in ROWS}

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"{len(ROWS)} rows · labels -> {LABELS_FILE.relative_to(ROOT)} · open http://127.0.0.1:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

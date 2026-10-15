"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Check,
  Download,
  FileText,
  Filter,
  Plus,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import Shell from "./shell";
import ThesisCheck from "./thesis-check";
import CoverageMap from "./coverage-map";
import { EvidenceBalance, EvidenceProgress } from "./research-visuals";
import Dialog from "./dialog";
import {
  exportWorkspace,
  parseImport,
  mergeImport,
  readWorkspace,
  sampleTheses,
  saveWorkspace,
} from "@/lib/workspace";
import type { Status, Thesis } from "@/lib/types";
const statusIcon = {
  "Supports thesis": ArrowUpRight,
  "Challenges thesis": ArrowDownRight,
  Unresolved: Search,
};
export default function Dashboard() {
  const [own, setOwn] = useState<Thesis[]>([]),
    [samples, setSamples] = useState(sampleTheses),
    [demo, setDemo] = useState(true),
    [ready, setReady] = useState(false),
    [error, setError] = useState("");
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("All signals"),
    [company, setCompany] = useState("All companies"),
    [selected, setSelected] = useState<string | null>(null),
    [adding, setAdding] = useState(false),
    [brief, setBrief] = useState(false),
    [imported, setImported] = useState<Thesis[] | null>(null);
  useEffect(() => {
    try {
      const rows = readWorkspace();
      setOwn(rows);
      if (rows.length) setDemo(false);
    } catch (e) {
      setError((e as Error).message);
    }
    setReady(true);
  }, []);
  const rows = demo ? samples : own;
  const selectedRow = rows.find((r) => r.id === selected);
  function persist(next: Thesis[]) {
    if (demo) {
      setSamples(next);
      return true;
    }
    try {
      saveWorkspace(next);
      setOwn(next);
      setError("");
      return true;
    } catch {
      setError(
        "Browser storage is unavailable. Your changes have not been saved.",
      );
      return false;
    }
  }
  function update(row: Thesis) {
    return persist(rows.map((r) => (r.id === row.id ? row : r)));
  }
  const filtered = rows.filter(
    (r) =>
      (company === "All companies" || r.symbol === company) &&
      (filter === "All signals" || r.status === filter) &&
      `${r.title} ${r.company} ${r.symbol}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const supports = rows.filter((r) => r.status === "Supports thesis").length,
    challenges = rows.filter((r) => r.status === "Challenges thesis").length,
    unresolved = rows.filter((r) => r.status === "Unresolved").length;
  return (
    <Shell>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="tiny-line" /> RESEARCH OVERVIEW
          </div>
          <h1>Your research desk.</h1>
          <p>
            Track an idea. Collect evidence. Update your view.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => setAdding(true)}
          disabled={!ready}
        >
          <Plus size={17} /> New thesis
        </button>
      </div>
      <div className="mode-strip">
        <span>
          <Sparkles size={15} />
          {demo ? "Example workspace" : "Your workspace"}{" "}
          <span className="muted">
            {demo
              ? "Illustrative data · Not company findings."
              : "Local to this browser · Manual assessments."}
          </span>
        </span>
        <button
          className="text-link"
          onClick={() => {
            setDemo(!demo);
            setSelected(null);
            setCompany("All companies");
            setFilter("All signals");
          }}
        >
          {demo ? "Open my workspace" : "Explore example"}
          <ArrowRight size={15} />
        </button>
      </div>
      {error && (
        <div role="alert" className="notice">
          {error}
        </div>
      )}
      <section className="stat-grid" aria-label="Workspace overview">
        {[
          [Target, "Active theses", rows.length, "Ideas you are following"],
          [
            ArrowUpRight,
            "Supporting evidence",
            supports,
            "Developments that align",
          ],
          [
            ArrowDownRight,
            "Worth a closer look",
            challenges,
            "Developments that challenge",
          ],
          [
            Search,
            "Still an open question",
            unresolved,
            "More evidence needed",
          ],
        ].map(([Icon, label, n, sub], i) => {
          const I = Icon as typeof Target;
          return (
            <div className={`stat-card stat-${i}`} key={String(label)}>
              <div>
                <span>{String(label)}</span>
                <I size={18} />
              </div>
              <strong>{Number(n).toString().padStart(2, "0")}</strong>
              <small>{String(sub)}</small>
            </div>
          );
        })}
      </section>
      <div className="visual-grid"><CoverageMap /><EvidenceBalance rows={rows} onSelect={setFilter} /></div>
      <div className="dashboard-columns">
        <section className="thesis-section">
          <div className="section-head">
            <div>
              <h2>
                Your theses <span className="count">{rows.length}</span>
              </h2>
              <p>{demo ? "Example research" : "Your saved research"}</p>
            </div>
            <label className="button ghost import-control">Import JSON<input type="file" accept=".json,application/json" aria-label="Import workspace JSON" onChange={async e => {
              const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
              try { if (file.size > 5 * 1024 * 1024) throw Error("Choose a file smaller than 5 MB."); setImported(parseImport(await file.text())); setError(""); }
              catch (err) { setError((err as Error).message); }
            }}/></label>
            <button
              className="icon-button"
              disabled={demo}
              onClick={() => exportWorkspace(rows)}
              aria-label="Export theses"
            >
              <Download size={18} />
            </button>
          </div>
          <div className="filters">
            <label className="search-input">
              <Search size={16} />
              <input
                aria-label="Search theses"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search company or thesis…"
              />
            </label>
            <label className="select-wrap">
              <Filter size={15} />
              <select
                aria-label="Filter by company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              >
                <option>All companies</option>
                {[...new Set(rows.map((r) => r.symbol))].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="filter-tabs" aria-label="Signal filter">
            {[
              "All signals",
              "Supports thesis",
              "Challenges thesis",
              "Unresolved",
            ].map((s) => (
              <button
                key={s}
                aria-pressed={filter === s}
                onClick={() => setFilter(s)}
                className={filter === s ? "selected" : ""}
              >
                {s === "Supports thesis"
                  ? "Supporting"
                  : s === "Challenges thesis"
                    ? "Challenging"
                    : s}
              </button>
            ))}
          </div>
          <div className="thesis-list">
            {filtered.map((row, i) => {
              const Icon = statusIcon[row.status];
              return (
                <button
                  className="thesis-card"
                  key={row.id}
                  onClick={() => setSelected(row.id)}
                  style={{ animationDelay: `${i * 70}ms` }}
                >
                  <div className="thesis-top">
                    <span className="company-avatar">
                      {row.symbol.slice(0, 2)}
                    </span>
                    <div>
                      <strong>{row.symbol}</strong>
                      <span>{row.company}</span>
                    </div>
                    <span
                      className={`signal ${row.status === "Supports thesis" ? "support" : row.status === "Challenges thesis" ? "challenge" : "unresolved"}`}
                    >
                      <Icon size={13} />
                      {row.status}
                    </span>
                  </div>
                  <h3>{row.title}</h3>
                  <EvidenceProgress row={row} />
                  <div className="thesis-bottom">
                    <span>
                      <FileText size={14} />
                      {row.sample
                        ? "Illustrative evidence"
                        : row.evidence.length
                          ? "Your evidence notes"
                          : "Awaiting evidence"}
                    </span>
                    <span>
                      {row.reviewed ? (
                        <>
                          <Check size={14} />
                          Reviewed
                        </>
                      ) : (
                        <>
                          Review evidence <ArrowRight size={15} />
                        </>
                      )}
                    </span>
                  </div>
                </button>
              );
            })}
            {!filtered.length && (
              <div className="empty-state">
                <Target size={30} />
                <h3>
                  {rows.length
                    ? "No matching theses"
                    : "What are you watching for?"}
                </h3>
                <p>
                  {rows.length
                    ? "Try another company, signal, or search term."
                    : "Pin an idea about a company, then collect the evidence that could change your mind."}
                </p>
                {!rows.length && (
                  <button
                    className="button primary"
                    onClick={() => setAdding(true)}
                  >
                    <Plus size={15} /> Add your first thesis
                  </button>
                )}
              </div>
            )}
          </div>
        </section>
        <aside className="research-rail">
          <div className="rail-card brief-card">
            <span className="eyebrow">RESEARCH BRIEF</span>
            <div className="brief-glyph" aria-hidden="true"><FileText size={44}/><span>Q / R</span></div>
            <h3>Your thinking.<br/>On one page.</h3>
            <p>Theses, evidence and next steps.</p>
            <button className="button secondary" onClick={() => setBrief(true)}>Open research brief <ArrowUpRight size={15}/></button>
          </div>
          <Link href="/ask" className="rail-card research-shortcut"><Search size={20}/><span>Find the next piece of evidence</span><ArrowRight size={17}/></Link>
        </aside>
      </div>
      {imported && <Dialog title="Restore research" onClose={() => setImported(null)}><div className="dialog-body">
        <p>{imported.length} theses ready to import. Identical entries are skipped; conflicting IDs are saved as separate copies. Existing research is retained.</p>
        <button className="button primary" onClick={() => {try {const next = mergeImport(readWorkspace(), imported); saveWorkspace(next); setOwn(next); setDemo(false); setImported(null); setError("");} catch (err) {setError((err as Error).message); setImported(null);}}}>Merge into my workspace</button>
      </div></Dialog>}
      {brief && <Dialog title="Research brief" onClose={() => setBrief(false)}>
        <div className="dialog-body research-brief">
          <span className="eyebrow">QUANTRAG / {demo ? "ILLUSTRATIVE EXAMPLE" : "PERSONAL RESEARCH"}</span>
          <h2>The evidence so far.</h2>
          <p>{rows.length} theses · {rows.filter(r => r.reviewed).length} reviewed · Manual assessments</p>
          <button className="button secondary print-action" onClick={() => window.print()}>Print / Save PDF</button>
          {demo && <p className="notice">Illustrative scenarios and quotes. Not actual company findings.</p>}
          {!rows.length && <p>No theses yet. Add one to start your brief.</p>}
          {rows.map(row => <article className="brief-entry" key={row.id}>
            <span className="eyebrow">{row.symbol} · {row.status}</span><h3>{row.title}</h3>
            <EvidenceProgress row={row}/>
            <div className="evidence-timeline">{row.evidence.map(entry => <article key={entry.id}><small>{entry.quarter || "Period unspecified"} · {entry.kind === "answer" ? "Generated answer + sources" : "Evidence note"}</small><p>{entry.text}</p></article>)}</div>
            {row.note && <p className="brief-note">Next check: {row.note}</p>}
          </article>)}
        </div>
      </Dialog>}
      {selectedRow && (
        <Dialog
          drawer
          title="Thesis evidence"
          onClose={() => setSelected(null)}
        >
          <div className="drawer-body">
            <div className="eyebrow">
              {selectedRow.symbol} ·{" "}
              {selectedRow.sample ? "ILLUSTRATIVE EXAMPLE" : "YOUR RESEARCH"}
            </div>
            <h2 className="drawer-title">{selectedRow.title}</h2>
            <p>{selectedRow.description}</p>
            <span className="signal">{selectedRow.status}</span>
            {selectedRow.sample && (
              <div className="notice">
                These quotes demonstrate the interaction. They are not taken
                from this company’s filings.
              </div>
            )}
            <div className="evidence-timeline" aria-label="Evidence timeline">
              {selectedRow.evidence.map((entry, i) => <article key={entry.id}>
                <div className="section-head"><strong>{entry.quarter || "Period unspecified"}</strong><small>{entry.addedAt ? new Date(entry.addedAt).toLocaleDateString() : "Date not recorded"}</small></div>
                <span className="eyebrow">{String(i + 1).padStart(2, "0")} / {entry.kind === "answer" ? "GENERATED ANSWER + SOURCES" : selectedRow.sample ? "ILLUSTRATIVE EXCERPT" : "EVIDENCE NOTE"}</span>
                <p>{entry.text}</p>
              </article>)}
              {!selectedRow.evidence.length && <p>No evidence added yet.</p>}
            </div>
            {!selectedRow.sample && <ThesisCheck row={selectedRow} onSave={entries => update({...selectedRow, evidence:[...selectedRow.evidence, ...entries], status:"Unresolved", reviewed:false})}/>}
            {!selectedRow.sample && <>
              <details className="disclosure" style={{marginBottom: 20}}>
                <summary>Add evidence and your assessment</summary>
                <form onSubmit={e => {
                  e.preventDefault(); const f = new FormData(e.currentTarget);
                  const text = String(f.get("evidence")).trim(); if (!text) return;
                  update({...selectedRow, evidence: [...selectedRow.evidence, {id: crypto.randomUUID(), text, quarter: String(f.get("quarter")).trim(), addedAt: new Date().toISOString(), kind: "note"}], status: "Unresolved", reviewed: false});
                  e.currentTarget.reset();
                }}>
                  <label className="field">Evidence period<input name="quarter" maxLength={200} placeholder="e.g. Q2 FY26"/></label>
                  <label className="field">Evidence note<textarea name="evidence" required maxLength={100000} placeholder="Paste an excerpt and its source reference"/></label>
                  <button className="button secondary" type="submit">Add timeline entry</button>
                </form>
              </details>
              <label className="field">Your assessment<select value={selectedRow.status} onChange={e => update({...selectedRow, status: e.target.value as Status, reviewed: false})}>
                <option>Unresolved</option><option disabled={selectedRow.evidence.length < 2}>Supports thesis</option><option disabled={selectedRow.evidence.length < 2}>Challenges thesis</option>
              </select></label>
            </>}
            <label className="field">
              Research note
              <textarea
                value={selectedRow.note}
                onChange={(e) =>
                  update({ ...selectedRow, note: e.target.value })
                }
                placeholder="What would you check next?"
              />
            </label>
            <div className="dialog-actions">
              <Link
                className="button secondary"
                href={`/ask?q=${encodeURIComponent(`What did ${selectedRow.company} say about ${selectedRow.title.toLowerCase()}?`)}`}
              >
                <Sparkles size={15} /> Ask a follow-up
              </Link>
              <button
                className="button primary"
                onClick={() =>
                  update({ ...selectedRow, reviewed: !selectedRow.reviewed })
                }
              >
                <Check size={15} />
                {selectedRow.reviewed ? "Mark unreviewed" : "Mark reviewed"}
              </button>
            </div>
          </div>
        </Dialog>
      )}
      {adding && (
        <Dialog title="Start with a thesis" onClose={() => setAdding(false)}>
          <form
            className="dialog-body"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const symbol = String(f.get("company"));
              const row: Thesis = {
                id: crypto.randomUUID(),
                company: symbol,
                symbol,
                title: String(f.get("title")).trim(),
                description: String(f.get("description")).trim(),
                status: "Unresolved",
                evidence: [],
                before: "",
                after: "",
                beforeQuarter: "",
                afterQuarter: "",
                note: "",
                reviewed: false,
                sample: false,
              };
              if (!row.title) return;
              try {
                const next = [row, ...own];
                saveWorkspace(next);
                setOwn(next);
                setDemo(false);
                setCompany("All companies");
                setFilter("All signals");
                setAdding(false);
              } catch {
                setError("Could not save. Browser storage may be disabled.");
              }
            }}
          >
            <p>
              Make it specific enough to test against the next earnings call.
            </p>
            <label className="field">
              Company
              <select name="company">
                <option>TCS</option>
                <option>INFY</option>
                <option>HDFCBANK</option>
                <option>HINDUNILVR</option>
              </select>
            </label>
            <label className="field">
              Your thesis
              <input
                name="title"
                required
                maxLength={140}
                placeholder="e.g. AI pilots will convert into recurring revenue"
              />
            </label>
            <label className="field">
              What evidence would you look for?
              <textarea
                name="description"
                maxLength={1000}
                placeholder="A comparable metric, a timeframe, or an explicit commitment…"
              />
            </label>
            <div className="notice">
              New theses begin as unresolved. Nothing is marked supported
              without evidence.
            </div>
            <button className="button primary" type="submit">
              <Plus size={16} /> Save thesis
            </button>
          </form>
        </Dialog>
      )}
    </Shell>
  );
}

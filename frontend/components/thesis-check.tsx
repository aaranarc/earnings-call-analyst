"use client";
import { useEffect, useState } from "react";
import { Sparkles, ArrowDownToLine } from "lucide-react";
import type { Company, Evidence, Thesis } from "@/lib/types";
type Suggestion = {period: string; relation: "supports" | "challenges" | "insufficient"; reason: string;
  evidence: {quote: string; chunk_id: number; symbol: string; period: string; speaker: string; role: string; page: number; source_url?: string}[]};
export default function ThesisCheck({row, onSave}: {row: Thesis; onSave: (entries: Evidence[]) => boolean}) {
  const [companies, setCompanies] = useState<Company[]>([]), [periods, setPeriods] = useState<string[]>([]),
    [busy, setBusy] = useState(false), [error, setError] = useState(""), [results, setResults] = useState<Suggestion[] | null>(null),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    fetch("/api/companies").then(r => {if (!r.ok) throw Error(); return r.json();}).then(data => {
      setCompanies(data.companies);
      setPeriods((data.companies as Company[]).find(c => c.symbol === row.symbol)?.documents.slice(-4).map(d => d.fiscal_label) || []);
    }).catch(() => setError("Transcript coverage could not be loaded."));
  }, [row.symbol]);
  const company = companies.find(c => c.symbol === row.symbol);
  async function check(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setResults(null); setSaved(false);
    try {
      const response = await fetch("/api/thesis/check", {method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({symbol:row.symbol, thesis:row.title + (row.description ? ". " + row.description : ""), periods}), signal:AbortSignal.timeout(280000)});
      if (!response.ok) throw Error(response.status === 429 ? "The analyst is busy or today's budget is used up. Please try later." : "The thesis check could not finish. Check the API and try again.");
      const data = await response.json(); setResults(data.suggestions);
    } catch(err) {setError((err as Error).message);} finally {setBusy(false);}
  }
  return <details className="disclosure thesis-check"><summary><Sparkles size={15}/> Check against earnings calls</summary>
    <div><p className="section-copy">AI suggestions with exact source quotes. Your assessment stays yours.</p>
      {company?.documents.length ? <form onSubmit={check}>
        <fieldset><legend>Periods to check (up to 4)</legend>{company.documents.map(d => <label key={d.fiscal_label} className="period-option"><input type="checkbox" checked={periods.includes(d.fiscal_label)} onChange={e => setPeriods(e.target.checked ? [...periods, d.fiscal_label].slice(-4) : periods.filter(p => p !== d.fiscal_label))}/>{d.fiscal_label}</label>)}</fieldset>
        {company.documents.length < 2 && <p className="section-copy">Only one call is available. Cross-quarter change needs more transcripts.</p>}
        <button className="button secondary" type="submit" disabled={busy || !periods.length}>{busy ? "Reading the evidence…" : "Check selected calls"}</button>
      </form> : <p className="section-copy">No single-company transcript coverage is available for this thesis.</p>}
      {error && <p role="alert" className="notice">{error}</p>}
      {results && <div className="suggestion-results">
        {results.map(r => <article key={r.period}><div className="section-head"><strong>{r.period}</strong><span className="signal">{r.relation === "supports" ? "May support" : r.relation === "challenges" ? "May challenge" : "Insufficient evidence"}</span></div><p>{r.reason}</p>
          {r.evidence.map((e,i) => <div className="suggestion-quote" key={i}><blockquote>{e.quote}</blockquote><small>{e.speaker} · {e.role} · Page {e.page}</small>{e.source_url?.startsWith("https://") && <a className="text-link" href={`${e.source_url}#page=${e.page}`} target="_blank" rel="noreferrer">Open source PDF ↗</a>}</div>)}
        </article>)}
        <button className="button secondary" disabled={saved || !results.some(r => r.evidence.length)} onClick={() => {
          const entries = results.filter(r => r.evidence.length).map(r => ({id:crypto.randomUUID(), quarter:r.period, addedAt:new Date().toISOString(), kind:"note" as const,
            text:`AI suggestion for review: ${r.relation}.\n\n` + r.evidence.map(e => `“${e.quote}”\n${e.symbol} · ${e.period} · ${e.speaker} (${e.role}) · Page ${e.page}\n${e.source_url || "Source URL unavailable"}`).join("\n\n")}));
          if (onSave(entries) !== false) setSaved(true);
        }}><ArrowDownToLine size={15}/>{saved ? "Added to your timeline" : "Keep quoted evidence"}</button>
      </div>}
    </div>
  </details>;
}

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Company } from "@/lib/types";

export default function CoverageMap() {
  const [data, setData] = useState<{ companies: Company[]; as_of: string } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch("/api/companies").then(r => { if (!r.ok) throw Error(); return r.json(); })
      .then(setData).catch(() => setFailed(true));
  }, []);
  const covered = data?.companies.filter(c => c.documents.length) || [];
  const periods = [...new Set(covered.flatMap(c => c.documents.map(d => d.fiscal_label)))].sort((a,b) => {
    const key = (s: string) => Number(s.match(/FY(\d+)/)?.[1] || 0) * 4 + Number(s.match(/Q(\d)/)?.[1] || 0);
    return key(a) - key(b);
  });
  return <section className="visual-panel coverage-map" aria-label="Transcript coverage map">
    <div className="section-head"><div><h2>Inside the library</h2><p>{data ? `${covered.length} companies · ${covered.reduce((n,c) => n + c.documents.length,0)} calls` : failed ? "Coverage unavailable" : "Loading transcripts…"}</p></div><span className="panel-tag">TRANSCRIPTS</span></div>
    {data ? <>
      <div className="table-scroll"><table className="coverage-table"><caption className="sr-only">Available transcripts by company and quarter</caption><thead><tr><th>Company</th>{periods.map(p => <th key={p}>{p}</th>)}</tr></thead><tbody>{covered.map(c => <tr key={c.symbol}><th scope="row">{c.symbol}</th>{periods.map(p => <td key={p}>{c.documents.some(d => d.fiscal_label === p) ? <Link className="coverage-cell available" href={`/ask?q=${encodeURIComponent(`What did ${c.name} discuss in ${p}?`)}`} aria-label={`Ask about ${c.symbol} ${p}`}>●<span className="sr-only"> Available</span></Link> : <span className="coverage-cell missing" aria-label="No transcript">—</span>}</td>)}</tr>)}</tbody></table></div>
      <div className="chart-footnote"><span>● Available &nbsp; — Not ingested</span><span>Snapshot · {data.as_of}</span></div>
    </> : <p className="section-copy">{failed ? "Coverage could not be loaded. Please refresh to retry." : "Checking the ingest snapshot."}</p>}
  </section>;
}

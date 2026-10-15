"use client";
import type { Thesis } from "@/lib/types";
export function EvidenceBalance({rows, onSelect}: {rows: Thesis[]; onSelect: (status: string) => void}) {
  const groups = ["Supports thesis", "Challenges thesis", "Unresolved"];
  const counts = groups.map(s => rows.filter(r => r.status === s).length);
  let offset = 0;
  return <section className="visual-panel" aria-label="Thesis assessment breakdown">
    <div className="section-head"><div><h2>Where you stand</h2><p>Your assessments, at a glance</p></div></div>
    <div className="balance-layout"><div className="donut-wrap"><svg viewBox="0 0 160 160" role="img" aria-label={groups.map((s,i) => `${counts[i]} ${s}`).join(', ')}><circle cx="80" cy="80" r="62" fill="none" stroke="var(--border)" strokeWidth="13"/>{counts.map((n,i) => {const length = rows.length ? n / rows.length * 100 : 0; const start=offset; offset+=length; return <circle key={groups[i]} className={`chart-series series-${i}`} cx="80" cy="80" r="62" pathLength="100" fill="none" strokeWidth="13" strokeDasharray={`${length} ${100-length}`} strokeDashoffset={-start} transform="rotate(-90 80 80)"/>;})}</svg><div><strong>{rows.length}</strong><span>theses</span></div></div>
    <div className="chart-legend">{groups.map((s,i) => <button key={s} onClick={() => onSelect(s)} aria-label={`Filter ${s}`}><i className={`series-bg-${i}`}/><span>{["Supporting", "Challenging", "Unresolved"][i]}</span><b>{counts[i]}</b></button>)}</div></div>
  </section>;
}
export function EvidenceProgress({row}: {row: Thesis}) {
  return <div className="evidence-progress" aria-label="Evidence collection progress"><span className={row.evidence.length ? "complete" : ""}><i/>{row.evidence.length} evidence entries</span><span className={row.reviewed ? "complete" : ""}><i/>{row.reviewed ? "Review complete" : "Review pending"}</span></div>;
}

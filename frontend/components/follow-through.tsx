"use client";
import { useState } from 'react';
import { ArrowRight, GitCompareArrows, ScanLine } from 'lucide-react';
import type { FollowThrough, MonitoredCompany } from '@/lib/monitor';

export default function FollowThroughPanel({company,onOpen}:{company:MonitoredCompany;onOpen:(trail:FollowThrough)=>void}) {
  const trails=company.follow_through||[],[selected,setSelected]=useState('');
  const trail=trails.find(t=>t.id===selected)||trails[trails.length-1];
  return <section className="visual-panel follow-through" aria-label="Follow-through">
    <div className="section-head"><div><span className="follow-label"><GitCompareArrows size={15}/> FOLLOW-THROUGH</span><h2>What followed the announcement?</h2></div><span className="panel-tag">{company.symbol}</span></div>
    {!trail?<div className="follow-empty"><ScanLine size={22}/><p>No linked announcement and outcome in the covered calls.</p><span>Current matching covers salary increases in consecutive quarters.</span></div>:<>
      {trails.length>1&&<div className="follow-periods" aria-label="Follow-through periods">{trails.map(t=><button key={t.id} aria-pressed={t.id===trail.id} onClick={()=>setSelected(t.id)}>{t.before.period} <ArrowRight size={12}/> {t.after.period}</button>)}</div>}
      <div className="follow-path">
        <button className="follow-step" onClick={()=>onOpen(trail)}><span className="follow-stage">01 · {trail.before.period}</span><small>Management announced</small><strong>{trail.topic}</strong><span className="text-link">Read earlier statement <ArrowRight size={13}/></span></button>
        <ArrowRight className="follow-arrow" size={22}/>
        <button className="follow-step" onClick={()=>onOpen(trail)}><span className="follow-stage">02 · {trail.after.period}</span><small>Management later reported</small><strong>{trail.outcome_label}</strong><span className="text-link">Read later statement <ArrowRight size={13}/></span></button>
        <div className="follow-result"><span>{trail.wage_impact_bps!==null?'Reported wage impact':'Operating margin'}</span><strong>{trail.wage_impact_bps!==null?`${trail.wage_impact_bps} bps`:trail.metric?.raw||'—'}</strong><small>{trail.wage_impact_bps!==null?'A cost impact, not the net margin change':trail.impact_source&&trail.metric?.reported_change_bps!==null?`${trail.metric!.reported_change_bps} bps net QoQ · wage pressure cited`:trail.metric?.basis||'No unambiguous figure'}</small></div>
      </div>
      <div className="follow-footer"><span>Salary-increase matching · review required</span><button className="button secondary" onClick={()=>onOpen(trail)}>Review & save evidence <ArrowRight size={15}/></button></div>
    </>}
  </section>;
}

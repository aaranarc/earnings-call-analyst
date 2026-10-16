import { readWorkspace, saveWorkspace } from './workspace';
import type { Thesis } from './types';
import type { GrowthProject } from './growth';
export type SourceQuote = {source_type?:string; period:string; quote:string; speaker:string; page:number; source_url:string; source_sha256:string};
export type MetricFact = SourceQuote & {id:string; value:number; raw:string; basis:string; period_end:string; reported_change_bps:number|null};
export type MonitorSignal = {id:string; kind:string; direction:string; title:string; change_bps:number; period:string; current:MetricFact; previous:MetricFact|null; attribution:string; arithmetic_matches:boolean};
export type FollowThrough = {id:string; topic:string; before:SourceQuote; after:SourceQuote; metric:MetricFact|null; impact_source:MetricFact|null; wage_impact_bps:number|null; link_basis:string; outcome_label:string; verdict:string};
export type ReportedRange = SourceQuote & {raw:string; lower:number; upper:number};
export type ResultPeriod = {period:string; period_end:string; call_date:string|null; source_url:string; source_sha256:string; reported_range?:ReportedRange|null};
export type MonitoredCompany = {symbol:string; name:string; sector:string; market:string; call_count:number; latest_period:string; facts:MetricFact[]; commentary:SourceQuote[]; signals:MonitorSignal[]; gap_before:string[]; follow_through?:FollowThrough[]; metric_label?:string; result_periods?:ResultPeriod[]};
export type MonitorReport = {version:number; as_of:string; corpus_hash:string; update_policy:string; companies:MonitoredCompany[]};
const SLOT='quantrag.favourites.v1';
export function keepGrowth(project:GrowthProject) {
  return keepObservation({name:project.symbol,symbol:project.symbol},
    'growth-'+project.id,`Growth Payoff: ${project.name}`,
    [...(project.amount_source?[project.amount_source]:[]),...project.milestones]);
}
function validFavourites(value:unknown):string[] {
  if (!Array.isArray(value)||value.length>100||!value.every(x=>typeof x==='string'&&/^[A-Z0-9.-]{1,20}$/.test(x))||new Set(value).size!==value.length) throw Error('Saved favourites could not be read. Existing data is unchanged.');
  return value;
}
export function readFavourites():string[] {const value=localStorage.getItem(SLOT);return value===null?[]:validFavourites(JSON.parse(value));}
export function saveFavourites(symbols:string[]) {readFavourites();localStorage.setItem(SLOT,JSON.stringify(validFavourites(symbols)));}
export function quarterIndex(label:string) {const m=label.match(/^Q([1-4]) FY(\d{2})$/);return m?Number(m[2])*4+Number(m[1])-1:0;}
export function chartPeriods(facts:Pick<MetricFact,"period">[]) {
  if(!facts.length)return [];
  const first=quarterIndex(facts[0].period),last=quarterIndex(facts[facts.length-1].period);
  // Keep a bounded view; a blank slot is missing coverage, never an interpolated observation.
  return Array.from({length:Math.min(last-first+1,8)},(_,i)=>{const n=Math.max(first,last-7)+i;return `Q${n%4+1} FY${String(Math.floor(n/4)).padStart(2,'0')}`;});
}
export function keepSignal(company:MonitoredCompany,signal:MonitorSignal) {
  return keepObservation(company,'monitor-'+signal.id,`${signal.title} (${signal.period})`,[...(signal.previous?[signal.previous]:[]),signal.current]);
}
export function trailQuotes(trail:FollowThrough):SourceQuote[] {return [trail.before,trail.after,...(trail.metric?[trail.metric]:[])];}
export function keepTrail(company:MonitoredCompany,trail:FollowThrough) {
  return keepObservation(company,'followthrough-'+trail.id,`Follow-through: ${trail.topic} (${trail.before.period} → ${trail.after.period})`,trailQuotes(trail));
}
function keepObservation(company:Pick<MonitoredCompany,'name'|'symbol'>,id:string,title:string,quotes:SourceQuote[]) {
  const rows=readWorkspace();
  if(rows.some(r=>r.id===id))return id;
  const row:Thesis={id,company:company.name,symbol:company.symbol,title:`${company.symbol}: ${title}`,description:'A source-linked observation, saved for source review. Not a causal conclusion.',status:'Unresolved',reviewed:false,sample:false,before:'',after:'',beforeQuarter:'',afterQuarter:'',note:'',evidence:quotes.map((q,i)=>({id:`${id}-${i}`,quarter:q.period,kind:'note',addedAt:new Date().toISOString(),text:`${q.speaker}, ${q.period}, PDF page ${q.page}:\n“${q.quote}”\nSource: ${q.source_url}#page=${q.page}\nPDF SHA-256: ${q.source_sha256}`}))};
  saveWorkspace([row,...rows]);return id;
}

import { readWorkspace, saveWorkspace } from './workspace';
import type { Thesis } from './types';
export type SourceQuote = {period:string; quote:string; speaker:string; page:number; source_url:string; source_sha256:string};
export type MetricFact = SourceQuote & {id:string; value:number; raw:string; basis:string; period_end:string; reported_change_bps:number|null};
export type MonitorSignal = {id:string; kind:string; direction:string; title:string; change_bps:number; period:string; current:MetricFact; previous:MetricFact|null; attribution:string; arithmetic_matches:boolean};
export type MonitoredCompany = {symbol:string; name:string; sector:string; market:string; call_count:number; latest_period:string; facts:MetricFact[]; commentary:SourceQuote[]; signals:MonitorSignal[]; gap_before:string[]};
export type MonitorReport = {version:number; as_of:string; corpus_hash:string; update_policy:string; companies:MonitoredCompany[]};
const SLOT='quantrag.favourites.v1';
function validFavourites(value:unknown):string[] {
  if (!Array.isArray(value)||value.length>100||!value.every(x=>typeof x==='string'&&/^[A-Z0-9.-]{1,20}$/.test(x))||new Set(value).size!==value.length) throw Error('Saved favourites could not be read. Existing data is unchanged.');
  return value;
}
export function readFavourites():string[] {const value=localStorage.getItem(SLOT);return value===null?[]:validFavourites(JSON.parse(value));}
export function saveFavourites(symbols:string[]) {readFavourites();localStorage.setItem(SLOT,JSON.stringify(validFavourites(symbols)));}
export function quarterIndex(label:string) {const m=label.match(/^Q([1-4]) FY(\d{2})$/);return m?Number(m[2])*4+Number(m[1])-1:0;}
export function chartPeriods(facts:MetricFact[]) {
  if(!facts.length)return [];
  const first=quarterIndex(facts[0].period),last=quarterIndex(facts[facts.length-1].period);
  // Keep a bounded view; a blank slot is missing coverage, never an interpolated observation.
  return Array.from({length:Math.min(last-first+1,8)},(_,i)=>{const n=Math.max(first,last-7)+i;return `Q${n%4+1} FY${String(Math.floor(n/4)).padStart(2,'0')}`;});
}
export function keepSignal(company:MonitoredCompany,signal:MonitorSignal) {
  const rows=readWorkspace(),id='monitor-'+signal.id;
  if(rows.some(r=>r.id===id))return id;
  const quotes:SourceQuote[]=[...(signal.previous?[signal.previous]:[]),signal.current];
  const row:Thesis={id,company:company.name,symbol:company.symbol,title:`${company.symbol}: ${signal.title} (${signal.period})`,description:'A company-reported observation, saved for source review. Not a causal conclusion.',status:'Unresolved',reviewed:false,sample:false,before:'',after:'',beforeQuarter:'',afterQuarter:'',note:'',evidence:quotes.map((q,i)=>({id:`${id}-${i}`,quarter:q.period,kind:'note',addedAt:new Date().toISOString(),text:`${q.speaker}, ${q.period}, PDF page ${q.page}:\n“${q.quote}”\nSource: ${q.source_url}#page=${q.page}\nPDF SHA-256: ${q.source_sha256}`}))};
  saveWorkspace([row,...rows]);return id;
}

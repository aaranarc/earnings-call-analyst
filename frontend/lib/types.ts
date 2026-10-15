export type Status = "Supports thesis" | "Challenges thesis" | "Unresolved";
export type Evidence = {
  id: string;
  text: string;
  quarter: string;
  addedAt: string | null;
  kind: "note" | "answer" | "legacy";
};
export type Thesis = {
  evidence: Evidence[];
  id: string;
  company: string;
  symbol: string;
  title: string;
  description: string;
  status: Status;
  before: string;
  after: string;
  beforeQuarter: string;
  afterQuarter: string;
  note: string;
  reviewed: boolean;
  sample: boolean;
};
export type Company = {
  symbol: string;
  name: string;
  sector: string;
  documents: { fiscal_label: string; chunks: number; source_url?: string }[];
};
export type Hit = {
  chunk_id: number;
  symbol: string;
  company: string;
  fiscal_label: string;
  speaker: string;
  role: string;
  page: number;
  text: string;
  source_url?: string;
  scores: Record<string, number>;
  section?: string;
  context?: { position: "before" | "after"; chunk_id: number; speaker: string; role: string; section: string; page: number; text: string }[];
};
export type NumberCheck = {
  where: string;
  start: number;
  end: number;
  raw: string;
  status: string;
  source?: { raw: string; chunk_id: number } | null;
};
export type Answer = {
  question: string;
  answer_markdown: string;
  refused: boolean;
  refusal_reason: string | null;
  hits: Hit[];
  citations: { n: number; chunk_id: number }[];
  numbers: NumberCheck[];
  comparison_table:
    | {
        metric: string;
        cells: { company: string; value: string; citations: number[] }[];
      }[]
    | null;
  route: { kind: string; companies: string[]; periods: string[] };
  timing_s: Record<string, number>;
};
export type EvalReport = {
  status: string;
  metrics: { name: string; value: number; definition: string }[];
  ablations: {
    name: string;
    hit_at_5: number | null;
    mrr_at_10: number | null;
  }[];
  failure_cases: { question: string; finding: string }[];
  agreement: { kappa: number | null; sample_size: number } | null;
  last_run: { date: string; commit: string } | null;
};

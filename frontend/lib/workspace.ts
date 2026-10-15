import type { Evidence, Thesis } from "./types";
const legacySamples = [
  {
    id: "sample-1",
    company: "Tata Consultancy Services",
    symbol: "TCS",
    title: "AI pilots are becoming real revenue",
    description:
      "Watch for a shift from experimentation to paid, scaled deployments.",
    status: "Supports thesis",
    before:
      "Client conversations are centred on pilots and identifying the right use cases.",
    after:
      "Several pilot engagements have moved into paid production deployments.",
    beforeQuarter: "Earlier quarter",
    afterQuarter: "Later quarter",
    note: "Check whether the next call separates AI revenue from the wider cloud business.",
    reviewed: false,
    sample: true,
  },
  {
    id: "sample-2",
    company: "Infosys",
    symbol: "INFY",
    title: "Margins recover as utilisation improves",
    description:
      "Look for evidence that operating efficiency is translating into margins.",
    status: "Challenges thesis",
    before:
      "We expect better utilisation to support margin expansion over the coming quarters.",
    after:
      "Improved utilisation was offset by higher delivery costs. Margins did not expand.",
    beforeQuarter: "Earlier quarter",
    afterQuarter: "Later quarter",
    note: "Separate temporary wage effects from structural delivery costs.",
    reviewed: false,
    sample: true,
  },
  {
    id: "sample-3",
    company: "HDFC Bank",
    symbol: "HDFCBANK",
    title: "Deposit growth catches up with lending",
    description:
      "Track management’s progress towards a more balanced funding mix.",
    status: "Unresolved",
    before: "Growing the deposit franchise remains a priority for the year.",
    after:
      "The later excerpt does not provide a comparable deposit growth measure.",
    beforeQuarter: "Earlier quarter",
    afterQuarter: "Later quarter",
    note: "Missing evidence is not a missed commitment.",
    reviewed: false,
    sample: true,
  },
];

const statuses = ["Supports thesis", "Challenges thesis", "Unresolved"];
const fields = ["id", "company", "symbol", "title", "description", "before", "after", "beforeQuarter", "afterQuarter", "note"];
const STORAGE_SLOT = "quantrag.theses.v2";
function legacyEvidence(row: Record<string, unknown>): Evidence[] {
  return ["before", "after"].filter(k => String(row[k]).trim()).map(k => ({
    id: `${row.id}-${k}`, text: String(row[k]), quarter: String(row[k + "Quarter"]), addedAt: null, kind: "legacy",
  }));
}
function validateRows(value: unknown, legacy = false): Thesis[] {
  if (!Array.isArray(value) || value.length > 500) throw Error("Invalid workspace: expected at most 500 theses.");
  const ids = new Set<string>();
  return value.map(row => {
    if (!row || typeof row !== "object" || !fields.every(k => typeof row[k] === "string" && row[k].length <= 100000) ||
      !row.id || ids.has(row.id) || !statuses.includes(row.status) || typeof row.reviewed !== "boolean" || row.sample !== false)
      throw Error("Invalid workspace: thesis fields or duplicate IDs. Existing research is unchanged.");
    ids.add(row.id);
    const evidence = legacy ? legacyEvidence(row) : row.evidence;
    const evidenceIds = new Set<string>();
    if (!Array.isArray(evidence) || evidence.length > 1000 || !evidence.every(e => {
      if (!e || typeof e.id !== "string" || !e.id || evidenceIds.has(e.id) || typeof e.text !== "string" || !e.text.trim() || e.text.length > 100000 ||
        typeof e.quarter !== "string" || e.quarter.length > 200 || !["note", "answer", "legacy"].includes(e.kind) ||
        !(e.addedAt === null || (typeof e.addedAt === "string" && Number.isFinite(Date.parse(e.addedAt))))) return false;
      evidenceIds.add(e.id); return true;
    })) throw Error("Invalid evidence timeline. Existing research is unchanged.");
    return { ...Object.fromEntries(fields.map(k => [k, row[k]])), status: row.status, reviewed: row.reviewed, sample: false,
      evidence: evidence.map(e => ({id: e.id, text: e.text, quarter: e.quarter, addedAt: e.addedAt, kind: e.kind})) } as Thesis;
  });
}
export const sampleTheses: Thesis[] = legacySamples.map(row => ({...row, status: row.status as Thesis["status"], evidence: legacyEvidence(row)}));
export function readWorkspace(): Thesis[] {
  const current = localStorage.getItem(STORAGE_SLOT);
  if (current !== null) return validateRows(JSON.parse(current));
  const saved = localStorage.getItem("quantrag.theses.v1");
  if (!saved) return [];
  const migrated = validateRows(JSON.parse(saved), true);
  // Preserve v1 as a recovery copy; do not erase it on migration.
  saveWorkspace(migrated);
  return migrated;
}
export function saveWorkspace(rows: Thesis[]) {
  // Never replace unreadable stored research with an empty/new workspace.
  const existing = localStorage.getItem(STORAGE_SLOT);
  if (existing !== null) validateRows(JSON.parse(existing));
  localStorage.setItem(STORAGE_SLOT, JSON.stringify(validateRows(rows)));
}
export function parseImport(text: string): Thesis[] {
  if (new Blob([text]).size > 5 * 1024 * 1024) throw Error("Choose a workspace file smaller than 5 MB.");
  const data = JSON.parse(text);
  if (!data || ![1, 2].includes(data.version)) throw Error("Unsupported workspace version.");
  return validateRows(data.theses, data.version === 1);
}
export function mergeImport(existing: Thesis[], incoming: Thesis[]): Thesis[] {
  const result = [...existing];
  for (const row of incoming) {
    const match = result.find(r => r.id === row.id);
    if (match && JSON.stringify(match) === JSON.stringify(row)) continue;
    // A conflicting ID becomes a separate copy, never a destructive overwrite.
    result.push(match ? {...row, id: crypto.randomUUID(), title: `${row.title} (imported copy)`} : row);
  }
  return validateRows(result);
}
export function exportWorkspace(rows: Thesis[]) {
  const blob = new Blob([JSON.stringify({version: 2, theses: rows}, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = "quantrag-theses.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

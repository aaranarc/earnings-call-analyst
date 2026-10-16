import type { SourceQuote } from "./monitor";
export type Milestone = SourceQuote & {
  period_end: string;
  stage: string;
  label: string;
  value_text: string | null;
};
export type GrowthProject = {
  id: string;
  symbol: string;
  name: string;
  category: string;
  amount: number | null;
  amount_label: string;
  amount_source: SourceQuote | null;
  outcome: string;
  missing: string;
  payoff_status: string;
  milestones: Milestone[];
  operating_metric?: {
    label: string;
    unit: string;
    before: number;
    after: number;
    after_is_lower_bound: boolean;
    before_label: string;
    after_label: string;
    source: SourceQuote;
  } | null;
};
export type GrowthReport = {
  version: number;
  as_of: string;
  methodology: string;
  projects: GrowthProject[];
};
export type Scenario = {
  capital: number;
  annualReturn: number;
  rampYears: number;
  startYear: number;
};
// A sensitivity calculation, not a trained prediction. Capital is deployed in full
// at time zero; returns ramp linearly after the chosen first operating year.
// No compounding, cash-flow conversion or whole-company growth is assumed.
export function projectPayoff(input: Scenario, years: number) {
  if (
    ![3, 5].includes(years) ||
    !Number.isFinite(input.capital) ||
    input.capital <= 0 ||
    input.capital > 1e7 ||
    !Number.isFinite(input.annualReturn) ||
    input.annualReturn < -20 ||
    input.annualReturn > 50 ||
    !Number.isInteger(input.rampYears) ||
    input.rampYears < 1 ||
    input.rampYears > 5 ||
    !Number.isInteger(input.startYear) ||
    input.startYear < 1 ||
    input.startYear > 5
  )
    return null;
  return Array.from({ length: years + 1 }, (_, year) => ({
    year,
    profit:
      ((input.capital * input.annualReturn) / 100) *
      Math.min(1, Math.max(0, (year - input.startYear + 1) / input.rampYears)),
  }));
}

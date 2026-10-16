"use client";
import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BookmarkPlus,
  Check,
  CircleHelp,
  ExternalLink,
  Factory,
  GitCompareArrows,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import Shell from "./shell";
import { chartScale } from "@/lib/chart-scale";
import Dialog from "./dialog";
import type { SourceQuote } from "@/lib/monitor";
import { keepGrowth } from "@/lib/monitor";
import { projectPayoff } from "@/lib/growth";
import type { GrowthProject, GrowthReport } from "@/lib/growth";

const money = (n: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(n);
export default function GrowthPayoff({ report }: { report: GrowthReport }) {
  const [id, setId] = useState("hul-minimalist"),
    [filter, setFilter] = useState("All projects");
  const project =
    report.projects.find((p) => p.id === id) || report.projects[0];
  const [detail, setDetail] = useState<{
      title: string;
      quotes: SourceQuote[];
    } | null>(null),
    [saved, setSaved] = useState<string[]>([]),
    [error, setError] = useState("");
  const [enabled, setEnabled] = useState(false),
    [capital, setCapital] = useState(String(project.amount ?? "")),
    [capitalEdited, setCapitalEdited] = useState(false),
    [rate, setRate] = useState(10),
    [ramp, setRamp] = useState(3),
    [start, setStart] = useState(1),
    [years, setYears] = useState(3),
    [point, setPoint] = useState(3),
    [hovered, setHovered] = useState<number | null>(null);
  const operating = project.operating_metric;
  const amount = capital.trim() === "" ? null : Number(capital);
  const points = enabled
    ? projectPayoff(
        {
          capital: amount ?? 0,
          annualReturn: rate,
          rampYears: ramp,
          startYear: start,
        },
        years,
      )
    : null;
  const active = points?.[Math.min(point, years)],
    chartPoint = points?.[Math.min(hovered ?? point, years)],
    last = points?.[years];
  const scale = chartScale(points?.map(p => p.profit) ?? [0, 1], true),
    x = (year: number) => 58 + (year / years) * 650,
    y = (value: number) => 218 - ((value - scale.min) / (scale.max - scale.min)) * 170;
  function choose(p: GrowthProject) {
    setId(p.id);
    setEnabled(false);
    setCapital(String(p.amount ?? ""));
    setCapitalEdited(false);
    setHovered(null);
    setError("");
    setRate(10);
    setRamp(3);
    setStart(1);
    setPoint(3);
    setYears(3);
  }
  function open(title: string, quotes: SourceQuote[]) {
    setError("");
    setDetail({ title, quotes });
  }
  function save() {
    try {
      keepGrowth(project);
      setSaved([...saved, project.id]);
      setError("");
    } catch {
      setError("Evidence could not be saved. Existing research is unchanged.");
    }
  }
  return (
    <Shell>
      <div className="gp-heading">
        <div>
          <span className="gp-eyebrow">
            <GitCompareArrows size={15} /> INVESTMENT → EXECUTION → PAYOFF
          </span>
          <h1>Growth Payoff</h1>
          <p>Is the money going in building a stronger business?</p>
        </div>
        <span className="panel-tag">Evidence snapshot · {report.as_of}</span>
      </div>
      <div className="gp-overview">
        <div>
          <Factory size={19} />
          <strong>{report.projects.length}</strong>
          <span>tracked investments</span>
          <div
            className="gp-overview-bars"
            aria-label="Sourced milestones per project"
          >
            {report.projects.map((p) => (
              <i
                key={p.id}
                title={`${p.name}: ${p.milestones.length} milestones`}
                style={{ height: `${p.milestones.length * 7}px` }}
              />
            ))}
          </div>
        </div>
        <div>
          <GitCompareArrows size={19} />
          <strong>
            {report.projects.reduce((n, p) => n + p.milestones.length, 0)}
          </strong>
          <span>sourced milestones</span>
          <div className="gp-overview-dots" aria-hidden="true">
            {report.projects
              .flatMap((p) => p.milestones)
              .map((_, i) => (
                <i key={i} />
              ))}
          </div>
        </div>
        <div>
          <CircleHelp size={19} />
          <strong>Open</strong>
          <span>financial payoff not established</span>
        </div>
      </div>
      <div className="gp-layout">
        <aside className="gp-projects">
          <div className="section-head">
            <h2>Where capital is going</h2>
          </div>
          <div className="gp-filters" aria-label="Project categories">
            {["All projects", "Acquisition", "Capacity expansion"].map((f) => (
              <button
                key={f}
                aria-pressed={filter === f}
                onClick={() => {
                  setFilter(f);
                  if (f !== "All projects" && project.category !== f)
                    choose(report.projects.find((p) => p.category === f)!);
                }}
              >
                {f === "Capacity expansion"
                  ? "Capacity"
                  : f === "Acquisition"
                    ? "Acquisitions"
                    : f}
              </button>
            ))}
          </div>
          {report.projects
            .filter((p) => filter === "All projects" || p.category === filter)
            .map((p) => (
              <button
                className={`gp-project ${p.id === project.id ? "active" : ""}`}
                key={p.id}
                aria-pressed={p.id === project.id}
                onClick={() => choose(p)}
              >
                <span>
                  {p.symbol}
                  <ArrowUpRight size={15} />
                </span>
                <strong>{p.name}</strong>
                <small>{p.category}</small>
                <div className="gp-mini-track" aria-hidden="true">
                  {[0, 1, 2, 3].map((i) => (
                    <i
                      key={i}
                      className={
                        i < Math.min(p.milestones.length, 3) ? "filled" : ""
                      }
                    />
                  ))}
                </div>
                <small>{p.outcome}</small>
              </button>
            ))}
          <p className="gp-pilot-note">
            Reviewed pilot · 3 companies. Missing projects are not a negative
            signal.
          </p>
        </aside>
        <div className="gp-main">
          <section
            className="visual-panel gp-evidence"
            aria-label="Investment evidence"
          >
            <div className="section-head">
              <div>
                <span className="monitor-kicker">
                  {project.symbol} · {project.category}
                </span>
                <h2>{project.name}</h2>
              </div>
              <button
                className="button secondary"
                onClick={() =>
                  open(project.name + " · Evidence", project.milestones)
                }
              >
                View sources <ExternalLink size={14} />
              </button>
            </div>
            <div className="gp-amount-row">
              <button
                className="gp-amount"
                disabled={!project.amount_source}
                onClick={() =>
                  project.amount_source &&
                  open(project.amount_label, [project.amount_source])
                }
              >
                <span>{project.amount_label}</span>
                <strong>
                  {project.amount === null
                    ? "Not extracted"
                    : `₹${money(project.amount)} cr`}
                </strong>
                <small>
                  {project.amount_source?.period || "No amount assumed"}{" "}
                  {project.amount_source && <ArrowUpRight size={13} />}
                </small>
              </button>
              <div className="gp-payoff-status">
                <span>Financial payoff</span>
                <strong>{project.payoff_status}</strong>
                <small>Execution progress ≠ investment return</small>
              </div>
            </div>
            <div className="gp-timeline" aria-label="Investment milestones">
              {project.milestones.map((m, i) => (
                <button
                  className="gp-milestone"
                  key={`${m.period}-${i}`}
                  onClick={() => open(m.stage + " · " + m.period, [m])}
                >
                  <span className="gp-node">{i + 1}</span>
                  <small>{m.period}</small>
                  <span>{m.stage}</span>
                  <strong>{m.label}</strong>
                  <small className="text-link">
                    Source · p. {m.page} <ArrowUpRight size={12} />
                  </small>
                </button>
              ))}
              <div className="gp-milestone gp-next">
                <span className="gp-node">
                  <CircleHelp size={16} />
                </span>
                <small>Still to establish</small>
                <span>Financial payoff</span>
                <strong>Profit & cash returns</strong>
                <small>Evidence needed</small>
              </div>
            </div>
            {operating && (
              <button
                className="gp-operating"
                onClick={() =>
                  open("Distribution reach · management reported", [
                    operating.source,
                  ])
                }
              >
                <div>
                  <span>
                    {operating.label} · {operating.unit}
                  </span>
                  <small>Operating progress · not financial return</small>
                </div>
                <div className="gp-reach-bars">
                  <span>
                    <i
                      style={{
                        width: `${(operating.before / operating.after) * 100}%`,
                      }}
                    />
                    <b>{money(operating.before)}</b>
                    <small>{operating.before_label}</small>
                  </span>
                  <span>
                    <i style={{ width: "100%" }} />
                    <b>
                      {money(operating.after)}
                      {operating.after_is_lower_bound ? "+" : ""}
                    </b>
                    <small>{operating.after_label}</small>
                  </span>
                </div>
                <ArrowUpRight size={16} />
              </button>
            )}
            <div className="gp-evidence-footer">
              <span>
                <CircleHelp size={16} />
                {project.missing}
              </span>
              <button
                className="text-link"
                onClick={save}
                disabled={saved.includes(project.id)}
              >
                {saved.includes(project.id) ? (
                  <Check size={15} />
                ) : (
                  <BookmarkPlus size={15} />
                )}{" "}
                {saved.includes(project.id)
                  ? "Saved to research"
                  : "Save evidence"}
              </button>
            </div>
            {error && (
              <p role="alert" className="notice">
                {error}
              </p>
            )}
          </section>
          <section
            className="visual-panel gp-scenario"
            aria-label="Investment payoff scenario"
          >
            <div className="section-head">
              <div>
                <span className="monitor-kicker">
                  <SlidersHorizontal size={13} /> ASSUMPTION EXPLORER
                </span>
                <h2>What could this investment earn?</h2>
              </div>
              <div className="gp-horizon" aria-label="Scenario horizon">
                {[3, 5].map((n) => (
                  <button
                    key={n}
                    aria-pressed={years === n}
                    onClick={() => {
                      setYears(n);
                      setPoint(n);
                    }}
                  >
                    {n} years
                  </button>
                ))}
              </div>
            </div>
            <div className="gp-chart-top">
              <div>
                <span>Annual incremental operating profit · ₹ crore</span>
                <strong>
                  {active ? `₹${money(active.profit)} cr` : "—"}
                  <small>
                    {active
                      ? `Scenario year ${active.year}`
                      : "Awaiting assumptions"}
                  </small>
                </strong>
              </div>
              <span className="gp-scenario-badge">
                {enabled
                  ? "Illustrative · not a forecast"
                  : "Company forecast unavailable"}
              </span>
            </div>
            <div className="gp-chart">
              <svg
                viewBox="0 0 760 270"
                onMouseLeave={() => setHovered(null)}
                role="img"
                aria-label={
                  last
                    ? `Illustrative annual operating profit reaches ${money(last.profit)} crore in year ${years}; not a company forecast.`
                    : "Scenario chart. Choose assumptions to calculate potential investment payoff."
                }
              >
                {scale.ticks.map((tick) => (
                  <g key={tick}>
                    <line
                      x1="58"
                      x2="708"
                      y1={y(tick)}
                      y2={y(tick)}
                      stroke="var(--border)"
                      strokeDasharray="4 6"
                    />
                    <text x="48" y={y(tick) + 4} textAnchor="end">
                      {enabled ? money(tick) : "—"}
                    </text>
                  </g>
                ))}
                {Array.from({ length: years + 1 }, (_, i) => (
                  <text key={i} x={x(i)} y="249" textAnchor="middle">
                    {i === 0 ? "Start" : `Year ${i}`}
                  </text>
                ))}
                {points && (
                  <>
                    <path
                      d={`M ${points.map((p) => `${x(p.year)},${y(p.profit)}`).join(" L ")} L 708,${y(0)} L 58,${y(0)} Z`}
                      fill="var(--primary)"
                      opacity="0.07"
                    />
                    <path
                      d={`M ${points.map((p) => `${x(p.year)},${y(p.profit)}`).join(" L ")}`}
                      fill="none"
                      stroke="var(--primary)"
                      strokeWidth="3"
                      strokeDasharray="7 5"
                    />
                    {chartPoint && (
                      <line
                        x1={x(chartPoint.year)}
                        x2={x(chartPoint.year)}
                        y1="40"
                        y2="222"
                        stroke="var(--muted)"
                        strokeDasharray="3 5"
                      />
                    )}
                    {points.map((p) => (
                      <g key={p.year} onMouseEnter={() => setHovered(p.year)}>
                        <rect
                          x={Math.max(50, x(p.year) - 650 / years / 2)}
                          y="40"
                          width={650 / years}
                          height="185"
                          fill="transparent"
                        />
                        <circle
                          cx={x(p.year)}
                          cy={y(p.profit)}
                          r={p.year === (hovered ?? point) ? 6 : 4}
                          fill="var(--primary)"
                        />
                      </g>
                    ))}
                    {chartPoint && (
                      <g
                        transform={`translate(${Math.min(630, Math.max(58, x(chartPoint.year) - 60))},15)`}
                      >
                        <rect
                          width="125"
                          height="24"
                          rx="6"
                          fill="var(--bg)"
                          stroke="var(--border)"
                        />
                        <text x="62" y="16" textAnchor="middle">
                          Y{chartPoint.year} · ₹{money(chartPoint.profit)} cr
                        </text>
                      </g>
                    )}
                  </>
                )}
              </svg>
              {!enabled && (
                <div className="gp-chart-empty">
                  <TrendingUp size={28} />
                  <strong>Explore the payoff, not a price target.</strong>
                  <button
                    className="button primary"
                    onClick={() => setEnabled(true)}
                  >
                    Build a scenario <ArrowRight size={15} />
                  </button>
                </div>
              )}
            </div>
            {enabled && (
              <>
                <div
                  className="gp-year-points"
                  aria-label="Inspect scenario years"
                >
                  {points?.map((p) => (
                    <button
                      key={p.year}
                      aria-pressed={point === p.year}
                      onClick={() => setPoint(p.year)}
                    >
                      Year {p.year}
                      <strong>₹{money(p.profit)} cr</strong>
                    </button>
                  ))}
                </div>
                <div className="gp-controls">
                  <label>
                    Capital deployed · ₹ crore
                    <input
                      aria-label="Scenario capital in crore"
                      type="number"
                      min="1"
                      max="10000000"
                      value={capital}
                      onChange={(e) => {
                        setCapital(e.target.value);
                        setCapitalEdited(true);
                      }}
                    />
                    <small>
                      {!capitalEdited && project.amount !== null
                        ? `${project.amount_label}; scenario assumes full deployment at start.`
                        : "Your assumption · not a reported payout"}
                    </small>
                  </label>
                  <label>
                    Annual operating return at full ramp <b>{rate}%</b>
                    <input
                      aria-label="Annual operating return"
                      type="range"
                      min="-20"
                      max="50"
                      step="1"
                      value={rate}
                      onChange={(e) => setRate(Number(e.target.value))}
                    />
                    <small>
                      Illustrative starting assumption · not estimated from
                      filings
                    </small>
                  </label>
                  <label>
                    First operating year <b>Year {start}</b>
                    <input
                      aria-label="First operating year"
                      type="range"
                      min="1"
                      max="5"
                      value={start}
                      onChange={(e) => setStart(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Years to full ramp <b>{ramp}</b>
                    <input
                      aria-label="Years to full ramp"
                      type="range"
                      min="1"
                      max="5"
                      value={ramp}
                      onChange={(e) => setRamp(Number(e.target.value))}
                    />
                  </label>
                </div>
                {!points && (
                  <p className="notice" role="alert">
                    Enter positive capital up to ₹1,00,00,000 crore to calculate
                    this scenario.
                  </p>
                )}
                <details className="gp-model">
                  <summary>Calculation & limits</summary>
                  <p>
                    Annual operating profit = capital × assumed annual operating
                    return × ramp fraction. Ramp starts in the first operating
                    year and increases evenly to 100%. Years run from assumed
                    deployment, not today's calendar date. No compounding or
                    reinvestment. Defaults (10% return, year 1 start, 3-year
                    ramp) are illustrative. This excludes taxes, financing, cash
                    conversion, inflation, maintenance spending and changes
                    elsewhere in the business. It is not cash flow, ROI
                    validation, a confidence interval or a whole-company
                    forecast.
                  </p>
                </details>
              </>
            )}
            <div className="gp-scenario-foot">
              <span>
                <i /> Dashed line = assumptions
              </span>
              <span>
                Whole-company projection withheld · insufficient financial
                history
              </span>
            </div>
          </section>
          <Link
            className="gp-question"
            href={`/ask?q=${encodeURIComponent(`What did ${project.symbol} report about ${project.name}? Cite the source and distinguish plans from actual results.`)}`}
          >
            <span>
              <strong>Go deeper into {project.name}</strong>
              <small>Ask the analyst about the original statements</small>
            </span>
            <ArrowRight size={20} />
          </Link>
        </div>
      </div>
      {detail && (
        <Dialog title={detail.title} drawer onClose={() => setDetail(null)}>
          <div className="monitor-detail">
            <p className="monitor-detail-note">
              Management-reported evidence. These excerpts do not independently
              establish project returns or causality.
            </p>
            {detail.quotes.map((q, i) => (
              <article className="monitor-source" key={i}>
                <div className="monitor-source-meta">
                  <b>{q.period}</b>
                  <span>
                    {q.speaker} · PDF p. {q.page}
                  </span>
                </div>
                <blockquote>{q.quote}</blockquote>
                <a
                  className="text-link"
                  href={`${q.source_url}#page=${q.page}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open source PDF <ExternalLink size={14} />
                </a>
              </article>
            ))}
            <button
              className="button primary"
              disabled={saved.includes(project.id)}
              onClick={save}
            >
              {saved.includes(project.id)
                ? "Saved to research"
                : "Save project evidence"}
            </button>
            {error && (
              <p role="alert" className="notice">
                {error}
              </p>
            )}
            <Link className="text-link monitor-open-research" href="/research">
              Open saved research <ArrowRight size={14} />
            </Link>
          </div>
        </Dialog>
      )}
    </Shell>
  );
}

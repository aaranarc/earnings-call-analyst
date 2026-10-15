"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  FlaskConical,
  LoaderCircle,
  RotateCcw,
} from "lucide-react";
import Shell from "./shell";
import type { EvalReport } from "@/lib/types";
export default function Evaluation() {
  const [report, setReport] = useState<EvalReport | null>(null),
    [error, setError] = useState(false);
  function load() {
    setError(false);
    fetch("/api/eval/latest")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setReport)
      .catch(() => setError(true));
  }
  useEffect(load, []);
  return (
    <Shell>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MEASUREMENT BEFORE CONFIDENCE</div>
          <h1>Show the work.</h1>
          <p>
            Retrieval, faithfulness, and number checking—measured separately,
            with their limitations.
          </p>
        </div>
        <a
          className="button secondary"
          href="https://github.com/aaranarc/earnings-call-analyst/actions/workflows/ci.yml"
          target="_blank"
          rel="noreferrer"
        >
          Live CI <ArrowUpRight size={15} />
        </a>
      </div>
      {error ? (
        <div className="notice" role="alert">
          Could not load evaluation results.{" "}
          <button className="button ghost" onClick={load}>
            <RotateCcw size={14} />
            Retry
          </button>
        </div>
      ) : !report ? (
        <div className="loading">
          <LoaderCircle className="spinner" size={18} />
          Loading published evaluation…
        </div>
      ) : report.status === "pending" ? (
        <div className="empty-state eval-pending">
          <FlaskConical size={35} />
          <h2>The benchmark is still being built.</h2>
          <p>
            Human-reviewed gold questions and number labels are not complete. We
            don’t publish provisional scores as final results.
          </p>
          <p>
            Retrieval and generation evaluation tools are ready. Reviewed gold
            questions, judge runs and human calibration are still pending.
          </p>
          <Link className="button secondary" href="/how-it-works">
            Explore the pipeline <ArrowUpRight size={15} />
          </Link>
        </div>
      ) : (
        <>
          <section className="method-grid">
            {report.metrics.map((m) => (
              <article key={m.name} className="method-card">
                <h2>{m.name}</h2>
                <strong className="metric-value">{m.value}</strong>
                <p>{m.definition}</p>
              </article>
            ))}
          </section>
          <h2 style={{ marginTop: 35 }}>Retrieval ablations</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Configuration</th>
                  <th>Hit rate @ 5</th>
                  <th>MRR @ 10</th>
                </tr>
              </thead>
              <tbody>
                {report.ablations.map((r) => (
                  <tr key={r.name}>
                    <td>{r.name}</td>
                    <td>{r.hit_at_5 ?? "Not measured"}</td>
                    <td>{r.mrr_at_10 ?? "Not measured"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.agreement && (
            <p className="section-copy">
              Judge–human agreement: κ {report.agreement.kappa ?? "undefined"}{" "}
              across {report.agreement.sample_size} answers.
            </p>
          )}
          <h2>Failure cases</h2>
          {report.failure_cases.map((f) => (
            <article className="pinned-card" key={f.question}>
              <strong>{f.question}</strong>
              <p>{f.finding}</p>
            </article>
          ))}
          {report.last_run && (
            <p className="section-copy mono">
              Last run: {report.last_run.date} · commit {report.last_run.commit}
            </p>
          )}
        </>
      )}
    </Shell>
  );
}

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import Shell from "@/components/shell";
export default function Page() {
  const steps = [
    [
      "01",
      "Start with the source",
      "Transcript PDFs are registered with company, quarter, source URL, and SHA-256. Ingestion preserves speaker and page context.",
    ],
    [
      "02",
      "Retrieve the evidence",
      "Vector and keyword search are fused with reciprocal rank fusion, then reranked. Company and quarter filters narrow the search.",
    ],
    [
      "03",
      "Generate with citations",
      "The model sees numbered excerpts. Every factual claim must cite one. An answer without valid citations is withheld.",
    ],
    [
      "04",
      "Check every number",
      "Numbers are normalised and matched against the cited passage. Value matches do not prove that the surrounding claim is faithful.",
    ],
    [
      "05",
      "Keep your thesis honest",
      "Use evidence to revisit your thinking. The workspace stores notes locally. On-demand thesis checks propose exact source quotes; you review the evidence and choose your assessment.",
    ],
  ];
  return (
    <Shell>
      <div className="page-heading">
        <div>
          <div className="eyebrow">NO BLACK BOX REQUIRED</div>
          <h1>From transcript to evidence.</h1>
          <p>One traceable pipeline. Five steps you can inspect.</p>
        </div>
      </div>
      <div className="table-scroll">
        <svg
          className="pipeline"
          viewBox="0 0 1000 180"
          role="img"
          aria-label="Transcript PDFs flow through hybrid retrieval, cited generation, number checks, and the thesis workspace"
        >
          <defs>
            <linearGradient id="flow">
              <stop stopColor="#dce99a" />
              <stop offset="1" stopColor="#b6c5e0" />
            </linearGradient>
            <marker
              id="arrow"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
            >
              <path d="M0 0L8 4L0 8" fill="#aaaab0" />
            </marker>
          </defs>
          {[
            "Transcript PDFs",
            "Hybrid retrieval",
            "Cited answer",
            "Number check",
            "Thesis workspace",
          ].map((label, i) => (
            <g key={label}>
              <rect
                x={i * 202 + 2}
                y="48"
                width="180"
                height="84"
                rx="12"
                fill="#1d1d20"
                stroke={i === 4 ? "url(#flow)" : "#343437"}
              />
              <text x={i * 202 + 20} y="75" fill="#aaaab0" fontSize="10">
                0{i + 1}
              </text>
              <text x={i * 202 + 20} y="106" fill="#f2f2ef" fontSize="13">
                {label}
              </text>
              {i < 4 && (
                <path
                  d={`M ${i * 202 + 185} 90 h 14`}
                  stroke="#aaaab0"
                  markerEnd="url(#arrow)"
                />
              )}
            </g>
          ))}
        </svg>
      </div>
      <section className="method-grid">
        {steps.map(([n, title, copy]) => (
          <article className="method-card" key={n}>
            <span className="mono">{n}</span>
            <h2>{title}</h2>
            <p>{copy}</p>
          </article>
        ))}
        <article className="method-card">
          <span className="mono">THE LIMITS</span>
          <h2>Evidence is not certainty.</h2>
          <p>
            A tiny corpus, imperfect retrieval, and value-only number checks
            leave real gaps. Review the original document before relying on a
            claim.
          </p>
          <Link className="text-link" style={{ marginTop: 20 }} href="/eval">
            Inspect evaluation <ArrowRight size={14} />
          </Link>
        </article>
      </section>
    </Shell>
  );
}

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  MessageSquare,
  Sparkles,
  Target,
} from "lucide-react";
import CoverageMap from "./coverage-map";
import { Brand } from "./shell";
import type { EvalReport } from "@/lib/types";
export const questions = [
  "Why did TCS’s operating margin fall in Q1 FY27?",
  "Compare TCS and Infosys on deal wins",
  "What risks did HDFC Bank discuss?",
  "What is the weather tomorrow?",
];
export default function Landing() {
  const router = useRouter(),
    [q, setQ] = useState(""),
    [metrics, setMetrics] = useState<EvalReport | null>(null);
  useEffect(() => {
    fetch("/api/health").catch(() => {});
    fetch("/api/eval/latest")
      .then((r) => (r.ok ? r.json() : null))
      .then(setMetrics)
      .catch(() => {});
  }, []);
  return (
    <div className="landing">
      <header className="landing-nav">
        <Brand />
        <nav aria-label="Main navigation">
          <Link href="/how-it-works">How it works</Link>
          <Link href="/eval">Evaluation</Link>
          <Link href="/watchlist" className="button secondary">
            Open workspace <ArrowRight size={14} />
          </Link>
        </nav>
      </header>
      <main id="main-content">
        <section className="hero">
          <div className="eyebrow">
            <Sparkles size={13} /> EARNINGS CALLS / CONNECTED RESEARCH
          </div>
          <h1>
            What did they say?
            <br />
            <span className="gradient-text">What happened next?</span>
          </h1>
          <p>
            Follow company announcements into later earnings calls. Compare the statements, inspect the numbers, keep the evidence.
          </p>
          <div className="hero-actions"><Link className="button primary follow-hero" href="/ask">Ask the analyst <ArrowRight size={16}/></Link> <Link className="text-link" href="/growth-payoff">Explore Growth Payoff <ArrowRight size={16}/></Link></div>
          <form
            className="prompt-box"
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim())
                router.push(`/ask?q=${encodeURIComponent(q.trim())}`);
            }}
          >
            <Sparkles size={21} />
            <input
              aria-label="Ask an earnings call"
              placeholder="What did management say—and does the evidence agree?"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              required
              minLength={3}
              maxLength={2000}
            />
            <button className="button primary" type="submit">
              <span>Ask the analyst</span>
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="question-chips">
            {questions.map((q, i) => (
              <Link key={q} href={`/ask?q=${encodeURIComponent(q)}`}>
                {
                  [
                    "Explain TCS margins",
                    "Compare deal wins",
                    "Explore HDFC risks",
                    "Test a refusal",
                  ][i]
                }{" "}
                <ArrowRight size={10} style={{ display: "inline" }} />
              </Link>
            ))}
          </div>
          <div className="hero-footnote">
            <BookOpen size={12} /> Transcript-grounded answers · Cited evidence
            · Number checks
          </div>
        </section>
        <div className="landing-library"><CoverageMap /><div className="library-caption"><span className="eyebrow">START WITH WHAT IS KNOWN</span><h2>A clear view of<br/>the evidence.</h2><p>Choose an available quarter to start researching.</p><Link className="text-link" href="/watchlist">Explore company changes <ArrowRight size={16}/></Link></div></div>
        <section className="landing-features" aria-label="Research tools">
          {[
            [
              MessageSquare,
              "An answer you can inspect.",
              "Citations take you straight to the original excerpt.",
              "Ask a question",
              "/ask",
            ],
            [
              Target,
              "Follow-through.",
              "Earlier announcements beside later reported outcomes. Both sources included.",
              "Explore QuarterLens",
              "/watchlist",
            ],
            [
              BookOpen,
              "Development results. Open limitations.",
              "Explore development retrieval and memory measurements. The human-reviewed benchmark is still pending.",
              "See the evaluation",
              "/eval",
            ],
          ].map(([Icon, title, desc, cta, href]) => {
            const I = Icon as typeof Target;
            return (
              <article className="feature" key={String(title)}>
                <I size={23} />
                <h2>{String(title)}</h2>
                <p>{String(desc)}</p>
                <Link className="text-link" href={String(href)}>
                  {String(cta)} <ArrowRight size={14} />
                </Link>
              </article>
            );
          })}
        </section>
        {metrics?.metrics?.length ? (
          <section
            className="landing-features"
            aria-label="Published evaluation metrics"
          >
            {metrics.metrics.map((m) => (
              <article className="feature" key={m.name}>
                <h2>{m.name}</h2>
                <strong className="metric-value">{m.value}</strong>
                <p>{m.definition}</p>
              </article>
            ))}
          </section>
        ) : null}

      </main>
      <footer>
        Research & educational project. Not investment advice.
        <span>QuantRAG · Built to show its work.</span>
      </footer>
    </div>
  );
}

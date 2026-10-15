"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Bookmark,
  Check,
  ExternalLink,
  LoaderCircle,
  MessageSquare,
  RotateCcw,
  Sparkles,
  Trash2,
} from "lucide-react";
import Shell from "./shell";
import Dialog from "./dialog";
import { questions } from "./landing";
import type { Answer, Hit, Thesis } from "@/lib/types";
import { readWorkspace, saveWorkspace } from "@/lib/workspace";
export default function Ask() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") || ""),
    [answer, setAnswer] = useState<Answer | null>(null),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState(""),
    [error, setError] = useState(""),
    [source, setSource] = useState<{ hit: Hit; highlight?: string } | null>(
      null,
    ),
    [pins, setPins] = useState<{ question: string; answer: string }[]>([]),
    [message, setMessage] = useState("");
  const [linkEvidence, setLinkEvidence] = useState(false),
    [theses, setTheses] = useState<Thesis[]>([]);
  const started = useRef(false),
    controller = useRef<AbortController | null>(null);
  useEffect(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("quantrag.pins.v1") || "[]",
      );
      if (
        Array.isArray(saved) &&
        saved.every(
          (p) =>
            typeof p?.question === "string" && typeof p?.answer === "string",
        )
      )
        setPins(saved);
    } catch {
      setMessage("Saved answers are unavailable in this browser.");
    }
  }, []);
  useEffect(() => {
    const initial = params.get("q");
    if (initial && !started.current) {
      started.current = true;
      void run(initial);
    }
  }, [params]);
  async function run(question: string) {
    if (question.trim().length < 3) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setQ(question);
    setBusy(true);
    setError("");
    setAnswer(null);
    setStatus("Connecting to the analyst…");
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: abort.signal,
      });
      if (!response.ok) {
        if (response.status === 429)
          throw Error("The analyst is busy. Please retry in a few seconds.");
        if (response.status === 503)
          throw Error(
            "The analyst is starting up or unavailable. Please wait a moment and retry.",
          );
        throw Error(
          "The analyst is unavailable. Check the API connection and retry.",
        );
      }
      if (!response.body) throw Error("The response stream is unavailable.");
      const reader = response.body.getReader(),
        decoder = new TextDecoder();
      let buffer = "",
        received = false;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const frame of parts) {
          const type = frame.match(/^event: (.+)$/m)?.[1];
          const data = frame.match(/^data: (.+)$/m)?.[1];
          if (!data) continue;
          const parsed = JSON.parse(data);
          if (type === "status") setStatus(parsed);
          if (type === "error") throw Error(parsed);
          if (type === "answer") {
            setAnswer(parsed);
            received = true;
          }
        }
        if (done) break;
      }
      if (!received)
        throw Error(
          "The connection ended before a checked answer arrived. Please retry.",
        );
    } catch (e) {
      if (!abort.signal.aborted) setError((e as Error).message);
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  }
  function savePins(next: typeof pins) {
    try {
      localStorage.setItem("quantrag.pins.v1", JSON.stringify(next));
      setPins(next);
      setMessage("Saved on this browser.");
    } catch {
      setMessage("Browser storage is unavailable. The answer was not saved.");
    }
  }
  function citation(n: number) {
    const c = answer?.citations.find((c) => c.n === n);
    const hit = answer?.hits.find((h) => h.chunk_id === c?.chunk_id);
    if (hit)
      setSource({
        hit,
        highlight: answer?.numbers.find(
          (n) => n.source?.chunk_id === hit.chunk_id,
        )?.source?.raw,
      });
  }
  function text(s: string, key: string) {
    return s.split(/(\[c\d+\]|\*\*[^*]+\*\*)/g).map((part, i) =>
      /^\[c\d+\]$/.test(part) ? (
        <button
          key={`${key}-${i}`}
          className="citation"
          onClick={() => citation(Number(part.slice(2, -1)))}
          aria-label={`Open citation ${part.slice(2, -1)}`}
        >
          {part.slice(2, -1)}
        </button>
      ) : part.startsWith("**") ? (
        <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>
      ) : (
        part
      ),
    );
  }
  function content(raw: string, where: string) {
    const chars = Array.from(raw),
      nodes: React.ReactNode[] = [];
    let start = 0;
    const nums = (answer?.numbers || [])
      .filter((n) => n.where === where && n.end <= chars.length)
      .sort((a, b) => a.end - b.end);
    nums.forEach((n, i) => {
      nodes.push(
        <span key={`t-${i}`}>
          {text(chars.slice(start, n.end).join(""), `n-${i}`)}
        </span>,
      );
      const matched = n.source?.raw;
      nodes.push(
        <button
          key={`b-${i}`}
          className={`number-badge ${n.status}`}
          title={`${(n.status === "verified" ? "Value matched — not claim verified" : n.status.replaceAll("_", " "))}${matched ? `: matched “${matched}”` : ": no matching source number"}`}
          aria-label={`${n.raw}: ${(n.status === "verified" ? "Value matched — not claim verified" : n.status.replaceAll("_", " "))}`}
          onClick={() => {
            const h = answer?.hits.find(
              (h) => h.chunk_id === n.source?.chunk_id,
            );
            if (h) setSource({ hit: h, highlight: matched });
            else
              setMessage(
                `${n.raw}: ${(n.status === "verified" ? "Value matched — not claim verified" : n.status.replaceAll("_", " "))}. No matching passage is available in this answer.`,
              );
          }}
        >
          {n.status === "verified"
            ? "✓"
            : n.status === "unverified"
              ? "!"
              : "~"}
        </button>,
      );
      start = n.end;
    });
    nodes.push(
      <span key="rest">{text(chars.slice(start).join(""), "rest")}</span>,
    );
    return nodes;
  }
  const tableCompanies = [
    ...new Set(
      answer?.comparison_table?.flatMap((r) => r.cells.map((c) => c.company)) ||
        [],
    ),
  ];
  return (
    <Shell>
      <div className="answer-layout">
        {!answer && !busy && !error && (
          <div className="chat-empty">
            <span className="brand-icon">
              <Sparkles size={27} />
            </span>
            <div className="eyebrow" style={{ justifyContent: "center" }}>
              FROM THE CALL. TO THE POINT.
            </div>
            <h1>
              A better question.
              <br />
              <span className="gradient-text">An answer you can check.</span>
            </h1>
            <p>
              Explore the transcripts, compare management commentary, or test
              your next thesis. Every answer comes back to the evidence.
            </p>
            <div className="question-chips">
              {questions.map((sample, i) => (
                <button
                  className="button ghost"
                  key={sample}
                  onClick={() => run(sample)}
                >
                  {
                    [
                      "Explain TCS margins",
                      "Compare deal wins",
                      "Explore HDFC risks",
                      "Test a refusal",
                    ][i]
                  }
                  <ArrowRight size={13} />
                </button>
              ))}
            </div>
          </div>
        )}
        {(answer || busy || error) && <h1 className="question-heading">{q}</h1>}
        {busy && (
          <div className="loading" role="status">
            <LoaderCircle size={19} className="spinner" />
            {status}
            <span className="muted">
              The answer appears after verification.
            </span>
          </div>
        )}
        {error && (
          <div className="notice" role="alert">
            {error}
            <div style={{ marginTop: 15 }}>
              <button className="button secondary" onClick={() => run(q)}>
                <RotateCcw size={14} /> Retry question
              </button>
            </div>
          </div>
        )}
        {answer && (
          <article className="answer-card">
            <div className="answer-toolbar">
              <span>
                <Sparkles size={17} /> QuantRAG analyst
              </span>
              {!answer.refused && (
                <button
                  className="button ghost"
                  onClick={() => {
                    if (
                      !pins.some(
                        (p) =>
                          p.question === answer.question &&
                          p.answer === answer.answer_markdown,
                      )
                    )
                      savePins([
                        ...pins,
                        {
                          question: answer.question,
                          answer: answer.answer_markdown,
                        },
                      ]);
                  }}
                >
                  <Bookmark size={14} />
                  Pin answer
                </button>
              )}
            </div>
            {!answer.refused && (
              <button
                className="button secondary"
                style={{ marginBottom: 20 }}
                onClick={() => {
                  try {
                    setTheses(readWorkspace());
                    setLinkEvidence(true);
                  } catch {
                    setMessage(
                      "Your saved thesis workspace could not be loaded.",
                    );
                  }
                }}
              >
                <Bookmark size={14} /> Save evidence to a thesis
              </button>
            )}
            {answer.refused ? (
              <div>
                <h2>Outside the available evidence</h2>
                <p className="section-copy">{answer.refusal_reason}</p>
              </div>
            ) : (
              <>
                {answer.route.kind === "comparison" && new Set(answer.citations.map(c => answer.hits.find(h => h.chunk_id === c.chunk_id)?.fiscal_label).filter(Boolean)).size > 1 && <div className="notice">This comparison uses different fiscal periods. It is not a same-quarter peer comparison.</div>}
                <div className="answer-summary" aria-label="Answer evidence summary">
                  <span><b>{answer.citations.length}</b> citations</span>
                  <span><b>{answer.numbers.filter(n => n.status === "verified").length}/{answer.numbers.length}</b> numbers matched</span>
                  <span>{answer.route.periods.join(" · ") || "Period not specified"}</span>
                </div>
                <div className="answer-prose">
                  {content(answer.answer_markdown, "answer")}
                </div>
                {answer.comparison_table?.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Metric</th>
                          {tableCompanies.map((c) => (
                            <th key={c}>{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {answer.comparison_table.map((row, ri) => (
                          <tr key={ri}>
                            <td>{row.metric}</td>
                            {tableCompanies.map((company) => {
                              const ci = row.cells.findIndex(
                                (c) => c.company === company,
                              );
                              const cell = row.cells[ci];
                              return (
                                <td key={company}>
                                  {cell ? (
                                    <>
                                      {content(cell.value, `table:${ri}:${ci}`)}
                                      {cell.citations.map((n) => (
                                        <button
                                          className="citation"
                                          key={n}
                                          onClick={() => citation(n)}
                                          aria-label={`Open citation ${n}`}
                                        >
                                          {n}
                                        </button>
                                      ))}
                                    </>
                                  ) : (
                                    "Not discussed"
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <div className="source-meta">
                  <Check size={13} /> Numbers checked against cited text. A
                  match does not establish the claim’s meaning.
                </div>
              </>
            )}
            <details className="disclosure">
              <summary>How this was answered</summary>
              <div>
                <div className="trace-grid">
                  <div>
                    <strong>Route</strong>
                    {answer.route.kind}
                  </div>
                  <div>
                    <strong>Companies / periods</strong>
                    {answer.route.companies.join(", ") ||
                      "No company filter"} ·{" "}
                    {answer.route.periods.join(", ") || "All available periods"}
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Chunk</th>
                        <th>Dense</th>
                        <th>FTS</th>
                        <th>RRF</th>
                        <th>Rerank</th>
                      </tr>
                    </thead>
                    <tbody>
                      {answer.hits.map((h) => (
                        <tr key={h.chunk_id}>
                          <td>
                            <button
                              className="citation"
                              onClick={() => setSource({ hit: h })}
                            >
                              {h.chunk_id}
                            </button>
                          </td>
                          {["dense", "fts", "rrf", "rerank"].map((k) => (
                            <td key={k}>{h.scores[k]?.toFixed(4) ?? "—"}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="source-meta">
                  {Object.entries(answer.timing_s).map(([k, v]) => (
                    <span className="mono" key={k}>
                      {k}: {v.toFixed(2)}s
                    </span>
                  ))}
                </div>
              </div>
            </details>
          </article>
        )}
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            run(q);
          }}
        >
          <div className="prompt-box">
            <MessageSquare size={19} />
            <input
              aria-label="Your question"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              required
              minLength={3}
              maxLength={2000}
              placeholder="Ask about a company, quarter, or claim…"
              disabled={busy}
            />
            <button
              className="button primary"
              disabled={busy}
              type="submit"
              aria-label="Send question"
            >
              {busy ? (
                <LoaderCircle size={17} className="spinner" />
              ) : (
                <ArrowRight size={17} />
              )}
            </button>
          </div>
        </form>
        {message && (
          <p className="status-message" role="status">
            {message}
          </p>
        )}
        {pins.length > 0 && (
          <section className="pinned-list">
            <h2>Pinned answers</h2>
            <p className="section-copy">
              Saved excerpts on this browser. Re-run the question to inspect
              citations.
            </p>
            {pins.map((pin, i) => (
              <article className="pinned-card" key={i}>
                <button
                  className="icon-button"
                  aria-label={`Remove pinned answer ${i + 1}`}
                  onClick={() => savePins(pins.filter((_, j) => i !== j))}
                >
                  <Trash2 size={14} />
                </button>
                <strong>{pin.question}</strong>
                <p>{pin.answer}</p>
              </article>
            ))}
          </section>
        )}
      </div>
      {linkEvidence && answer && (
        <Dialog
          title="Keep this evidence"
          onClose={() => setLinkEvidence(false)}
        >
          <form
            className="dialog-body"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const id = String(form.get("thesis"));
              let current: Thesis[];
              try { current = readWorkspace(); } catch { setMessage("Saved research could not be loaded. Evidence was not saved."); setLinkEvidence(false); return; }
              const selected = current.find((t) => t.id === id);
              if (id !== "new" && !selected) { setMessage("This thesis no longer exists. Reopen the save dialog."); setLinkEvidence(false); return; }
              const evidence =
                answer.answer_markdown +
                "\n\nSources: " +
                answer.citations
                  .map((c) => {
                    const hit = answer.hits.find(
                      (h) => h.chunk_id === c.chunk_id,
                    );
                    return hit
                      ? `${hit.company}, ${hit.fiscal_label}, page ${hit.page}: ${hit.source_url || "Source URL unavailable"}`
                      : "";
                  })
                  .join("\n");
              const period = [
                ...new Set(
                  answer.hits
                    .filter((h) =>
                      answer.citations.some((c) => c.chunk_id === h.chunk_id),
                    )
                    .map((h) => h.fiscal_label),
                ),
              ].join(", ");
              const updated: Thesis = selected
                ? {
                    ...selected,
                    evidence: [...selected.evidence, { id: crypto.randomUUID(), text: evidence, quarter: period, addedAt: new Date().toISOString(), kind: "answer" }],
                    status: "Unresolved",
                    reviewed: false,
                  }
                : {
                    id: crypto.randomUUID(),
                    company: answer.route.companies.join(", ") || "Research",
                    symbol: answer.route.companies.join(", ") || "Research",
                    title: String(form.get("title") || answer.question).trim(),
                    description:
                      "Evidence saved from a cited analyst answer. Review the source before making an assessment.",
                    evidence: [{id: crypto.randomUUID(), text: evidence, quarter: period, addedAt: new Date().toISOString(), kind: "answer"}],
                    before: "",
                    beforeQuarter: period,
                    after: "",
                    afterQuarter: "",
                    status: "Unresolved",
                    note: "",
                    sample: false,
                    reviewed: false,
                  };
              try {
                saveWorkspace(
                  selected
                    ? current.map((t) => (t.id === selected.id ? updated : t))
                    : [updated, ...current],
                );
                setLinkEvidence(false);
                setMessage(
                  "Evidence saved to your thesis workspace. The assessment remains unresolved.",
                );
              } catch {
                setMessage(
                  "Browser storage is unavailable. Evidence was not saved.",
                );
              }
            }}
          >
            <p>
              Save the checked answer with its source links. Adding new evidence
              resets your assessment to unresolved.
            </p>
            <label className="field">
              Thesis
              <select name="thesis">
                <option value="new">Create a new thesis</option>
                {theses.map((t) => (
                  <option value={t.id} key={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Title for a new thesis
              <input
                name="title"
                defaultValue={answer.question}
                required
                maxLength={140}
              />
            </label>
            <div className="notice">
              Each answer adds a new timeline entry. Your earlier evidence stays intact.
            </div>
            <button className="button primary" type="submit">
              Save evidence <ArrowRight size={15} />
            </button>
          </form>
        </Dialog>
      )}
      {source && (
        <Dialog title="Source evidence" drawer onClose={() => setSource(null)}>
          <div className="drawer-body">
            <div className="eyebrow">
              {source.hit.symbol} · {source.hit.fiscal_label}
            </div>
            <h2>{source.hit.company}</h2>
            <div className="source-meta">
              <span>{source.hit.speaker}</span>
              <span>{source.hit.role}</span>
              <span>{source.hit.section === "qa" ? "Q&A" : source.hit.section === "prepared" ? "Prepared remarks" : "Section unavailable"}</span>
              <span>Page {source.hit.page}</span>
            </div>
            <div className="source-text">
              {source.highlight
                ? source.hit.text.split(source.highlight).map((part, i) => (
                    <span key={i}>
                      {i > 0 && <mark>{source.highlight}</mark>}
                      {part}
                    </span>
                  ))
                : source.hit.text}
            </div>
            {!!source.hit.context?.length && <details className="disclosure">
              <summary>Read surrounding excerpts</summary>
              <div><p className="section-copy">Adjacent transcript chunks. These were not necessarily used to generate the answer.</p>
                {source.hit.context.map(entry => <article className="context-excerpt" key={entry.chunk_id}>
                  <strong>{entry.position === "before" ? "Before" : "After"} · {entry.speaker}</strong>
                  <small>{entry.role} · {entry.section === "qa" ? "Q&A" : entry.section === "prepared" ? "Prepared remarks" : "Section unavailable"} · Page {entry.page}</small>
                  <p>{entry.text}</p>
                </article>)}
              </div>
            </details>}
            {source.hit.source_url?.startsWith("https://") ? (
              <a
                className="button secondary"
                href={`${source.hit.source_url}#page=${source.hit.page}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open source PDF <ExternalLink size={14} />
              </a>
            ) : (
              <p>No source PDF link is available for this excerpt.</p>
            )}
          </div>
        </Dialog>
      )}
    </Shell>
  );
}

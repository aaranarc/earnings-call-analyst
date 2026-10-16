"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowRight,
  AudioLines,
  Bookmark,
  ChartNoAxesCombined,
  GitBranch,
  LayoutGrid,
  MessageSquare,
  Sparkles,
  TrendingUp,
} from "lucide-react";
export function Brand() {
  return (
    <Link href="/" className="brand">
      <span className="brand-icon">
        <AudioLines size={22} />
      </span>
      Quant<span>RAG</span>
      <small>ALPHA</small>
    </Link>
  );
}
export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const links = [
    ["/growth-payoff", "Growth Payoff", TrendingUp],
    ["/watchlist", "QuarterLens", LayoutGrid],
    ["/research", "Saved research", Bookmark],
    ["/ask", "Ask the analyst", MessageSquare],
    ["/eval", "Evaluation", ChartNoAxesCombined],
    ["/how-it-works", "How it works", GitBranch],
  ] as const;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {links.map(([href, label, Icon]) => (
            <Link
              key={href}
              href={href}
              className={path === href ? "nav-link active" : "nav-link"}
              aria-current={path === href ? "page" : undefined}
            >
              <Icon size={18} />
              {label}
              {path === href && <span className="nav-dot" />}
            </Link>
          ))}
        </nav>
        <div className="side-note">
          <Bookmark size={20} />
          <strong>Follow changes. Keep evidence.</strong>
          <p>Trace each finding to its source.</p>
          <Link href="/how-it-works">
            See the research process <ArrowRight size={14} />
          </Link>
        </div>
        <div className="side-bottom">
          <Sparkles size={15} />
          <span>Built to show its work</span>
          <span className="version">v2 α</span>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <span className="breadcrumb">
            Workspace <span>/</span>{" "}
            <b>{links.find((x) => x[0] === path)?.[1] || "Overview"}</b>
          </span>
          <Link href="/ask" className="text-link">
            <Sparkles size={15} /> Ask a question <ArrowRight size={14} />
          </Link>
        </header>
        <main id="main-content">{children}</main>
        <footer>
          Research & educational project. Not investment advice.{" "}
          <span>Verify every claim at the source.</span>
        </footer>
      </div>
    </div>
  );
}

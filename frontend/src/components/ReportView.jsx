/**
 * ReportView.jsx — Renders the markdown research report with citations,
 * quality scores, and a collapsible source list.
 * PDF export uses @react-pdf/renderer (real text, selectable, searchable).
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScorePanel } from "./ScoreBadge";
import { parseMd } from "../utils/parseMd";
import ChartsSection from "./ChartsSection";
import SummaryBox from "./SummaryBox";

// --------------------------------------------------------------------------- //
// PDF export — lazy-loaded so @react-pdf/renderer never bloats initial bundle
// --------------------------------------------------------------------------- //
async function exportToPDF(result) {
  const { topic, report, scores, sources, revision_count, elapsed_seconds } = result;

  // Dynamic imports — only downloaded when user clicks the button
  const [{ pdf }, { ReportPDFDocument }] = await Promise.all([
    import("@react-pdf/renderer"),
    import("./ReportPDF"),
  ]);

  const blocks = parseMd(report);
  const doc = (
    <ReportPDFDocument
      topic={topic}
      report={report}
      scores={scores}
      sources={sources}
      revision_count={revision_count}
      elapsed_seconds={elapsed_seconds}
      blocks={blocks}
    />
  );

  const blob = await pdf(doc).toBlob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `research-${topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 50)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --------------------------------------------------------------------------- //
// Sub-components
// --------------------------------------------------------------------------- //
function SourceList({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="source-list">
      <button
        className="source-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
        {sources.length} Sources Used
        <svg
          className={`source-chevron ${open ? "source-chevron--open" : ""}`}
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <ul className="source-items">
          {sources.map((url, i) => (
            <li key={i} className="source-item">
              <span className="source-num">{i + 1}</span>
              <a href={url} target="_blank" rel="noopener noreferrer" className="source-link">
                {url}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MetaBar({ topic, elapsed, revisionCount }) {
  return (
    <div className="report-meta">
      <div className="report-meta__topic">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
        <span>{topic}</span>
      </div>
      <div className="report-meta__stats">
        {elapsed && (
          <span className="meta-chip">⏱ {elapsed}s</span>
        )}
        <span className="meta-chip">
          🔄 {revisionCount === 0 ? "No revisions" : `${revisionCount} revision${revisionCount > 1 ? "s" : ""}`}
        </span>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Main component
// --------------------------------------------------------------------------- //
export default function ReportView({ result, onReset }) {
  if (!result) return null;

  const { topic, report, scores, sources, revision_count, elapsed_seconds, charts } = result;
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");

  const handleDownloadPDF = async () => {
    setPdfLoading(true);
    setPdfError("");
    try {
      await exportToPDF(result);
    } catch (err) {
      console.error("PDF export failed:", err);
      setPdfError("PDF generation failed. Please try again.");
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="report-view" id="report-section">
      <div className="report-header">
        <div className="report-header__left">
          <div className="report-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Research Report
          </div>
          <h2 className="report-title">{topic}</h2>
        </div>
        <div className="report-header__actions">
          <div>
            <button
              id="download-pdf-btn"
              className="pdf-btn"
              onClick={handleDownloadPDF}
              disabled={pdfLoading}
              title="Download real-text PDF"
            >
              {pdfLoading ? (
                <span className="btn-spinner" />
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              )}
              {pdfLoading ? "Generating…" : "Download PDF"}
            </button>
            {pdfError && <p className="pdf-error">{pdfError}</p>}
          </div>
          <button className="report-reset-btn" onClick={onReset} title="New research">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 .49-3.4" />
            </svg>
            New Research
          </button>
        </div>
      </div>

      <MetaBar topic={topic} elapsed={elapsed_seconds} revisionCount={revision_count} />

      {/* Summarize button + collapsible summary */}
      <SummaryBox report={report} />

      <ScorePanel scores={scores} />

      <div className="report-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => <h1 className="md-h1">{children}</h1>,
            h2: ({ children }) => <h2 className="md-h2">{children}</h2>,
            h3: ({ children }) => <h3 className="md-h3">{children}</h3>,
            p: ({ children }) => <p className="md-p">{children}</p>,
            ul: ({ children }) => <ul className="md-ul">{children}</ul>,
            ol: ({ children }) => <ol className="md-ol">{children}</ol>,
            li: ({ children }) => <li className="md-li">{children}</li>,
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">
                {children}
              </a>
            ),
            blockquote: ({ children }) => <blockquote className="md-blockquote">{children}</blockquote>,
            code: ({ inline, children }) =>
              inline ? (
                <code className="md-code-inline">{children}</code>
              ) : (
                <pre className="md-code-block"><code>{children}</code></pre>
              ),
            strong: ({ children }) => <strong className="md-strong">{children}</strong>,
          }}
        >
          {report}
        </ReactMarkdown>
      </div>

      {/* Charts section — only renders if visualizer found verified data */}
      <ChartsSection charts={charts} />

      <SourceList sources={sources} />
    </div>
  );
}

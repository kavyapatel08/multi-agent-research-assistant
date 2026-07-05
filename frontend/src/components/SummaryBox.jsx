/**
 * SummaryBox.jsx — Collapsible bullet-point summary above the full report.
 * Calls POST /summarize with the report text. Caches result per (report, length)
 * so switching view modes doesn't re-trigger the API. Only fetches when user clicks.
 */
import { useState, useRef } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function SummaryBox({ report }) {
  const [open, setOpen] = useState(false);
  const [length, setLength] = useState("brief");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // Cache: { "brief": "...", "detailed": "..." }
  const cache = useRef({});

  const fetchSummary = async (len) => {
    if (cache.current[len]) return cache.current[len];

    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report, length: len }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      cache.current[len] = data.summary;
      return data.summary;
    } catch (err) {
      setError(err.message || "Summary failed. Please try again.");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (!open) {
      // Opening — fetch if not cached
      if (!cache.current[length]) {
        await fetchSummary(length);
      }
      setOpen(true);
    } else {
      setOpen(false);
    }
  };

  const handleLengthChange = async (newLen) => {
    if (newLen === length) return;
    setLength(newLen);
    if (open && !cache.current[newLen]) {
      // Already open and switching mode — fetch new length
      await fetchSummary(newLen);
    }
  };

  const summary = cache.current[length] || "";

  return (
    <div className="summary-box" id="summary-box">
      {/* Trigger row */}
      <div className="summary-trigger">
        <button
          id="summarize-btn"
          className={`summary-btn ${open ? "summary-btn--active" : ""}`}
          onClick={handleToggle}
          disabled={loading}
        >
          {loading ? (
            <span className="btn-spinner" />
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
          )}
          {loading ? "Summarizing…" : open ? "Hide Summary" : "Summarize"}
        </button>

        {/* Length toggle — visible always so user can pre-select */}
        <div className="summary-length-toggle" role="group" aria-label="Summary length">
          <button
            className={`length-btn ${length === "brief" ? "length-btn--active" : ""}`}
            onClick={() => handleLengthChange("brief")}
          >
            Brief
          </button>
          <button
            className={`length-btn ${length === "detailed" ? "length-btn--active" : ""}`}
            onClick={() => handleLengthChange("detailed")}
          >
            Detailed
          </button>
        </div>
      </div>

      {/* Expanded summary panel */}
      {open && (
        <div className="summary-panel">
          {error ? (
            <p className="summary-error">{error}</p>
          ) : loading ? (
            <div className="summary-loading">
              <span className="btn-spinner" />
              <span>Generating summary…</span>
            </div>
          ) : summary ? (
            <ul className="summary-bullets">
              {summary
                .split("\n")
                .filter(l => l.trim())
                .map((line, i) => (
                  <li key={i} className="summary-bullet">
                    {line.replace(/^[•\-*]\s*/, "")}
                  </li>
                ))}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  );
}

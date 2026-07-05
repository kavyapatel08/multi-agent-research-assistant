/**
 * SearchBar.jsx — Topic input with client-side validation.
 * Enforces 300-char max before sending to backend.
 */
import { useState } from "react";

const MAX_LENGTH = 300;

export default function SearchBar({ onSubmit, isLoading }) {
  const [topic, setTopic] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = topic.trim();

    if (!trimmed) {
      setError("Please enter a research topic.");
      return;
    }
    if (trimmed.length > MAX_LENGTH) {
      setError(`Topic must be ${MAX_LENGTH} characters or fewer.`);
      return;
    }
    setError("");
    onSubmit(trimmed);
  };

  const remaining = MAX_LENGTH - topic.length;

  return (
    <form onSubmit={handleSubmit} className="search-form">
      <div className="search-input-wrapper">
        <div className="search-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </div>
        <input
          id="topic-input"
          type="text"
          className="search-input"
          placeholder="Enter any research topic… e.g. 'Future of quantum computing'"
          value={topic}
          onChange={(e) => {
            setTopic(e.target.value);
            if (error) setError("");
          }}
          disabled={isLoading}
          maxLength={MAX_LENGTH + 10}
          autoFocus
        />
        <button
          id="search-submit"
          type="submit"
          className="search-btn"
          disabled={isLoading || !topic.trim()}
        >
          {isLoading ? (
            <span className="btn-spinner" />
          ) : (
            <>
              <span>Research</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </>
          )}
        </button>
      </div>

      <div className="search-meta">
        {error ? (
          <span className="search-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
          </span>
        ) : (
          <span className={`char-count ${remaining < 50 ? "char-count--warn" : ""}`}>
            {remaining} characters remaining
          </span>
        )}
      </div>
    </form>
  );
}

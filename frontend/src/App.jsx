/**
 * App.jsx — Main application shell.
 * State machine: idle → loading → done / error
 */
import { useState, useCallback, useEffect } from "react";
import SearchBar from "./components/SearchBar";
import LoadingSteps from "./components/LoadingSteps";
import ReportView from "./components/ReportView";
import { streamResearch, checkHealth } from "./api";

const STATE = { IDLE: "idle", LOADING: "loading", DONE: "done", ERROR: "error" };

export default function App() {
  const [appState, setAppState] = useState(STATE.IDLE);
  const [currentStep, setCurrentStep] = useState("starting");
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [backendOk, setBackendOk] = useState(null);
  const [abortFn, setAbortFn] = useState(null);

  // Check backend health on mount
  useEffect(() => {
    checkHealth().then(setBackendOk);
  }, []);

  const handleSubmit = useCallback((topic) => {
    setAppState(STATE.LOADING);
    setCurrentStep("starting");
    setResult(null);
    setErrorMsg("");

    const abort = streamResearch(topic, {
      onProgress: ({ step }) => {
        setCurrentStep(step);
      },
      onResult: (data) => {
        setResult(data);
        setCurrentStep("done");
        setAppState(STATE.DONE);
      },
      onError: (msg) => {
        setErrorMsg(msg);
        setAppState(STATE.ERROR);
      },
    });

    setAbortFn(() => abort);
  }, []);

  const handleReset = useCallback(() => {
    if (abortFn) abortFn();
    setAppState(STATE.IDLE);
    setCurrentStep("starting");
    setResult(null);
    setErrorMsg("");
  }, [abortFn]);

  return (
    <div className="app">
      {/* Background decoration */}
      <div className="bg-orb bg-orb--1" aria-hidden="true" />
      <div className="bg-orb bg-orb--2" aria-hidden="true" />
      <div className="bg-grid" aria-hidden="true" />

      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div className="logo">
            <div className="logo-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="logo-text">
              <span className="logo-name">ResearchAI</span>
              <span className="logo-tag">Multi-Agent · Powered by Groq</span>
            </div>
          </div>

          {backendOk !== null && (
            <div className={`health-badge ${backendOk ? "health-badge--ok" : "health-badge--err"}`}>
              <span className="health-dot" />
              {backendOk ? "Backend Online" : "Backend Offline"}
            </div>
          )}
        </header>

        {/* Hero — only shown when idle */}
        {appState === STATE.IDLE && (
          <section className="hero">
            <div className="hero-content">
              <div className="hero-eyebrow">
                <span className="eyebrow-chip">6 AI Agents</span>
                <span className="eyebrow-chip">Live Web Search</span>
                <span className="eyebrow-chip">Auto Fact-Checking</span>
              </div>
              <h1 className="hero-title">
                Research anything with<br />
                <span className="hero-gradient">multi-agent AI</span>
              </h1>
              <p className="hero-subtitle">
                A team of specialized AI agents plans, searches, reads, writes, reviews,
                and fact-checks your research — all in one request.
              </p>
            </div>
          </section>
        )}

        {/* Search bar — always visible */}
        {appState !== STATE.DONE && (
          <div className={`search-section ${appState === STATE.IDLE ? "search-section--hero" : "search-section--compact"}`}>
            <SearchBar onSubmit={handleSubmit} isLoading={appState === STATE.LOADING} />
          </div>
        )}

        {/* Loading steps */}
        {appState === STATE.LOADING && (
          <LoadingSteps currentStep={currentStep} />
        )}

        {/* Error state */}
        {appState === STATE.ERROR && (
          <div className="error-card" role="alert">
            <div className="error-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <div className="error-content">
              <h3>Research Failed</h3>
              <p>{errorMsg}</p>
            </div>
            <button className="error-retry-btn" onClick={handleReset}>Try Again</button>
          </div>
        )}

        {/* Report */}
        {appState === STATE.DONE && result && (
          <ReportView result={result} onReset={handleReset} />
        )}

        {/* Footer */}
        <footer className="app-footer">
          <p>Built with LangGraph · Groq · Tavily · FastAPI · React</p>
        </footer>
      </div>
    </div>
  );
}

/**
 * LoadingSteps.jsx — Animated multi-step pipeline progress indicator.
 * Receives the current active step name and renders an animated pipeline.
 */

const STEPS = [
  { key: "planning",     label: "Planning",     icon: "🧠", desc: "Breaking topic into sub-questions" },
  { key: "searching",    label: "Searching",    icon: "🔍", desc: "Querying live web sources" },
  { key: "reading",      label: "Reading",      icon: "📖", desc: "Scraping & extracting content" },
  { key: "writing",      label: "Writing",      icon: "✍️",  desc: "Drafting the research report" },
  { key: "reviewing",    label: "Reviewing",    icon: "⚖️",  desc: "Scoring quality & accuracy" },
  { key: "fact_checking", label: "Fact-Checking", icon: "✅", desc: "Adding citations & verifying claims" },
];

const STEP_ORDER = STEPS.map((s) => s.key);

function getStepStatus(stepKey, activeStep) {
  const activeIdx = STEP_ORDER.indexOf(activeStep);
  const stepIdx = STEP_ORDER.indexOf(stepKey);

  if (activeStep === "done") return "done";
  if (stepIdx < activeIdx) return "done";
  if (stepIdx === activeIdx) return "active";
  return "pending";
}

export default function LoadingSteps({ currentStep }) {
  return (
    <div className="loading-container" role="status" aria-label="Research pipeline progress">
      <div className="loading-header">
        <div className="loading-pulse-ring" />
        <h2 className="loading-title">Research in Progress</h2>
        <p className="loading-subtitle">
          {STEPS.find((s) => s.key === currentStep)?.desc || "Initializing pipeline…"}
        </p>
      </div>

      <div className="steps-list">
        {STEPS.map((step, idx) => {
          const status = getStepStatus(step.key, currentStep);
          return (
            <div key={step.key} className={`step-item step-item--${status}`}>
              <div className="step-connector">
                {idx < STEPS.length - 1 && (
                  <div className={`step-line step-line--${status === "done" ? "done" : "pending"}`} />
                )}
              </div>

              <div className={`step-icon-wrap step-icon-wrap--${status}`}>
                {status === "done" ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : status === "active" ? (
                  <span className="step-spinner" />
                ) : (
                  <span className="step-number">{idx + 1}</span>
                )}
              </div>

              <div className="step-content">
                <span className={`step-label step-label--${status}`}>{step.label}</span>
                <span className="step-emoji">{step.icon}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="loading-dots">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

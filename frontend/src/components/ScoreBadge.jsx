/**
 * ScoreBadge.jsx — Visual critic score badges with color coding.
 *
 * Scoring weights (matching backend graph.py):
 *   40% faithfulness — factual accuracy is paramount
 *   35% completeness — coverage breadth is next
 *   25% clarity      — readability matters but is secondary
 *
 * overall_pct = round((faithfulness*0.40 + completeness*0.35 + clarity*0.25) * 10)
 */

// ── Sub-score helpers (x / 10) ────────────────────────────────────────────────
function getScoreColor(score) {
  if (score >= 8) return "score--high";
  if (score >= 6) return "score--mid";
  return "score--low";
}

function getScoreLabel(score) {
  if (score >= 9) return "Excellent";
  if (score >= 8) return "Very Good";
  if (score >= 6) return "Good";
  if (score >= 4) return "Fair";
  return "Needs Work";
}

// ── Overall-score helpers (0–100 %) ──────────────────────────────────────────
function getOverallColor(pct) {
  if (pct >= 80) return "score--high";
  if (pct >= 50) return "score--mid";
  return "score--low";
}

function getOverallLabel(pct) {
  if (pct >= 90) return "Excellent";
  if (pct >= 80) return "Very Good";
  if (pct >= 65) return "Good";
  if (pct >= 50) return "Fair";
  return "Needs Work";
}

// SVG ring helper — draws a circular progress indicator
function Ring({ pct, color }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const dash = ((100 - pct) / 100) * circ;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" className="overall-ring">
      {/* Track */}
      <circle
        cx="36" cy="36" r={r}
        fill="none"
        stroke="rgba(255,255,255,0.08)"
        strokeWidth="6"
      />
      {/* Progress arc */}
      <circle
        cx="36" cy="36" r={r}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={dash}
        transform="rotate(-90 36 36)"
        style={{ transition: "stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)" }}
      />
    </svg>
  );
}

// ── Individual sub-score card ─────────────────────────────────────────────────
export function ScoreBadge({ label, score }) {
  const colorClass = getScoreColor(score);
  const pct = (score / 10) * 100;

  return (
    <div className={`score-badge ${colorClass}`}>
      <div className="score-badge__top">
        <span className="score-badge__label">{label}</span>
        <span className="score-badge__value">
          {score}<span className="score-badge__denom">/10</span>
        </span>
      </div>
      <div className="score-badge__bar-bg">
        <div className="score-badge__bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-badge__sublabel">{getScoreLabel(score)}</span>
    </div>
  );
}

// ── Overall score card (headline) ─────────────────────────────────────────────
function OverallScoreCard({ pct }) {
  const colorClass = getOverallColor(pct);
  // Map CSS class → a concrete hex for the SVG ring stroke
  const ringColor = colorClass === "score--high"
    ? "#34d399"
    : colorClass === "score--mid"
    ? "#fbbf24"
    : "#f87171";

  return (
    <div className={`score-badge score-badge--overall ${colorClass}`}>
      <div className="overall-card__inner">
        <div className="overall-ring-wrap">
          <Ring pct={pct} color={ringColor} />
          <span className="overall-ring-value">{pct}%</span>
        </div>
        <div className="overall-card__text">
          <span className="score-badge__label">Overall Score</span>
          <span className="overall-card__sublabel">{getOverallLabel(pct)}</span>
          <span className="overall-card__weights">
            F·40% + C·35% + Cl·25%
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Panel: overall card + three sub-score cards ───────────────────────────────
export function ScorePanel({ scores }) {
  if (!scores) return null;
  const overall = scores.overall_pct ?? 0;

  return (
    <div className="score-panel">
      <h3 className="score-panel__title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
        Quality Scores
      </h3>
      <div className="score-panel__grid">
        {/* Headline overall card — spans first column */}
        <OverallScoreCard pct={overall} />
        {/* Three supporting sub-score cards */}
        <ScoreBadge label="Faithfulness" score={scores.faithfulness ?? 0} />
        <ScoreBadge label="Completeness" score={scores.completeness ?? 0} />
        <ScoreBadge label="Clarity"      score={scores.clarity ?? 0} />
      </div>
    </div>
  );
}

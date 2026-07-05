/**
 * ChartsSection.jsx — Renders visualizer output with 4 distinct card types:
 *   "stat"  → large headline number card (single value — no chart)
 *   "bar"   → Recharts BarChart with one distinct color per bar
 *   "line"  → Recharts LineChart with gradient stroke
 *   "table" → plain HTML table
 *
 * All charts from the backend are rendered — no artificial cap.
 * Grid wraps naturally with auto-fit columns.
 */
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ── Palette: 8 distinct colors, cycles for bars ──────────────────────────────
const PALETTE = [
  "#6d8eff", // blue
  "#34d399", // green
  "#f59e0b", // amber
  "#f87171", // red
  "#a78bfa", // purple
  "#22d3ee", // cyan
  "#fb923c", // orange
  "#4ade80", // lime
];

// ── Custom tooltip ─────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label, unit }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="chart-tooltip__value" style={{ color: p.color }}>
          {p.value}{unit ? ` ${unit}` : ""}
        </p>
      ))}
    </div>
  );
};

// ── Source caption ─────────────────────────────────────────────────────────────
function ChartCaption({ sourceUrl }) {
  if (!sourceUrl) return null;
  const display = sourceUrl.length > 72 ? sourceUrl.slice(0, 72) + "…" : sourceUrl;
  return (
    <p className="chart-caption">
      Source:{" "}
      <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="chart-caption-link">
        {display}
      </a>
    </p>
  );
}

// ── Stat card — single headline number ────────────────────────────────────────
function StatCard({ chart }) {
  const point = chart.data?.[0];
  if (!point) return null;

  // Format large numbers nicely
  const raw = point.value;
  const formatted =
    typeof raw === "number" && raw >= 1_000_000_000
      ? (raw / 1_000_000_000).toFixed(1) + "B"
      : typeof raw === "number" && raw >= 1_000_000
      ? (raw / 1_000_000).toFixed(1) + "M"
      : typeof raw === "number" && raw >= 1_000
      ? raw.toLocaleString()
      : String(raw);

  return (
    <div className="chart-card chart-card--stat">
      <p className="chart-stat__label">{chart.title}</p>
      <p className="chart-stat__value">
        {formatted}
        {chart.unit ? <span className="chart-stat__unit"> {chart.unit}</span> : null}
      </p>
      {point.label && point.label !== chart.title && (
        <p className="chart-stat__sub">{point.label}</p>
      )}
      <ChartCaption sourceUrl={chart.source_url} />
    </div>
  );
}

// ── Bar chart — 2+ comparative categories ─────────────────────────────────────
function BarChartCard({ chart }) {
  if (!chart.data || chart.data.length < 2) return <StatCard chart={chart} />;
  return (
    <div className="chart-card">
      <h4 className="chart-title">{chart.title}{chart.unit ? ` (${chart.unit})` : ""}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chart.data} margin={{ top: 8, right: 12, bottom: 24, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            angle={chart.data.length > 4 ? -30 : 0}
            textAnchor={chart.data.length > 4 ? "end" : "middle"}
            interval={0}
          />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} width={36} />
          <Tooltip content={<CustomTooltip unit={chart.unit} />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={60}>
            {chart.data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <ChartCaption sourceUrl={chart.source_url} />
    </div>
  );
}

// ── Line chart — 2+ chronological points ──────────────────────────────────────
function LineChartCard({ chart }) {
  if (!chart.data || chart.data.length < 2) return <StatCard chart={chart} />;
  return (
    <div className="chart-card">
      <h4 className="chart-title">{chart.title}{chart.unit ? ` (${chart.unit})` : ""}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chart.data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} width={36} />
          <Tooltip content={<CustomTooltip unit={chart.unit} />} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={PALETTE[0]}
            strokeWidth={2.5}
            dot={(props) => {
              const { cx, cy, index } = props;
              return (
                <circle
                  key={index}
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={PALETTE[index % PALETTE.length]}
                  stroke="#080c14"
                  strokeWidth={1.5}
                />
              );
            }}
            activeDot={{ r: 6, fill: PALETTE[1], stroke: "#080c14", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <ChartCaption sourceUrl={chart.source_url} />
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
function TableCard({ chart }) {
  if (!chart.data?.length) return null;
  return (
    <div className="chart-card">
      <h4 className="chart-title">{chart.title}</h4>
      <div className="chart-table-wrap">
        <table className="chart-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>{chart.unit ? `Value (${chart.unit})` : "Value"}</th>
            </tr>
          </thead>
          <tbody>
            {chart.data.map((row, i) => (
              <tr key={i}>
                <td>{row.label}</td>
                <td style={{ color: PALETTE[i % PALETTE.length], fontWeight: 600 }}>
                  {row.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ChartCaption sourceUrl={chart.source_url} />
    </div>
  );
}

// ── Router ─────────────────────────────────────────────────────────────────────
function ChartCard({ chart, index }) {
  switch (chart.type) {
    case "stat":
      return <StatCard chart={chart} />;
    case "bar":
      return <BarChartCard chart={chart} />;
    case "line":
      return <LineChartCard chart={chart} />;
    case "table":
      return <TableCard chart={chart} />;
    default:
      // Unknown type: treat as stat if 1 point, bar if 2+
      return chart.data?.length === 1
        ? <StatCard chart={chart} />
        : <BarChartCard chart={chart} />;
  }
}

// ── Main export ────────────────────────────────────────────────────────────────
export default function ChartsSection({ charts }) {
  // Render nothing if no charts — no placeholder, no empty container
  if (!charts || charts.length === 0) return null;

  return (
    <div className="charts-section" id="charts-section">
      <div className="charts-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6"  y1="20" x2="6"  y2="14" />
        </svg>
        <span>Data &amp; Visualizations</span>
        <span className="charts-badge">
          {charts.length} item{charts.length !== 1 ? "s" : ""} · source-verified
        </span>
      </div>

      {/* No artificial cap — all charts render, grid wraps naturally */}
      <div className="charts-grid">
        {charts.map((chart, i) => (
          <ChartCard key={i} chart={chart} index={i} />
        ))}
      </div>
    </div>
  );
}

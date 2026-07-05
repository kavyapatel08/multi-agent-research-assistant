/**
 * ReportPDF.jsx — @react-pdf/renderer document built from structured report data.
 * Always white background, dark text — fully independent of the app's dark theme.
 * Lazy-loaded via dynamic import() — zero impact on initial bundle.
 */

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
} from '@react-pdf/renderer';

// --------------------------------------------------------------------------- //
// Print palette — ALWAYS white background, dark text.
// No CSS variables. No references to the app's dark UI theme.
// All accent colors are dark enough to read on a white page.
// --------------------------------------------------------------------------- //
const C = {
  // Page backgrounds
  bg:       '#FFFFFF',   // page — always white
  surface:  '#F8F9FC',   // section / card fill
  surface2: '#EEF1F8',   // table header, score tile

  // Borders
  border:   '#D1D9E6',   // light rule
  border2:  '#B0BCCE',   // stronger table/section border

  // Text — dark on white
  ink:      '#111827',   // headings, primary text
  ink2:     '#374151',   // body text
  ink3:     '#6B7280',   // captions, meta
  inkFaint: '#9CA3AF',   // footer, disabled

  // Accents — dark enough to read on white
  primary:  '#1D4ED8',   // deep blue (badge, citations, bullets)
  success:  '#15803D',   // dark green
  warn:     '#92400E',   // dark amber
  danger:   '#991B1B',   // dark red
};

const S = StyleSheet.create({
  // ---- Page ----
  page: {
    backgroundColor: C.bg,
    paddingTop: 48,
    paddingBottom: 56,
    paddingHorizontal: 48,
    fontFamily: 'Helvetica',
  },

  // ---- Header ----
  header: {
    marginBottom: 28,
    paddingBottom: 16,
    borderBottomWidth: 2,
    borderBottomColor: C.border2,
    borderBottomStyle: 'solid',
  },
  headerBadge: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: C.primary,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  headerTitle: {
    fontSize: 22,
    fontFamily: 'Helvetica-Bold',
    color: C.ink,
    marginBottom: 6,
    lineHeight: 1.3,
  },
  headerMeta: {
    fontSize: 9,
    color: C.ink3,
  },

  // ---- Quality Scores ----
  scoreSection: {
    marginBottom: 24,
    padding: 14,
    backgroundColor: C.surface,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: C.border,
    borderStyle: 'solid',
  },
  scoreTitle: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: C.ink3,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  scoreGrid: {
    flexDirection: 'row',
    gap: 10,
  },
  scoreItem: {
    flex: 1,
    padding: 10,
    backgroundColor: C.surface2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: C.border,
    borderStyle: 'solid',
  },
  scoreLabel: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: C.ink3,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  scoreValue: {
    fontSize: 20,
    fontFamily: 'Helvetica-Bold',
    color: C.ink,
  },
  scoreDenom: {
    fontSize: 10,
    color: C.ink3,
  },
  scoreSub: {
    fontSize: 8,
    marginTop: 3,
  },

  // ---- Markdown: headings ----
  h1: {
    fontSize: 18,
    fontFamily: 'Helvetica-Bold',
    color: C.ink,
    marginTop: 20,
    marginBottom: 10,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.border2,
    borderBottomStyle: 'solid',
  },
  h2: {
    fontSize: 14,
    fontFamily: 'Helvetica-Bold',
    color: C.ink,
    marginTop: 18,
    marginBottom: 8,
  },
  h3: {
    fontSize: 11,
    fontFamily: 'Helvetica-Bold',
    color: C.ink2,
    marginTop: 12,
    marginBottom: 6,
  },

  // ---- Markdown: paragraph / inline ----
  paragraph: {
    fontSize: 10,
    color: C.ink2,
    lineHeight: 1.7,
    marginBottom: 8,
  },
  cite: {
    fontSize: 9,
    color: C.primary,
  },
  divider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 14,
  },

  // ---- Bullets ----
  bulletGroup: { marginBottom: 10 },
  bulletRow: {
    flexDirection: 'row',
    marginBottom: 4,
    paddingLeft: 4,
  },
  bulletDot: {
    fontSize: 10,
    color: C.primary,
    marginRight: 8,
    width: 10,
  },
  bulletText: {
    fontSize: 10,
    color: C.ink2,
    lineHeight: 1.6,
    flex: 1,
  },

  // ---- Tables ----
  table: {
    marginBottom: 14,
    borderWidth: 1,
    borderColor: C.border2,
    borderStyle: 'solid',
    borderRadius: 4,
    overflow: 'hidden',
  },
  tableHeaderRow: {
    flexDirection: 'row',
    backgroundColor: C.surface2,
    borderBottomWidth: 1,
    borderBottomColor: C.border2,
    borderBottomStyle: 'solid',
  },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    borderBottomStyle: 'solid',
  },
  tableCellHeader: {
    flex: 1,
    padding: 6,
    fontSize: 9,
    fontFamily: 'Helvetica-Bold',
    color: C.ink,
  },
  tableCell: {
    flex: 1,
    padding: 6,
    fontSize: 9,
    color: C.ink2,
  },

  // ---- Sources ----
  sourceSection: {
    marginTop: 24,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: C.border2,
    borderTopStyle: 'solid',
  },
  sourceTitle: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: C.ink3,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  sourceItem: {
    flexDirection: 'row',
    marginBottom: 5,
  },
  sourceNum: {
    fontSize: 9,
    color: C.primary,
    fontFamily: 'Helvetica-Bold',
    width: 18,
  },
  sourceUrl: {
    fontSize: 9,
    color: C.ink3,
    flex: 1,
  },

  // ---- Footer (fixed on every page) ----
  footer: {
    position: 'absolute',
    bottom: 24,
    left: 48,
    right: 48,
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: C.border,
    borderTopStyle: 'solid',
    paddingTop: 8,
  },
  footerText: {
    fontSize: 8,
    color: C.inkFaint,
  },
  pageNum: {
    fontSize: 8,
    color: C.inkFaint,
  },
});

// --------------------------------------------------------------------------- //
// Score helpers (dark-on-white readable colors)
// --------------------------------------------------------------------------- //
function scoreColor(v) {
  if (v >= 8) return C.success;
  if (v >= 6) return C.warn;
  return C.danger;
}
function scoreLabel(v) {
  if (v >= 9) return 'Excellent';
  if (v >= 8) return 'Very Good';
  if (v >= 6) return 'Good';
  if (v >= 4) return 'Fair';
  return 'Needs Work';
}

// --------------------------------------------------------------------------- //
// Block renderers
// --------------------------------------------------------------------------- //
function renderBlock(block, idx) {
  switch (block.type) {
    case 'h1':
      return <Text key={idx} style={S.h1}>{block.text}</Text>;
    case 'h2':
      return <Text key={idx} style={S.h2}>{block.text}</Text>;
    case 'h3':
      return <Text key={idx} style={S.h3}>{block.text}</Text>;
    case 'divider':
      return <View key={idx} style={S.divider} />;
    case 'paragraph':
      return (
        <Text key={idx} style={S.paragraph}>
          {block.spans.map((sp, si) =>
            sp.cite
              ? <Text key={si} style={S.cite}>{sp.text}</Text>
              : <Text key={si}>{sp.text}</Text>
          )}
        </Text>
      );
    case 'bullet':
      return (
        <View key={idx} style={S.bulletGroup}>
          {block.items.map((item, bi) => (
            <View key={bi} style={S.bulletRow}>
              <Text style={S.bulletDot}>•</Text>
              <Text style={S.bulletText}>{item}</Text>
            </View>
          ))}
        </View>
      );
    case 'table':
      return (
        <View key={idx} style={S.table}>
          <View style={S.tableHeaderRow}>
            {block.headers.map((h, hi) => (
              <Text key={hi} style={S.tableCellHeader}>{h}</Text>
            ))}
          </View>
          {block.rows.map((row, ri) => (
            <View
              key={ri}
              style={[S.tableRow, ri === block.rows.length - 1 && { borderBottomWidth: 0 }]}
            >
              {row.map((cell, ci) => (
                <Text key={ci} style={S.tableCell}>{cell}</Text>
              ))}
            </View>
          ))}
        </View>
      );
    default:
      return null;
  }
}

// --------------------------------------------------------------------------- //
// Main PDF Document component
// --------------------------------------------------------------------------- //
export function ReportPDFDocument({
  topic, report, scores, sources,
  revision_count, elapsed_seconds, blocks,
}) {
  const now = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <Document
      title={`Research Report: ${topic}`}
      author="ResearchAI"
      subject={topic}
      creator="ResearchAI — Multi-Agent Research Assistant"
    >
      <Page size="A4" style={S.page}>

        {/* ── Header ── */}
        <View style={S.header}>
          <Text style={S.headerBadge}>RESEARCH REPORT · ResearchAI</Text>
          <Text style={S.headerTitle}>{topic}</Text>
          <Text style={S.headerMeta}>
            Generated {now}
            {elapsed_seconds ? `  ·  ${elapsed_seconds}s` : ''}
            {revision_count > 0
              ? `  ·  ${revision_count} revision${revision_count > 1 ? 's' : ''}`
              : ''}
          </Text>
        </View>

        {/* ── Quality Scores ── */}
        {scores && (
          <View style={S.scoreSection}>
            <Text style={S.scoreTitle}>Quality Scores</Text>
            <View style={S.scoreGrid}>
              {[
                ['Faithfulness', scores.faithfulness],
                ['Completeness', scores.completeness],
                ['Clarity',      scores.clarity],
              ].map(([label, val]) => (
                <View key={label} style={S.scoreItem}>
                  <Text style={S.scoreLabel}>{label}</Text>
                  <Text style={[S.scoreValue, { color: scoreColor(val) }]}>
                    {val}
                    <Text style={S.scoreDenom}>/10</Text>
                  </Text>
                  <Text style={[S.scoreSub, { color: scoreColor(val) }]}>
                    {scoreLabel(val)}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* ── Report body ── */}
        {blocks.map((block, i) => renderBlock(block, i))}

        {/* ── Sources ── */}
        {sources && sources.length > 0 && (
          <View style={S.sourceSection}>
            <Text style={S.sourceTitle}>Sources ({sources.length})</Text>
            {sources.map((url, i) => (
              <View key={i} style={S.sourceItem}>
                <Text style={S.sourceNum}>{i + 1}.</Text>
                <Text style={S.sourceUrl}>{url}</Text>
              </View>
            ))}
          </View>
        )}

        {/* ── Footer with page numbers (fixed on every page) ── */}
        <View style={S.footer} fixed>
          <Text style={S.footerText}>ResearchAI · Multi-Agent Research Assistant</Text>
          <Text
            style={S.pageNum}
            render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`}
          />
        </View>

      </Page>
    </Document>
  );
}

/**
 * parseMd.js — Lightweight markdown-to-structured-data parser for PDF export.
 * Converts the research report markdown into an array of typed blocks that
 * ReportPDF.jsx can render as real PDF text elements.
 *
 * Supported blocks:
 *   { type: 'h1'|'h2'|'h3', text }
 *   { type: 'paragraph', text, spans: [{text, cite}] }
 *   { type: 'bullet', items: [string] }
 *   { type: 'table', headers: [string], rows: [[string]] }
 *   { type: 'divider' }
 */

/** Strip inline markdown bold/italic but keep text */
function stripInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/_(.+?)_/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .trim();
}

/** Parse inline citation markers like [Source: URL] */
function parseSpans(text) {
  const parts = [];
  const re = /\[Source:\s*(https?:\/\/[^\]]+)\]/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ text: stripInline(text.slice(last, m.index)), cite: null });
    parts.push({ text: `[Source: ${m[1]}]`, cite: m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push({ text: stripInline(text.slice(last)), cite: null });
  return parts.filter(p => p.text.trim());
}

/** Check if a line is a markdown table separator like |---|---| */
function isTableSep(line) {
  return /^\|[\s\-:|]+\|/.test(line);
}

/** Parse a markdown table block (array of raw lines) → {headers, rows} */
function parseTable(lines) {
  const rows = lines
    .filter(l => !isTableSep(l))
    .map(l =>
      l.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => stripInline(c.trim()))
    );
  if (rows.length === 0) return null;
  const [headers, ...body] = rows;
  return { type: 'table', headers, rows: body };
}

export function parseMd(markdown) {
  if (!markdown) return [];
  const lines = markdown.split('\n');
  const blocks = [];

  let i = 0;
  let bulletBuffer = [];
  let tableBuffer = [];

  const flushBullets = () => {
    if (bulletBuffer.length) {
      blocks.push({ type: 'bullet', items: [...bulletBuffer] });
      bulletBuffer = [];
    }
  };
  const flushTable = () => {
    if (tableBuffer.length) {
      const t = parseTable(tableBuffer);
      if (t) blocks.push(t);
      tableBuffer = [];
    }
  };

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimEnd();

    // Headings
    if (/^# /.test(line)) {
      flushBullets(); flushTable();
      blocks.push({ type: 'h1', text: stripInline(line.replace(/^# /, '')) });
      i++; continue;
    }
    if (/^## /.test(line)) {
      flushBullets(); flushTable();
      blocks.push({ type: 'h2', text: stripInline(line.replace(/^## /, '')) });
      i++; continue;
    }
    if (/^### /.test(line)) {
      flushBullets(); flushTable();
      blocks.push({ type: 'h3', text: stripInline(line.replace(/^### /, '')) });
      i++; continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      flushBullets(); flushTable();
      blocks.push({ type: 'divider' });
      i++; continue;
    }

    // Table lines
    if (/^\|/.test(line)) {
      flushBullets();
      tableBuffer.push(line);
      i++; continue;
    } else {
      flushTable();
    }

    // Bullet points
    if (/^(\s*[-*+]|\s*\d+\.) /.test(line)) {
      const text = stripInline(line.replace(/^\s*[-*+\d.]+\s/, ''));
      bulletBuffer.push(text);
      i++; continue;
    } else {
      flushBullets();
    }

    // Blank lines
    if (line.trim() === '') {
      i++; continue;
    }

    // Paragraph
    const spans = parseSpans(line);
    if (spans.length) {
      blocks.push({ type: 'paragraph', text: stripInline(line), spans });
    }
    i++;
  }

  flushBullets();
  flushTable();
  return blocks;
}

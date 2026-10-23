/**
 * Build-time cover cards for syndication.
 *
 * The articles collection carries no photography (no `heroImage` values are
 * set today), so feed items would otherwise ship without an image. These
 * generated typographic cards give each item a stable, brand-consistent
 * picture without inventing news imagery.
 *
 * Each card is authored as SVG and rasterised to PNG with sharp, because RSS
 * readers and social-card unfurlers handle PNG far more reliably than SVG.
 * Rendered by `src/pages/covers/[...path].png.ts`.
 */

import sharp from "sharp";

export type CoverKind = "article" | "briefing";

export interface CoverOptions {
  kind: CoverKind;
  title: string;
  /** Small line above the rule, e.g. the source name or "每日简报". */
  eyebrow: string;
  /** Second metadata line, e.g. tag labels. */
  meta: string;
  /** Right-aligned date, `YYYY-MM-DD`. */
  date: string;
}

const WIDTH = 1200;
const HEIGHT = 630;

const ACCENT = "#1d4ed8";
const INK = "#131720";
const MUTED = "#4f5562";
const DIM = "#7a8090";
const BORDER = "#dfe2ea";

/** Mirrors the site font stack; the installed Noto SC faces match it. */
const SERIF = "'Noto Serif SC', Georgia, serif";
const SANS = "'Noto Sans SC', Arial, sans-serif";
const MONO = "'JetBrains Mono', Consolas, monospace";

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Rough advance width of a character in em units. */
function charWidth(ch: string): number {
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x2e80) return 1; // CJK, full-width punctuation
  if (/[iIl1.,:;'|!]/.test(ch)) return 0.3;
  if (/[A-Z]/.test(ch)) return 0.68;
  if (/[a-z0-9]/.test(ch)) return 0.55;
  if (ch === " ") return 0.3;
  return 0.62;
}

function measure(text: string): number {
  let total = 0;
  for (const ch of text) total += charWidth(ch);
  return total;
}

function truncate(text: string, maxChars: number): string {
  const chars = Array.from(text);
  return chars.length <= maxChars ? text : `${chars.slice(0, maxChars - 1).join("")}…`;
}

/** Latin words, CJK runs, or a single punctuation/space character. */
const WRAP_TOKENS = /[A-Za-z0-9][A-Za-z0-9'’\-_.]*|\s+|./gu;

/**
 * Greedy wrap by estimated width, breaking between tokens rather than
 * between characters so Latin words stay intact (`OpenAI`, not `OpenA / I`).
 * CJK breaks naturally, since each Han character is its own token.
 *
 * `maxUnits` is in em units, so `maxUnits = availablePx / fontSize`.
 */
function wrapText(text: string, maxUnits: number, maxLines: number): string[] {
  const tokens = text.match(WRAP_TOKENS) ?? [];
  const lines: string[] = [];
  let current = "";
  let used = 0;
  let consumedTokens = 0;

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    const width = measure(token);

    if (used + width <= maxUnits || current.length === 0) {
      current += token;
      used += width;
      continue;
    }

    // Token does not fit: start a new line.
    if (lines.length === maxLines - 1) break; // no room for another line
    lines.push(current.trimEnd());
    consumedTokens = i;
    current = token.trimStart();
    used = measure(current);
  }

  if (current.trim().length > 0 && lines.length < maxLines) {
    lines.push(current.trimEnd());
    consumedTokens = tokens.length;
  }

  if (lines.length === 0) return [""];

  // Signal truncation when the title did not fit.
  if (consumedTokens < tokens.length) {
    const lastIndex = lines.length - 1;
    const lastChars = Array.from(lines[lastIndex]);
    lines[lastIndex] = `${lastChars.slice(0, Math.max(0, lastChars.length - 1)).join("")}…`;
  }

  return lines;
}

function buildSvg(options: CoverOptions): string {
  const { kind, title, eyebrow, meta, date } = options;

  const titleWidth = WIDTH - 160;

  // Shrink the type until the title fits in three lines. Long Latin words
  // cannot break, so a fixed size would overflow the card.
  let titleSize = 56;
  let titleLines: string[] = [];
  for (const size of [56, 52, 48, 44, 40, 36]) {
    titleSize = size;
    titleLines = wrapText(title, titleWidth / size, 3);
    if (titleLines.length < 3) break;
    // Accept three lines only when the text was not cut short.
    const joined = titleLines.join("").replace(/…$/, "");
    if (joined.length >= Array.from(title).length - 1) break;
  }

  const titleLineHeight = Math.round(titleSize * 1.3);
  // Anchor the block so 1-3 lines stay vertically balanced.
  const titleStartY =
    titleLines.length === 1 ? 330 : titleLines.length === 2 ? 300 : 272;

  const tspans = titleLines
    .map(
      (line, i) =>
        `<tspan x="80" y="${titleStartY + i * titleLineHeight}">${escapeXml(line)}</tspan>`,
    )
    .join("");

  const eyebrowText = escapeXml(truncate(eyebrow, 34));
  const metaText = escapeXml(truncate(meta, 44));
  const kindLabel = kind === "briefing" ? "每日简报 · DAILY BRIEFING" : "深度文章 · ARTICLE";

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f7f8fa"/>
      <stop offset="1" stop-color="#e9ecf2"/>
    </linearGradient>
  </defs>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)"/>
  <rect x="0" y="0" width="${WIDTH}" height="10" fill="${ACCENT}"/>

  <rect x="80" y="70" width="54" height="54" rx="11" fill="${ACCENT}"/>
  <text x="107" y="107" text-anchor="middle" font-family="${SANS}" font-size="24" font-weight="700" fill="#ffffff">AI</text>
  <text x="150" y="94" font-family="${SANS}" font-size="21" font-weight="600" fill="${INK}">AI 科技每日早报</text>
  <text x="150" y="120" font-family="${SANS}" font-size="14" fill="${DIM}">AI Daily News · 中文</text>

  <text x="80" y="212" font-family="${SANS}" font-size="17" letter-spacing="2.4" fill="${ACCENT}">${kindLabel}</text>
  <text font-family="${SERIF}" font-size="${titleSize}" font-weight="700" fill="${INK}" letter-spacing="-0.5">${tspans}</text>

  <line x1="80" y1="498" x2="1120" y2="498" stroke="${BORDER}" stroke-width="1"/>
  <text x="80" y="548" font-family="${SANS}" font-size="17" fill="${MUTED}">${eyebrowText}</text>
  <text x="80" y="578" font-family="${SANS}" font-size="15" fill="${DIM}">${metaText}</text>
  <text x="1120" y="548" text-anchor="end" font-family="${MONO}" font-size="17" fill="${DIM}">${escapeXml(date)}</text>
  <text x="1120" y="578" text-anchor="end" font-family="${SANS}" font-size="13" fill="${DIM}">unclejoeyao666.github.io/ai-daily-news</text>
</svg>`;
}

/** Render a 1200×630 PNG cover card. */
export async function renderCoverPng(options: CoverOptions): Promise<Buffer> {
  return sharp(Buffer.from(buildSvg(options)), { density: 144 })
    .resize(WIDTH, HEIGHT)
    .png({ compressionLevel: 9, palette: true })
    .toBuffer();
}

/** Convenience for measurement in tests. */
export const coverMeasure = measure;

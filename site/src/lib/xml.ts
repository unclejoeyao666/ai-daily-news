/**
 * Minimal, dependency-free XML serialisation for the RSS feeds.
 *
 * `@astrojs/rss` is fine for plain feeds, but the syndication endpoints here
 * need full control over namespaces (`content`, `media`, `itunes`, `dc`,
 * `ainews`), CDATA payloads and element ordering, so the XML is emitted
 * directly instead of round-tripping through a parser.
 */

/** Escape text for use in XML character data and attribute values. */
export function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Wrap HTML in a CDATA section.
 *
 * A literal `]]>` cannot appear inside CDATA, so any occurrence is split
 * across two sections, which is the standard workaround.
 */
export function cdata(html: string): string {
  return `<![CDATA[${html.replace(/]]>/g, "]]]]><![CDATA[>")}]]>`;
}

/** `<tag>escaped text</tag>`, omitted entirely when the value is empty. */
export function el(tag: string, value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  return `<${tag}>${esc(value)}</${tag}>`;
}

/** `<tag><![CDATA[html]]></tag>`, omitted when empty. */
export function cdataEl(tag: string, html: string | null | undefined): string {
  if (!html) return "";
  return `<${tag}>${cdata(html)}</${tag}>`;
}

/** Self-closing `<tag k="v" .../>` built from the entries that have values. */
export function selfClosing(
  tag: string,
  attrs: Record<string, string | number | null | undefined>,
): string {
  const parts = Object.entries(attrs)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}="${esc(String(v))}"`);
  return `<${tag} ${parts.join(" ")}/>`;
}

/** RFC 822 / RFC 1123 date, the format RSS 2.0 requires for `pubDate`. */
export function rfc822(date: Date): string {
  return date.toUTCString();
}

/** RFC 3339 / ISO 8601 timestamp, used by JSON Feed and the JSON API. */
export function iso8601(date: Date): string {
  return date.toISOString();
}

/** Assemble an XML document from the root element and namespace map. */
export function xmlDocument(
  namespaces: Record<string, string>,
  body: string,
): string {
  const ns = Object.entries(namespaces)
    .map(([prefix, uri]) => ` xmlns:${prefix}="${esc(uri)}"`)
    .join("");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"${ns}>\n${body}\n</rss>\n`;
}

/**
 * Syndication data layer.
 *
 * Single source of truth for the machine-readable feeds this site publishes:
 *
 *   /rss.xml            RSS 2.0 + content:encoded + media + itunes + dc
 *   /rss-briefings.xml  RSS 2.0 of daily briefings (audio enclosures)
 *   /feed.json          JSON Feed 1.1
 *   /api/news.json      flat JSON API for programmatic integrations
 *
 * Everything is computed at build time from the Astro content collections,
 * so the feeds always match the published site.
 */

import { getCollection, type CollectionEntry } from "astro:content";
import fs from "node:fs";
import path from "node:path";
import {
  SITE_TITLE,
  SITE_TAGLINE,
  SITE_DESCRIPTION,
  SITE_AUTHOR,
  TAG_LABELS,
} from "../consts";

export const FEED_LIMIT = 40;
export const BRIEFING_FEED_LIMIT = 40;

/** Absolute base URL of the published site (Astro `base` included). */
export const SITE_BASE = "https://unclejoeyao666.github.io/ai-daily-news";
export const FEED_LANGUAGE = "zh-CN";

function copyrightYear(): number {
  return new Date().getUTCFullYear();
}

export function articleUrl(id: string): string {
  return `${SITE_BASE}/articles/${id}`;
}

export function briefingUrl(id: string): string {
  return `${SITE_BASE}/briefings/${id}`;
}

export function coverUrl(kind: "article" | "briefing", id: string): string {
  return `${SITE_BASE}/covers/${kind}/${id}.png`;
}

/**
 * `audioUrl` in frontmatter is site-relative and already carries the base
 * path (`/ai-daily-news/audio/2026-10-23.mp3`). SITE_BASE also ends with that
 * base path, so only the origin is prepended.
 */
export function absoluteAudioUrl(audioUrl: string | undefined): string | null {
  if (!audioUrl) return null;
  if (/^https?:\/\//i.test(audioUrl)) return audioUrl;
  const origin = new URL(SITE_BASE).origin;
  return `${origin}${audioUrl.startsWith("/") ? "" : "/"}${audioUrl}`;
}

/**
 * Byte length of a published audio file, read from `site/public` at build
 * time. RSS `enclosure` wants a real length; readers show "unknown" for 0.
 *
 * Returns 0 when the file is absent — a handful of briefings declare an
 * `audioUrl` whose MP3 was never published, and those must not advertise an
 * enclosure that 404s.
 */
export function audioByteSize(audioUrl: string | undefined): number {
  if (!audioUrl) return 0;
  const rel = audioUrl
    .replace(/^https?:\/\/[^/]+/, "")
    .replace(/^\/ai-daily-news/, "")
    .replace(/^\/+/, "");
  try {
    return fs.statSync(path.join(process.cwd(), "public", rel)).size;
  } catch {
    return 0;
  }
}

/** True when the audio file backing this URL is actually published. */
export function audioExists(audioUrl: string | undefined): boolean {
  return audioByteSize(audioUrl) > 0;
}

function tagLabels(tags: readonly string[]): string[] {
  return tags.map((slug) => TAG_LABELS[slug] ?? slug);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Articles, newest first. */
export async function getArticles(): Promise<CollectionEntry<"articles">[]> {
  return (await getCollection("articles")).sort(
    (a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime(),
  );
}

/** Briefings, newest first. */
export async function getBriefings(): Promise<CollectionEntry<"briefings">[]> {
  return (await getCollection("briefings")).sort(
    (a, b) => b.data.date.getTime() - a.data.date.getTime(),
  );
}

/** Articles referenced by a briefing, in briefing order. */
export async function briefingArticles(
  briefing: CollectionEntry<"briefings">,
  index?: Map<string, CollectionEntry<"articles">>,
): Promise<CollectionEntry<"articles">[]> {
  const byId = index ?? new Map((await getArticles()).map((a) => [a.id, a]));
  return briefing.data.articles
    .map((slug) => byId.get(slug))
    .filter((a): a is CollectionEntry<"articles"> => Boolean(a));
}

/**
 * Drop the trailing "原文参考" block from rendered article HTML.
 *
 * That block repeats the original-language quote and source link, which the
 * feeds already carry in structured fields. Keeping it would duplicate
 * content in every reader.
 */
export function stripReferenceBlock(html: string): string {
  const marker = html.search(/<h2[^>]*>[^<]*原文参考/);
  const body = marker >= 0 ? html.slice(0, marker) : html;
  return body.replace(/(<hr\s*\/?>\s*)+$/i, "").trim();
}

/** Plain-text rendering of an HTML fragment. */
export function plainText(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

/** Map a frontmatter language code to its Chinese label. */
export function sourceLangLabel(lang: string): string {
  return { de: "德语原文", en: "英语原文", zh: "中文原创" }[lang] ?? "外文原文";
}

export interface FeedArticle {
  id: string;
  title: string;
  titleOriginal: string;
  description: string;
  pubDate: Date;
  link: string;
  cover: string;
  sourceName: string;
  sourceUrl: string;
  sourceLang: string;
  sourceLangLabel: string;
  tags: string[];
  tagLabels: string[];
  /** Rendered article body HTML, without the trailing reference block. */
  contentHtml: string;
  /** Body as plain text, for `description` fallbacks. */
  contentText: string;
}

export async function buildFeedArticles(limit = FEED_LIMIT): Promise<FeedArticle[]> {
  const articles = (await getArticles()).slice(0, limit);
  return articles.map((article) => {
    const { data } = article;
    const contentHtml = stripReferenceBlock(article.rendered?.html ?? "");
    return {
      id: article.id,
      title: data.title,
      titleOriginal: data.titleOriginal,
      description: data.description,
      pubDate: data.pubDate,
      link: articleUrl(article.id),
      cover: coverUrl("article", article.id),
      sourceName: data.sourceName,
      sourceUrl: data.sourceUrl,
      sourceLang: data.sourceLang,
      sourceLangLabel: sourceLangLabel(data.sourceLang),
      tags: [...data.tags],
      tagLabels: tagLabels(data.tags),
      contentHtml,
      contentText: plainText(contentHtml),
    };
  });
}

export interface FeedBriefing {
  id: string;
  title: string;
  date: Date;
  link: string;
  cover: string;
  audioUrl: string | null;
  audioBytes: number;
  articles: {
    title: string;
    link: string;
    description: string;
    tagLabels: string[];
    sourceName: string;
  }[];
}

export async function buildFeedBriefings(
  limit = BRIEFING_FEED_LIMIT,
): Promise<FeedBriefing[]> {
  const index = new Map((await getArticles()).map((a) => [a.id, a]));
  const briefings = (await getBriefings()).slice(0, limit);

  return Promise.all(
    briefings.map(async (briefing) => {
      const articles = await briefingArticles(briefing, index);
      const bytes = audioByteSize(briefing.data.audioUrl);
      return {
        id: briefing.id,
        title: briefing.data.title,
        date: briefing.data.date,
        link: briefingUrl(briefing.id),
        cover: coverUrl("briefing", briefing.id),
        // Only advertise audio that is actually published.
        audioUrl: bytes > 0 ? absoluteAudioUrl(briefing.data.audioUrl) : null,
        audioBytes: bytes,
        articles: articles.map((a) => ({
          title: a.data.title,
          link: articleUrl(a.id),
          description: a.data.description,
          tagLabels: tagLabels(a.data.tags),
          sourceName: a.data.sourceName,
        })),
      };
    }),
  );
}

/** Channel-level metadata shared by every feed format. */
export const feedMeta = {
  title: SITE_TITLE,
  tagline: SITE_TAGLINE,
  description: SITE_DESCRIPTION,
  author: SITE_AUTHOR,
  site: SITE_BASE,
  language: FEED_LANGUAGE,
  get copyright() {
    return `© ${copyrightYear()} ${SITE_AUTHOR}`;
  },
  isoDate,
};

export { tagLabels };

import type { APIRoute } from "astro";
import {
  buildFeedArticles,
  buildFeedBriefings,
  feedMeta,
  briefingUrl,
} from "../lib/feeds";
import { cdataEl, el, esc, rfc822, selfClosing, xmlDocument } from "../lib/xml";

/**
 * RSS 2.0 — full-fidelity feed.
 *
 * Every item carries:
 *   - title / link / guid / pubDate / category
 *   - description   short Chinese summary
 *   - content:encoded  full article body (HTML)
 *   - media:content   1200×630 cover card
 *   - dc:creator, dc:language
 *   - ainews:*        source name, source URL, original title, language,
 *                     and the daily-briefing that included the article
 *
 * The daily briefing is published as its own item with an `<enclosure>` that
 * points at the MP3, which is what podcast clients consume.
 */

const NS = {
  content: "http://purl.org/rss/1.0/modules/content/",
  media: "http://search.yahoo.com/mrss/",
  itunes: "http://www.itunes.com/dtds/podcast-1.0.dtd",
  dc: "http://purl.org/dc/elements/1.1/",
  atom: "http://www.w3.org/2005/Atom",
  ainews: `${feedMeta.site}/ns/ainews/1.0/`,
};

const AUDIO_TYPE = "audio/mpeg";
const IMAGE_TYPE = "image/png";

function channelHead(selfPath: string, latestCover: string | null): string {
  const now = new Date();
  return [
    el("title", feedMeta.title),
    el("link", `${feedMeta.site}/`),
    el("description", feedMeta.description),
    el("language", feedMeta.language),
    el("copyright", feedMeta.copyright),
    el("managingEditor", feedMeta.author),
    el("webMaster", feedMeta.author),
    el("lastBuildDate", rfc822(now)),
    el("generator", "Astro · ai-daily-news"),
    el("ttl", "60"),
    `<atom:link href="${esc(`${feedMeta.site}${selfPath}`)}" rel="self" type="application/rss+xml"/>`,
    // Channel image must be a real cover; fall back to the latest briefing's.
    latestCover
      ? selfClosing("image", {
          url: latestCover,
          title: feedMeta.title,
          link: `${feedMeta.site}/`,
        })
      : "",
  ]
    .filter(Boolean)
    .join("\n      ");
}

export const GET: APIRoute = async () => {
  const [articles, briefings] = await Promise.all([
    buildFeedArticles(),
    buildFeedBriefings(),
  ]);

  // Map article id -> the most recent briefing that features it.
  const briefingByArticle = new Map<string, { id: string; title: string }>();
  for (const briefing of briefings) {
    for (const item of briefing.articles) {
      const id = item.link.replace(`${feedMeta.site}/articles/`, "");
      if (!briefingByArticle.has(id)) {
        briefingByArticle.set(id, { id: briefing.id, title: briefing.title });
      }
    }
  }

  const briefingItems = briefings.map((briefing) => {
    const enclosure = briefing.audioUrl
      ? selfClosing("enclosure", {
          url: briefing.audioUrl,
          length: briefing.audioBytes || 0,
          type: AUDIO_TYPE,
        })
      : "";

    const list = briefing.articles
      .map(
        (a, i) =>
          `<li><a href="${esc(a.link)}">${esc(a.title)}</a> — ${esc(a.description)}</li>`,
      )
      .join("");

    const contentHtml = `<p>${esc(briefing.title)} · ${briefing.articles.length} 条精选</p><ol>${list}</ol>`;

    return [
      el("title", briefing.title),
      el("link", briefing.link),
      `<guid isPermaLink="true">${esc(briefing.link)}</guid>`,
      el("pubDate", rfc822(briefing.date)),
      el("description", `${briefing.title}：${briefing.articles.length} 条精选 AI 科技动态`),
      cdataEl("content:encoded", contentHtml),
      el("dc:creator", feedMeta.author),
      el("dc:language", feedMeta.language),
      `<category>${esc("每日简报")}</category>`,
      enclosure,
      selfClosing("media:content", {
        url: briefing.cover,
        type: IMAGE_TYPE,
        medium: "image",
        width: 1200,
        height: 630,
      }),
      selfClosing("media:thumbnail", { url: briefing.cover }),
      `<ainews:kind>${esc("briefing")}</ainews:kind>`,
      briefing.audioUrl
        ? `<ainews:audioUrl>${esc(briefing.audioUrl)}</ainews:audioUrl>`
        : "",
      `<ainews:articleCount>${briefing.articles.length}</ainews:articleCount>`,
    ]
      .filter(Boolean)
      .join("\n        ");
  });

  const articleItems = articles.map((article) => {
    const briefing = briefingByArticle.get(article.id);
    return [
      el("title", article.title),
      el("link", article.link),
      `<guid isPermaLink="true">${esc(article.link)}</guid>`,
      el("pubDate", rfc822(article.pubDate)),
      el("description", article.description),
      cdataEl("content:encoded", article.contentHtml),
      el("dc:creator", article.sourceName),
      el("dc:language", feedMeta.language),
      ...article.tagLabels.map((label) => `<category>${esc(label)}</category>`),
      `<source url="${esc(article.sourceUrl)}">${esc(article.sourceName)}</source>`,
      selfClosing("media:content", {
        url: article.cover,
        type: IMAGE_TYPE,
        medium: "image",
        width: 1200,
        height: 630,
      }),
      selfClosing("media:thumbnail", { url: article.cover }),
      `<ainews:kind>${esc("article")}</ainews:kind>`,
      `<ainews:sourceName>${esc(article.sourceName)}</ainews:sourceName>`,
      `<ainews:sourceUrl>${esc(article.sourceUrl)}</ainews:sourceUrl>`,
      `<ainews:originalTitle>${esc(article.titleOriginal)}</ainews:originalTitle>`,
      `<ainews:sourceLang>${esc(article.sourceLang)}</ainews:sourceLang>`,
      `<ainews:tags>${esc(article.tags.join(","))}</ainews:tags>`,
      briefing
        ? `<ainews:briefingUrl>${esc(briefingUrl(briefing.id))}</ainews:briefingUrl>`
        : "",
    ]
      .filter(Boolean)
      .join("\n        ");
  });

  const items = [...briefingItems, ...articleItems]
    .map((body) => `    <item>\n        ${body}\n    </item>`)
    .join("\n");

  const body = `  <channel>
      ${channelHead("/rss.xml", briefings[0]?.cover ?? articles[0]?.cover ?? null)}
${items}
  </channel>`;

  return new Response(xmlDocument(NS, body), {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};

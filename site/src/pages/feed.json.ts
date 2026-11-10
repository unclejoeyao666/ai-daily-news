import type { APIRoute } from "astro";
import {
  buildFeedArticles,
  buildFeedBriefings,
  feedMeta,
  SITE_BASE,
} from "../lib/feeds";

/**
 * JSON Feed 1.1 — https://www.jsonfeed.org/version/1.1/
 *
 * The same payload as `/rss.xml`, for readers and scripts that prefer JSON
 * over XML. Briefings and articles share one stream, newest first.
 *
 * Non-standard members (`_ainews_*`) carry the extra provenance the RSS feed
 * exposes through its `ainews:` namespace.
 */
export const GET: APIRoute = async () => {
  const [articles, briefings] = await Promise.all([
    buildFeedArticles(),
    buildFeedBriefings(),
  ]);

  const briefingByArticle = new Map<string, string>();
  for (const briefing of briefings) {
    for (const item of briefing.articles) {
      const id = item.link.replace(`${SITE_BASE}/articles/`, "");
      if (!briefingByArticle.has(id)) {
        briefingByArticle.set(id, briefing.link);
      }
    }
  }

  const briefingItems = briefings.map((briefing) => ({
    id: briefing.link,
    url: briefing.link,
    title: briefing.title,
    summary: `${briefing.title}：${briefing.articles.length} 条精选 AI 科技动态`,
    content_html: `<p>${briefing.title} · ${briefing.articles.length} 条精选</p><ol>${briefing.articles
      .map(
        (a) =>
          `<li><a href="${a.link}">${a.title}</a> — ${a.description}</li>`,
      )
      .join("")}</ol>`,
    date_published: briefing.date.toISOString(),
    image: briefing.cover,
    language: feedMeta.language,
    authors: [{ name: feedMeta.author, url: `${SITE_BASE}/` }],
    tags: ["每日简报"],
    attachments: briefing.audioUrl
      ? [
          {
            url: briefing.audioUrl,
            mime_type: "audio/mpeg",
            size_in_bytes: briefing.audioBytes || undefined,
            duration_in_seconds: undefined,
            title: briefing.title,
          },
        ]
      : undefined,
    _ainews_kind: "briefing",
    _ainews_article_count: briefing.articles.length,
    _ainews_articles: briefing.articles,
  }));

  const articleItems = articles.map((article) => ({
    id: article.link,
    url: article.link,
    title: article.title,
    summary: article.description,
    content_html: article.contentHtml,
    content_text: article.contentText,
    date_published: article.pubDate.toISOString(),
    image: article.cover,
    language: feedMeta.language,
    authors: [{ name: article.sourceName, url: article.sourceUrl }],
    tags: article.tagLabels,
    _ainews_kind: "article",
    _ainews_source_name: article.sourceName,
    _ainews_source_url: article.sourceUrl,
    _ainews_original_title: article.titleOriginal,
    _ainews_source_lang: article.sourceLang,
    _ainews_tags: article.tags,
    _ainews_briefing_url: briefingByArticle.get(article.id) ?? null,
  }));

  const feed = {
    version: "https://jsonfeed.org/version/1.1",
    title: feedMeta.title,
    home_page_url: `${SITE_BASE}/`,
    feed_url: `${SITE_BASE}/feed.json`,
    description: feedMeta.description,
    icon: `${SITE_BASE}/favicon.svg`,
    language: feedMeta.language,
    authors: [{ name: feedMeta.author, url: `${SITE_BASE}/` }],
    _ainews_site: feedMeta.site,
    _ainews_rss: `${SITE_BASE}/rss.xml`,
    _ainews_generated_at: new Date().toISOString(),
    items: [...briefingItems, ...articleItems],
  };

  return new Response(JSON.stringify(feed, null, 2), {
    headers: {
      "Content-Type": "application/feed+json; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};

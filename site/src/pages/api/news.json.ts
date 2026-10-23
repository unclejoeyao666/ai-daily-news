import type { APIRoute } from "astro";
import {
  buildFeedArticles,
  buildFeedBriefings,
  feedMeta,
  SITE_BASE,
} from "../../lib/feeds";

/**
 * Flat JSON API for programmatic integrations.
 *
 *   /api/news.json           articles + briefings + index
 *   /api/news.json?limit=5   (client-side; the file is fully static)
 *
 * Everything an integrator needs is in one document: article bodies, source
 * attribution, tags with Chinese labels, cover images, audio URLs and the
 * daily-briefing grouping.
 */
export const GET: APIRoute = async () => {
  const [articles, briefings] = await Promise.all([
    buildFeedArticles(),
    buildFeedBriefings(),
  ]);

  const briefingByArticle = new Map<
    string,
    { date: string; title: string; url: string; audioUrl: string | null }
  >();
  for (const briefing of briefings) {
    for (const item of briefing.articles) {
      const id = item.link.replace(`${SITE_BASE}/articles/`, "");
      if (!briefingByArticle.has(id)) {
        briefingByArticle.set(id, {
          date: briefing.date.toISOString().slice(0, 10),
          title: briefing.title,
          url: briefing.link,
          audioUrl: briefing.audioUrl,
        });
      }
    }
  }

  const payload = {
    schema: "ainews.v1",
    generated_at: new Date().toISOString(),
    site: {
      title: feedMeta.title,
      description: feedMeta.description,
      url: `${SITE_BASE}/`,
      language: feedMeta.language,
      author: feedMeta.author,
      feeds: {
        rss: `${SITE_BASE}/rss.xml`,
        json_feed: `${SITE_BASE}/feed.json`,
        api: `${SITE_BASE}/api/news.json`,
      },
    },
    counts: {
      articles: articles.length,
      briefings: briefings.length,
    },
    briefings: briefings.map((briefing) => ({
      id: briefing.id,
      title: briefing.title,
      date: briefing.date.toISOString().slice(0, 10),
      url: briefing.link,
      image: briefing.cover,
      audio_url: briefing.audioUrl,
      audio_bytes: briefing.audioBytes || null,
      article_count: briefing.articles.length,
      articles: briefing.articles.map((a) => ({
        title: a.title,
        url: a.link,
        summary: a.description,
        tags: a.tagLabels,
        source: a.sourceName,
      })),
    })),
    articles: articles.map((article) => ({
      id: article.id,
      title: article.title,
      title_original: article.titleOriginal,
      summary: article.description,
      url: article.link,
      image: article.cover,
      published_at: article.pubDate.toISOString(),
      source: {
        name: article.sourceName,
        url: article.sourceUrl,
        language: article.sourceLang,
        language_label: article.sourceLangLabel,
      },
      tags: article.tagLabels,
      tag_slugs: article.tags,
      content_html: article.contentHtml,
      content_text: article.contentText,
      briefing: briefingByArticle.get(article.id) ?? null,
    })),
  };

  return new Response(JSON.stringify(payload, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=3600",
    },
  });
};

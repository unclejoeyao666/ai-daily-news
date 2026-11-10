import type { APIRoute, GetStaticPaths } from "astro";
import { getCollection } from "astro:content";
import { renderCoverPng, type CoverKind } from "../../../lib/cover";
import { TAG_LABELS } from "../../../consts";
import { FEED_LIMIT, BRIEFING_FEED_LIMIT } from "../../../lib/feeds";

/**
 * Static PNG cover cards, so syndicated items always carry an image
 * (`media:content`, `itunes:image`, JSON Feed `image`).
 *
 *   /covers/article/<article-id>.png
 *   /covers/briefing/<YYYY-MM-DD>.png
 *
 * Only the window published by the feeds is rendered: rasterising all ~1,260
 * articles costs ~150s of build time for images no feed ever references.
 * Cover URLs are deterministic, so widening FEED_LIMIT is all it takes to
 * publish more.
 */
export const getStaticPaths: GetStaticPaths = async () => {
  const [articles, briefings] = await Promise.all([
    getCollection("articles"),
    getCollection("briefings"),
  ]);

  const recentArticles = [...articles]
    .sort((a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime())
    .slice(0, FEED_LIMIT);

  const recentBriefings = [...briefings]
    .sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
    .slice(0, BRIEFING_FEED_LIMIT);

  return [
    ...recentArticles.map((article) => ({
      params: { kind: "article", slug: article.id },
      props: {
        kind: "article" as CoverKind,
        title: article.data.title,
        eyebrow: `来源：${article.data.sourceName}`,
        meta: (article.data.tags as string[])
          .map((t) => TAG_LABELS[t] ?? t)
          .join(" · "),
        date: article.data.pubDate.toISOString().slice(0, 10),
      },
    })),
    ...recentBriefings.map((briefing) => ({
      params: { kind: "briefing", slug: briefing.id },
      props: {
        kind: "briefing" as CoverKind,
        title: briefing.data.title.replace(/^AI 科技每日早报\s*—\s*/, ""),
        eyebrow: `${briefing.data.articles.length} 条精选 · 中文音频简报`,
        meta: "AI Daily News 每日早报",
        date: briefing.data.date.toISOString().slice(0, 10),
      },
    })),
  ];
};

export const GET: APIRoute = async ({ props }) => {
  const png = await renderCoverPng(
    props as Parameters<typeof renderCoverPng>[0],
  );
  return new Response(new Uint8Array(png), {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
};

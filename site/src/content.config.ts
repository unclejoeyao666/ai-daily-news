import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';
import { TAG_SLUGS } from './consts';

const tagEnum = z.enum(TAG_SLUGS as [string, ...string[]]);

const articles = defineCollection({
  loader: glob({ base: './src/content/articles', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    titleOriginal: z.string(),
    description: z.string().max(300),
    pubDate: z.coerce.date(),
    sourceName: z.string(),
    sourceUrl: z.string().url(),
    sourceLang: z.enum(['de', 'en', 'zh']).default('en'),
    tags: z.array(tagEnum).min(1).max(3),
    heroImage: z.string().optional(),
  }),
});

const briefings = defineCollection({
  loader: glob({ base: './src/content/briefings', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    audioUrl: z.string().optional(),
    articles: z.array(z.string()).min(1).max(15),
  }),
});

export const collections = { articles, briefings };

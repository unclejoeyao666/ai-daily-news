// @ts-check
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://unclejoeyao666.github.io',
  base: '/ai-daily-news',
  trailingSlash: 'never',
  integrations: [mdx(), sitemap()],
});

// Site-wide constants. Tag taxonomy is loaded from data/tags.json
// at build time — to add a new tag, edit data/tags.json and rebuild.
import tagsConfig from "../../data/tags.json";

export const SITE_TITLE = "AI 科技每日早报";
export const SITE_TAGLINE = "AI Daily News — 中文";
export const SITE_DESCRIPTION =
  "每日全球 AI 科技动态：模型发布、智能体、研究突破、政策监管、芯片、融资。AI 中文翻译与影响分析。";
export const SITE_AUTHOR = "AI Daily News";

interface TagSpec {
  slug: string;
  label_cn: string;
  color: string;
  description?: string;
}

const tagsArr = (tagsConfig as { tags: TagSpec[] }).tags;

export const TAG_LABELS: Record<string, string> = Object.fromEntries(
  tagsArr.map((t) => [t.slug, t.label_cn])
);
export const TAG_COLORS: Record<string, string> = Object.fromEntries(
  tagsArr.map((t) => [t.slug, t.color])
);
export const TAG_DESCRIPTIONS: Record<string, string> = Object.fromEntries(
  tagsArr.map((t) => [t.slug, t.description ?? ""])
);
export const TAG_SLUGS = tagsArr.map((t) => t.slug);

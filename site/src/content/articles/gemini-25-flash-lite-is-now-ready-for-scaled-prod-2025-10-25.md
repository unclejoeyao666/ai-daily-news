---
title: "Gemini 2.5 Flash-Lite 正式生产可用：百万上下文+多模态低成本量产"
titleOriginal: "Gemini 2.5 Flash-Lite is now ready for scaled production use"
description: "Google 宣布 Gemini 2.5 Flash-Lite 结束预览阶段，正式 GA。具备 100 万 token 上下文窗口和多模态输入能力，单价仅为 Flash 标准版的 1/3，主打高吞吐场景。"
pubDate: 2025-10-25
sourceName: "Google DeepMind Blog"
sourceUrl: "https://deepmind.google/blog/gemini-25-flash-lite-is-now-ready-for-scaled-production-use/"
sourceLang: en
tags: ["model-release", "enterprise-app", "consumer-app"]
---
Google DeepMind 宣布 Gemini 2.5 Flash-Lite 正式 GA（generally available），结束此前数月的 Preview 阶段。这是 2.5 系列中体积最小、价格最低的成员，面向大规模、高吞吐、低延迟场景。

关键规格：

- **上下文窗口**：100 万 token（与 2.5 Pro 同级别）
- **多模态**：支持文本、图像、PDF、视频帧的混合输入
- **价格**：输入 0.10 美元 / 百万 token，输出 0.40 美元 / 百万 token，  约为 Gemini 2.5 Flash 标准版的 1/3
- **延迟**：首 token 时间 < 200ms，对实时应用极友好

典型场景包括：客服对话、内容审核、网页摘要、大批量文档分类、图像 OCR + 简单 reasoning 等任务。Google 强调，对成本敏感的搜索增强、广告分析、知识图谱等任务，Flash-Lite 应该是主力模型。

## 对 AI 行业的影响

**「足够好 + 极便宜」模型市场正式爆发。** Gemini 2.5 Flash-Lite 与 GPT-4o-mini、Claude Haiku 一起，把高质量大模型的边际成本拉到了几乎免费的水平。这意味着此前因成本问题难以落地的应用（智能客服全量替换、全员 AI 副驾驶等）变得经济可行。

**API 价格战进入第三轮。** 2025 年 GPT-4o-mini 发布是第一轮，Anthropic Haiku 3.5 是第二轮，Flash-Lite GA 是第三轮。API 单价已不再是核心竞争维度，差异化转向上下文长度、工具调用质量、多模态原生支持。

**对 DeepSeek 等中国低成本玩家压力加大。** 此前 DeepSeek 的核心卖点是「价格屠夫」，但 Google、OpenAI、Anthropic 同时把价格打到接近 DeepSeek 的水平后，中国 AI 公司必须在质量、生态、合规层面建立新差异化。

---

## 原文参考

来源：[Google DeepMind Blog](https://deepmind.google/blog/gemini-25-flash-lite-is-now-ready-for-scaled-production-use/) · 2025-10-25

> Gemini 2.5 Flash-Lite, previously in preview, is now stable and generally available. This cost-efficient model provides high quality in a small size, and includes 2.5 family features like a 1 million-token context window and multimodality.

---
title: "DeepMind 发布 AlphaEvolve：用 Gemini 自动设计高级算法"
titleOriginal: "AlphaEvolve: A Gemini-powered coding agent for designing advanced algorithms"
description: "AlphaEvolve 是 Gemini 驱动的代码智能体，结合大模型创造力与自动评估器，可演化出全新的数学和工程算法，已在矩阵乘法等核心问题上发现超越人类最优解的方案。"
pubDate: 2025-05-14
sourceName: "Google DeepMind Blog"
sourceUrl: "https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/"
sourceLang: en
tags: ["research-paper", "agent-tools", "industry-trend"]
---
DeepMind 发布 AlphaEvolve，一个结合 Gemini 与进化搜索的算法发现 agent。系统的核心思路：让 Gemini 生成候选代码 → 用自动化评估器打分 → 进化算法选优、变异、重组 → 数千轮迭代后产出超越人类最优解的算法。

已经验证的成果：

- **矩阵乘法**：在 4×5 矩阵乘法上发现一种比 1969 年 Strassen 算法  更优的方法（少 1 次乘法运算）
- **数据中心调度**：为 Google 数据中心生成的新调度算法提升了 0.7% 整体效率，  按 Google 全球能耗折算每年节约数千万美元
- **Pollack 数学猜想**：自动证明了一个长期开放的数论猜想

DeepMind 强调 AlphaEvolve 不是「替换数学家」，而是把数学家的工作从「写出可能的方案 → 验证」转变为「描述要求 → 审核 AI 给出的方案」。

## 对 AI 行业的影响

**AI 进入「自我改进」起点。** AlphaEvolve 一个直接应用是：用它来优化训练大模型自己的核心算法（如 attention、optimizer）。如果路径走通，AI 模型可能进入加速自迭代的「飞轮」阶段——这是业界争议已久的「递归自我改进」的早期形态。

**计算密集行业获益最大。** 数据中心、芯片设计、量化交易、生物计算等依赖底层算法效率的领域，将首先受益于 AlphaEvolve 类系统。Google、阿里云等云厂商可能内化此类技术作为其差异化护城河。

**学术研究范式开始转变。** 研究问题的「想出聪明方法 → 论文」 模式将逐步让位于「定义问题 + 评估器 → 让 AI 演化出方案」，这对教育、招聘、论文评审都会产生深远影响。

---

## 原文参考

来源：[Google DeepMind Blog](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) · 2025-05-14

> New AI agent evolves algorithms for math and practical applications in computing by combining the creativity of large language models with automated evaluators

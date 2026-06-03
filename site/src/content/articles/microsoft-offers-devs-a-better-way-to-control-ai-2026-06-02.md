---
title: "微软发布开放标准 ACS 让开发者精准控制 AI 智能体行为"
titleOriginal: "Microsoft offers devs a better way to control AI agent behavior"
description: "微软推出开源的 Agent Control Specification 标准，允许开发、合规和安全团队通过可移植的策略文件定义智能体行为边界，在多个拦截点自动检查智能体是否越界。"
pubDate: 2026-06-02
sourceName: "TechCrunch AI"
sourceUrl: "https://techcrunch.com/2026/06/02/microsoft-offers-devs-a-better-way-to-control-ai-agent-behavior/"
sourceLang: en
tags: ["agent-tools", "enterprise-app"]
---
## 报道核心

微软在 6 月 2 日发布了一项名为 Agent Control Specification 的开源新标准，旨在解决企业部署 AI 智能体时面临的核心难题：如何确保智能体在不同环境和任务中始终按预期行事。

## 关键细节

ACS 允许开发团队、合规团队和安全团队定义智能体的策略文件，明确智能体可以做什么、禁止做什么、何时需要人工审批、哪些操作需要记录留档。这些策略文件在智能体执行任务时的多个拦截点自动检查——包括接收输入前、调用工具前、工具返回结果后、以及最终响应用户前——确保智能体始终在护栏内运行。

## 行业反应

当前开发者通常通过系统提示词、自定义代码检查或分类器来管控智能体行为，但这些方法往往碎片化、难以审计且不易跨框架复用。ACS 将这些控制整合到统一的治理层，为企业大规模部署 AI 智能体提供了关键基础设施。面对业界对工具误用和级联失败的担忧，微软此举回应了企业对可控 AI 代理的迫切需求。

## 对 AI 行业的影响

ACS 解决了企业 AI 落地中的关键信任障碍——没有可靠的行为管控，企业不敢让智能体触及核心业务流程。这一标准若被广泛采用，将大幅加速企业级 AI 代理的部署速度，同时为合规审计提供了标准化工具。对 Anthropic 和 OpenAI 等竞争者来说，微软以开源标准制定者的身份占领治理层高地，将形成生态锁定效应。

---

## 原文参考

来源：[TechCrunch AI](https://techcrunch.com/2026/06/02/microsoft-offers-devs-a-better-way-to-control-ai-agent-behavior/) · 2026-06-02

> The specification lets developer, compliance, and security teams define their own policies for agents to follow in portable policy files.

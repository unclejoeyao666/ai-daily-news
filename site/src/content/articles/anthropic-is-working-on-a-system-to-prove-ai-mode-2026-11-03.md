---
title: "Anthropic 研发用于验证 AI 模型身份的系统"
titleOriginal: "Anthropic is working on a system to prove AI models’ identity"
description: "Anthropic 正研究名为 FlashProve 的开源系统，通过加密证明核实 AI 输出是否确由其声称的模型生成。它旨在防止模型被暗中替换，也可验证第三方关于模型执行任务的说法；目前仍属研究，Anthropic 尚无部署计划。"
pubDate: 2026-11-03
sourceName: "TechCrunch AI"
sourceUrl: "https://techcrunch.com/2026/11/03/anthropic-is-working-on-a-system-to-prove-ai-models-identity/"
sourceLang: en
tags: ["open-source", "safety-alignment"]
---
Anthropic 研究人员公布了 FlashProve 的研究进展。这套“可证明推理”系统为模型输出提供加密证明，使用户能够核验回答是否来自指定模型，并抵御包括模型运营方在内的冒名或替换。要使用该系统，模型实验室需为每个发布的模型公布可与输出匹配的指纹；指纹不会泄露模型权重，也被设计为可在本地设备轻量验证。Anthropic 同时公开了技术规格和部分开源代码。研究仍在进行，团队表示目前没有在 Anthropic 或其他实验室部署该系统的计划。

## 对 AI 行业的影响

如果这类证明能跨模型和部署环境可靠运行，用户、企业审计方及监管者就能把模型身份纳入可核验的服务承诺，降低服务商暗中换用较低成本模型或第三方夸大模型能力的空间。落地仍依赖模型厂商持续发布指纹、验证工具兼容及行业标准形成；目前它只是研究原型，实际治理效果尚未验证。

---

## 原文参考

来源：[TechCrunch AI](https://techcrunch.com/2026/11/03/anthropic-is-working-on-a-system-to-prove-ai-models-identity/) · 2026-11-03

> Called FlashProve, the system would let anyone check that an AI response really came from the model it claims to be from.

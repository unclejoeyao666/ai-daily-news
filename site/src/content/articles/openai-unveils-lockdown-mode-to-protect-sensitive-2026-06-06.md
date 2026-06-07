---
title: "OpenAI 推出锁定模式防御提示注入攻击"
titleOriginal: "OpenAI unveils Lockdown Mode to protect sensitive data from prompt injection attacks"
description: "OpenAI 推出 ChatGPT Lockdown Mode（锁定模式），旨在降低提示注入攻击导致敏感数据泄露的风险，但该模式并不能完全消除所有攻击向量。"
pubDate: 2026-06-06
sourceName: "TechCrunch AI"
sourceUrl: "https://techcrunch.com/2026/06/06/openai-unveils-lockdown-mode-to-protect-sensitive-data-from-prompt-injection-attacks/"
sourceLang: en
tags: ["safety-alignment", "enterprise-app"]
---
## 事件概述

OpenAI 于 6 月 6 日推出了 ChatGPT 的 Lockdown Mode（锁定模式），这一安全功能的核心目标是减少提示注入（prompt injection）攻击中敏感数据泄露的可能性。

## 技术细节

Lockdown Mode 通过限制模型对用户输入的过度信任，在一定程度上隔离了恶意指令的渗透。OpenAI 表示，该模式能显著降低攻击者通过精心构造的系统提示来窃取对话历史或用户数据的风险。但官方也坦诚指出，锁定模式并不能完全免疫所有类型的提示注入攻击，属于纵深防御策略的一环。

## 行业影响

随着 ChatGPT 在企业场景中的深度部署，提示注入攻击已成为大模型安全领域最棘手的挑战之一。Lockdown Mode 是对企业客户安全诉求的直接回应，并为整个行业提供了一种可参考的安全设计范式。

## 对 AI 行业的影响

Lockdown Mode 表明 OpenAI 正加速向企业级安全合规靠拢，对 Anthropic 和 Google 形成竞争压力——三巨头均需在 agent 安全能力上快速迭代。该模式若能有效落地，将直接推动大模型在企业内部场景的渗透率。

---

## 原文参考

来源：[TechCrunch AI](https://techcrunch.com/2026/06/06/openai-unveils-lockdown-mode-to-protect-sensitive-data-from-prompt-injection-attacks/) · 2026-06-06

> Even with Lockdown Mode, ChatGPT could be still vulnerable to prompt injections, but the goal is to reduce the likelihood that sensitive data gets shared in the process.

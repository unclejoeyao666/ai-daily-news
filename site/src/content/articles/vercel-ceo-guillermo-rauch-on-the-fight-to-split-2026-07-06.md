---
title: "Vercel CEO 谈模型与智能体分离：生产环境只看性价比"
titleOriginal: "Vercel CEO Guillermo Rauch on the fight to split off models from agents"
description: "Vercel CEO Guillermo Rauch 接受 TechCrunch 采访，阐述 AI 应用从单一模型走向多模型多智能体架构的趋势，强调生产环境中价格性能比才是决定性因素。"
pubDate: 2026-07-06
sourceName: "TechCrunch AI"
sourceUrl: "https://techcrunch.com/2026/07/06/vercel-ceo-guillermo-rauch-on-the-fight-to-split-off-models-from-agents/"
sourceLang: en
tags: ["agent-tools", "enterprise-app"]
---
## 报道核心

Guillermo Rauch 在采访中提出了一个行业共识正在形成的判断：AI 应用架构正在将「模型层」与「智能体层」分离。模型负责推理和理解，智能体负责编排、工具调用和工作流执行，两者的选型逻辑完全不同。

## 关键细节

Rauch 指出，在开发阶段人们追求最强模型，但进入生产环境后，价格性能比成为核心指标。很多任务用 GPT 四点一 mini 或 Claude Haiku 就能完成，无需调用最贵的旗舰模型。Vercel 的 v0 平台已经在实践这一思路，根据任务复杂度动态路由到不同模型。

## 行业反应

这一观点呼应了 Dify、LangChain 等框架的发展方向。Anthropic 和 OpenAI 也在分别构建 Claude Code 和 Responses API 的 agent 层，与底层推理模型解耦。模型路由创业公司如 OpenRouter 和 Martian 正成为这一趋势的受益者。

## 对 AI 行业的影响

对 OpenAI 和 Anthropic，模型与 agent 分离意味着旗舰模型的调用频率可能下降，但 agent 平台的粘性更高。对 Vercel，这一架构趋势直接利好其 v0 和 AI SDK 业务。对开发者，多模型路由将成为标配能力，OpenRouter 类中间层和 Vercel AI SDK 等工具链的价值将持续上升。

---

## 原文参考

来源：[TechCrunch AI](https://techcrunch.com/2026/07/06/vercel-ceo-guillermo-rauch-on-the-fight-to-split-off-models-from-agents/) · 2026-07-06

> "The reality is, when you're optimizing for production, you start looking at a price/performance," Guillermo Rauch tells TechCrunch.

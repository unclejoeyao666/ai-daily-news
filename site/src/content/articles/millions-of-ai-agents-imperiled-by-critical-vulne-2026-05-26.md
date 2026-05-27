---
title: "Starlette 框架曝高危漏洞，数百万 AI 智能体面临攻击风险"
titleOriginal: "Millions of AI agents imperiled by critical vulnerability in open source package"
description: "开源框架 Starlette 被发现高危漏洞 BadHost（CVE-2026-48710），影响 FastAPI、vLLM 等大量 Python AI 工具链，攻击者可借 HTTP Host 头绕过授权直接访问 MCP 服务器中的数据库、凭证等敏感数据。"
pubDate: 2026-05-26
sourceName: "Ars Technica"
sourceUrl: "https://arstechnica.com/information-technology/2026/05/millions-of-ai-agents-imperiled-by-critical-vulnerability-in-open-source-package/"
sourceLang: en
tags: ["safety-alignment", "open-source"]
---
## 报道核心

安全研究员在 Starlette 框架中发现高危漏洞 BadHost（CVE-2026-48710），该框架每周下载量达 3.25 亿次，是 FastAPI、vLLM、LiteLLM 等众多 Python AI 工具的核心依赖。漏洞利用方式极为简单——在 HTTP Host 头中注入一个字符即可绕过基于路径的授权检查。

## 影响范围

受影响的不仅是 AI 智能体本身，还涵盖 MCP 协议服务器、模型管理界面、评估仪表盘等整个生态。X41 D-Sec 扫描发现，暴露的数据包括临床试验数据库、生物识别信息、邮件系统、HR 招聘数据、云监控拓扑等敏感内容。

## 行业反应

虽然 CVSS 评分为 7 分（高危），发现方认为实际风险被“实质性低估”。X41 D-Sec 与 Nemesis 已推出在线检测工具。Starlette 1.0.1 版本已修复该漏洞，建议所有使用 Starlette 的项目立即升级。

## 对 AI 行业的影响

该漏洞波及整个 Python AI 工具链，从推理服务到 agent 框架无一幸免。对使用 FastAPI 构建 MCP 服务器的团队而言，这是一次紧急安全升级通知。OpenAI、Anthropic 等生态参与者需评估其依赖链是否受影响，安全审查应成为 AI 基础设施的标准环节。

---

## 原文参考

来源：[Ars Technica](https://arstechnica.com/information-technology/2026/05/millions-of-ai-agents-imperiled-by-critical-vulnerability-in-open-source-package/) · 2026-05-26

> "BadHost" was found in Starlette, a package with 325 million weekly downloads.

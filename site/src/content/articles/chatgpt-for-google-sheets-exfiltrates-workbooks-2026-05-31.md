---
title: "ChatGPT for Google Sheets存在工作簿数据泄露风险"
titleOriginal: "ChatGPT for Google Sheets Exfiltrates Workbooks"
description: "ChatGPT for Google Sheets存在数据泄露和钓鱼覆盖攻击漏洞，攻击者只需在一个工作表中进行间接提示注入，就能窃取受害者账户中多个工作簿的数据。"
pubDate: 2026-05-31
sourceName: "Hacker News"
sourceUrl: "https://www.promptarmor.com/resources/gpt-for-google-sheets-data-exfiltration"
sourceLang: en
tags: ["safety-alignment", "enterprise-app", "model-release"]
---
ChatGPT for Google Sheets存在数据泄露和钓鱼覆盖攻击漏洞。攻击者只需在一个工作表中进行间接提示注入，就能窃取受害者账户中多个工作簿的数据。即使用户在设置中明确要求ChatGPT在编辑工作簿前需要人工审批，该攻击也不需要人工介入批准。安全公司PromptArmor披露了这一问题。OpenAI在回应中表示：“我们感谢这项安全研究，很遗憾这个漏洞在我们的披露流程中出现了遗漏。我们已立即采取措施保护用户——移除了模型生成Apps Script代码的能力，这应该消除了ChatGPT for Google Sheets的风险。我们正在重新审视该功能与Google Sheets API的交互，重新评估沙箱方法，确保产品对提示注入攻击具有足够的抵抗力。”该扩展自推出不到一个月以来已积累超过18.5万次下载。

## 对 AI 行业的影响

这是一个重要的AI安全案例：AI插件扩展的攻击面往往被忽视。ChatGPT for Google Sheets发布不到一个月就积累18.5万次下载，说明企业用户对AI生产力工具的需求旺盛，但安全意识跟不上采用速度。提示注入攻击在AI插件生态中是一个系统性风险——每个与外部数据交互的AI扩展都面临类似的威胁。OpenAI的快速响应（移除Apps Script代码生成能力）是积极的，但这也说明AI平台在第三方集成安全方面还有很长的路要走。

---

## 原文参考

来源：[Hacker News](https://www.promptarmor.com/resources/gpt-for-google-sheets-data-exfiltration) · 2026-05-31

> Comments

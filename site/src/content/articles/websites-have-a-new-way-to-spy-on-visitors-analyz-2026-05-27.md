---
title: "网站新追踪手段：通过浏览器测量你的 SSD 活动"
titleOriginal: "Websites have a new way to spy on visitors: analyzing their SSD activity"
description: "安全研究人员发现一种名为 FROST 的新型追踪技术，可通过浏览器 JavaScript 测量用户 SSD 的 I/O 操作时序，进而推断用户打开的其他网站和应用程序，无需用户任何交互。"
pubDate: 2026-05-27
sourceName: "Ars Technica"
sourceUrl: "https://arstechnica.com/security/2026/05/websites-have-a-new-way-to-spy-on-visitors-analyzing-their-ssd-activity/"
sourceLang: en
tags: ["research-paper", "safety-alignment"]
---
## 报道核心

研究人员公布了名为 FROST（基于 OPFS SSD 时序的远程指纹识别）的新型追踪技术。通过浏览器 JavaScript 与 OPFS（源私有文件系统）交互，测量 SSD 的 I/O 操作延迟，再利用预训练的卷积神经网络分析，即可推断设备上打开的其他网站和应用。

## 关键细节

FROST 利用了竞争侧信道攻击原理。攻击者需在 OPFS 中创建一个数 GB 的大文件，通过持续读取该文件测量 SSD 的争用延迟。该攻击在 M2 Mac 上完整验证，在 Linux 上已验证基础原理可行。研究人员建议限制 OPFS 文件大小作为防御手段。

## 行业反应

这项研究将在七月的 DIMVA 安全会议上发布。目前没有证据表明 FROST 已在野外被利用，但它展示了浏览器 API 日益复杂带来的新攻击面。

## 对 AI 行业的影响

FROST 提醒我们，随着浏览器演变为操作系统级平台，OPFS 等功能虽为创新应用提供支持，但也打开了新的隐私泄露通道。对浏览器厂商而言，需要在 API 功能与隐私保护之间重新平衡。对用户而言，及时关闭不用的标签页仍是最简单的防御手段。

---

## 原文参考

来源：[Ars Technica](https://arstechnica.com/security/2026/05/websites-have-a-new-way-to-spy-on-visitors-analyzing-their-ssd-activity/) · 2026-05-27

> Telltale SSD activity can be measured in the browser using simple JavaScript.

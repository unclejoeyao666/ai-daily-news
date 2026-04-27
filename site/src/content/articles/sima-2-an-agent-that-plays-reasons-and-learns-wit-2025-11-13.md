---
title: "DeepMind 发布 SIMA 2：能在 3D 虚拟世界中思考和学习的 Gemini 智能体"
titleOriginal: "SIMA 2: An Agent that Plays, Reasons, and Learns With You in Virtual 3D Worlds"
description: "SIMA 2 是 DeepMind 第二代具身智能体，由 Gemini 驱动，可以在《Minecraft》《GTA V》等多种 3D 交互环境中理解指令、规划、推理并采取行动。"
pubDate: 2025-11-13
sourceName: "Google DeepMind Blog"
sourceUrl: "https://deepmind.google/blog/sima-2-an-agent-that-plays-reasons-and-learns-with-you-in-virtual-3d-worlds/"
sourceLang: en
tags: ["agent-tools", "research-paper", "model-release"]
---
Google DeepMind 发布了 SIMA 2（Scalable Instructable Multiworld Agent v2），第二代可扩展、可指令的多世界智能体。这是一个由 Gemini 驱动的 agent，能在多种 3D 虚拟环境中协同人类玩家完成复杂任务。

与 2024 年的初代 SIMA 相比，SIMA 2 的显著突破在于：

- **跨游戏泛化**：训练时只见过《No Man's Sky》《Goat Simulator 3》等几款游戏，  测试时能直接迁移到完全没见过的《Valheim》《GTA V》上工作
- **多步推理**：能拆解「先采集木头、再造工作台、再造斧头」这样的  10 步以上长链任务
- **从经验中学习**：可以从用户演示中持续学习新行为，无需重新训练模型

DeepMind 强调，SIMA 2 不是为玩游戏而设计——3D 虚拟世界是机器人具身智能的训练场。SIMA 学到的导航、操作、规划能力，可以迁移到 Gemini Robotics 1.5 这样的实体机器人上。

## 对 AI 行业的影响

**具身智能的「ImageNet 时刻」可能在 3D 游戏中发生。** SIMA 2 用游戏作为海量、低成本的具身训练数据源，与 OpenAI、Tesla、Figure 等公司高昂的真机数据采集形成鲜明对比。如果路线被验证，将大幅降低具身 AI 训练成本。

**游戏行业意外成为 AI 研究基础设施。** 此前游戏被视为 AI 的应用场景，现在游戏厂商（特别是开放世界的）正在变成 AI 训练数据的提供方。Roblox、米哈游等具备 3D 内容生成能力的公司可能受益。

**对中国机器人公司的提示。** 优必选、宇树等公司正大力投入实体机器人，SIMA 路线表明：仅靠真机数据不够，结合大规模虚拟环境训练才能达到通用泛化。国内具身 AI 团队需要类似的虚拟训练 stack。

---

## 原文参考

来源：[Google DeepMind Blog](https://deepmind.google/blog/sima-2-an-agent-that-plays-reasons-and-learns-with-you-in-virtual-3d-worlds/) · 2025-11-13

> Introducing SIMA 2, a Gemini-powered AI agent that can think, understand, and take actions in interactive environments.

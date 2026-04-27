---
title: "Gemini Robotics 1.5：将 AI 智能体带入物理世界"
titleOriginal: "Gemini Robotics 1.5 brings AI agents into the physical world"
description: "DeepMind 发布 Gemini Robotics 1.5，实现机器人感知、规划、思考、使用工具与行动的全链路一体化模型，迈向通用具身智能体的关键一步。"
pubDate: 2025-10-23
sourceName: "Google DeepMind Blog"
sourceUrl: "https://deepmind.google/blog/gemini-robotics-15-brings-ai-agents-into-the-physical-world/"
sourceLang: en
tags: ["model-release", "agent-tools", "research-paper"]
---
DeepMind 周三发布 Gemini Robotics 1.5，正式将 Gemini 大模型扩展到物理机器人领域。这一代将「视觉-语言-动作」（VLA）模型升级为「视觉-语言-推理-工具-动作」完整链路，机器人不仅能理解任务、规划步骤，还能使用工具完成多步操作。

三个关键能力：

1. **跨实体迁移**：同一个模型可控制不同形态的机器人（人形、双足、单臂、轮式），   无需为每种硬件单独训练
2. **网页 + 工具调用**：机器人遇到不会的任务时，可主动搜索网页、调用 API、   查阅说明书等
3. **长任务规划**：能完成「整理厨房」「分类回收」等需要 30+ 步的家庭任务

DeepMind 与 Boston Dynamics、Franka Robotics、Apptronik 等多家机器人厂商合作开展商业验证，首批客户包括宝马欧洲工厂的零部件分拣线。

## 对 AI 行业的影响

**机器人 foundation model 路线大获验证。** 与 RT-X、Open X-Embodiment 等数据集的理念相同——用一个大模型驱动所有机器人——但 Gemini Robotics 1.5 是首次在工业级商业部署中实现。这条路线一旦走通，机器人成本结构将和智能手机的 Android 时代一样标准化。

**对国内具身 AI 玩家的紧迫性。** 国内有宇树、优必选、智元等头部机器人公司，但缺少 Gemini 这样的大基础模型直接驱动。短期内中国机器人公司可能在产品形态和成本上保持优势，但智能层面的代差正在拉大。

**对 Apptronik、Figure 的影响。** 这些专注人形机器人的初创公司本期望靠自研 VLA 模型保持差异化，DeepMind 这次合作直接吃掉了一部分合作伙伴，Figure 等独立选手的护城河被进一步压缩。

---

## 原文参考

来源：[Google DeepMind Blog](https://deepmind.google/blog/gemini-robotics-15-brings-ai-agents-into-the-physical-world/) · 2025-10-23

> We’re powering an era of physical agents — enabling robots to perceive, plan, think, use tools and act to better solve complex, multi-step tasks.

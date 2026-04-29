#!/usr/bin/env python3
"""Step 3: AI Translation — 2026-04-29"""
import sys, os, json, sqlite3
sys.path.insert(0, '/Users/unclejoe/Media_Workspace/ai-daily-news')
from scripts.lib.news_db import NewsDB
from pathlib import Path

DB_PATH = "/Users/unclejoe/Media_Workspace/ai-daily-news/data/news.db"
ARCHIVE_DIR = Path("/Users/unclejoe/Media_Workspace/ai-daily-news/daily/2026/2026-04/2026-04-29")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# 10 articles in order
articles = [
    {
        "id": 1513,
        "title": "At his OpenAI trial, Musk relitigates an old friendship",
        "summary": "It's a story Musk has told before -- in interviews and to author Walter Isaacson for his bestselling biography of Musk -- but Tuesday was the first time he said it under oath.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "马斯克在OpenAI庭审中重翻旧账：老朋友为何走向决裂",
        "translated_summary": "这并不是马斯克第一次讲述这个故事——他曾在多次采访和传记作家沃尔特·艾萨克森为其撰写的人物传记中提及——但本周二是他首次在法庭宣誓后公开作证。庭审揭示了马斯克与阿尔特曼之间从合作到决裂的完整轨迹，以及他对OpenAI走向商业化的根本质疑。",
        "impact_analysis": "这场庭审不只是马斯克与OpenAI的法律战，更是一场关于AI公司治理结构的公开审判。马斯克的核心主张是：OpenAI从非营利机构转型为商业实体，背离了其创始使命。这一先例一旦成立，将对全球AI行业的资本结构设计产生深远影响——非营利外壳下的商业化路径将面临更大法律挑战。同时，马斯克的作证策略明显指向阿尔特曼个人，这将影响公众对AGI竞争格局的认知。",
        "industry_tags": ["industry-trend", "policy-regulation", "enterprise-app"],
        "slug": "musk-openai-trial-old-friendship",
    },
    {
        "id": 1514,
        "title": "Amazon is already offering new OpenAI products on AWS",
        "summary": "A day after OpenAI got Microsoft to agree to end exclusive rights, AWS announced a slate of OpenAI model offerings, including a new agent service.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "微软OpenAI分手次日：AWS火速上线OpenAI新产品组合",
        "translated_summary": "就在微软同意终止独家权利的次日，AWS迅速宣布推出包括全新Agent服务在内的OpenAI模型产品线。这一快速响应显示了云厂商在AI模型分发权上的激烈竞争态势，亚马逊不愿让谷歌云独享与OpenAI合作的红利。",
        "impact_analysis": "微软与OpenAI解除独家协议后，AWS在二十四小时内即推出OpenAI产品，说明云厂商对AI模型分发权的争夺已进入白热化阶段。AWS的快速跟进意味着OpenAI模型将同时在微软Azure、亚马逊AWS和谷歌云三大平台上线，分销格局从独家垄断走向三方竞争。对企业客户而言，这意味着更强的议价能力和更灵活的部署选择；对中小型AI应用开发者而言，多云支持将降低单一供应商锁定风险。",
        "industry_tags": ["enterprise-app", "chips-infra", "agent-tools"],
        "slug": "aws-openai-products-launch",
    },
    {
        "id": 1516,
        "title": "Google expands Pentagon's access to its AI after Anthropic's refusal",
        "summary": "After Anthropic refused to allow the DoD to use its AI for domestic mass surveillance and autonomous weapons, Google has signed a new contract with the department.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "Anthropic拒绝五角大楼后，谷歌迅速填补空白签署新合同",
        "translated_summary": "在Anthropic拒绝允许美国国防部将Claude用于大规模监控和自主武器之后，谷歌迅速与该部门签署了一份新的AI合同，扩大了其获取谷歌AI能力的权限。这份合同填补了Anthropic留下的空缺，也使谷歌成为美国军方AI合作的主要供应商。",
        "impact_analysis": "Anthropic的拒绝和谷歌的接替，在AI安全圈引发了广泛讨论。这不是简单的商业决策，而是涉及AI军事化边界的原则性问题。Anthropic的立场是：明确的拒绝将自身定位为有别于谷歌的安全优先企业；而谷歌则用合同行动回答了关于AI军事应用的态度。这将强化市场对AI公司伦理定位的认知分化——安全导向与商业导向的公司将在同一市场接受用户和监管者的差异化审视。",
        "industry_tags": ["policy-regulation", "safety-alignment", "industry-trend"],
        "slug": "google-pentagon-anthropic-refusal",
    },
    {
        "id": 1487,
        "title": "Goldman Staff in Hong Kong Lose Access to Anthropic's Claude",
        "summary": "Goldman Sachs Group Inc.'s staff in Hong Kong no longer have access to Anthropic's Claude, an AI agent that speeds the process of writing computer software, according to a person familiar with the matter.",
        "source_name": "Bloomberg Technology",
        "source_name_cn": "彭博科技",
        "translated_title": "高盛香港员工被禁止使用Anthropic的Claude：地缘AI合规警钟",
        "translated_summary": "据知情人士透露，高盛集团香港员工已无法再使用Anthropic的Claude服务。这一事件发生在地缘政治紧张局势加剧的背景下，涉及跨境数据传输合规、出口管制和金融业AI监管等多重因素。此举对亚洲金融机构使用境外AI工具的模式提出了新的合规挑战。",
        "impact_analysis": "高盛禁用Claude不是孤立事件，而是地缘AI合规深化的标志性信号。当全球最大投行之一开始系统性限制AI工具使用，意味着金融业的AI采购逻辑正在从效能优先转向合规优先。这对Anthropic等境外AI厂商是一个明确的市场信号：亚洲金融中心，特别是香港和新加坡，正在成为AI合规的敏感区域。本地化部署或合规认证将成为AI厂商进入金融行业的必要条件。",
        "industry_tags": ["policy-regulation", "enterprise-app", "china-ai"],
        "slug": "goldman-hong-kong-claude-ban",
    },
    {
        "id": 1526,
        "title": "Claude can now plug directly into Photoshop, Blender, and Ableton",
        "summary": "Anthropic has launched a set of connectors for Claude that allow the AI chatbot to tap into popular creative software, including Adobe's Creative Cloud apps, Affinity, Blender, Ableton, Autodesk, and more.",
        "source_name": "The Verge AI",
        "source_name_cn": "The Verge AI 频道",
        "translated_title": "Anthropic发布Claude创意软件连接器：Photoshop、Blender、Ableton全面接入",
        "translated_summary": "Anthropic为Claude发布了一套全新连接器，使其能够直接调用Photoshop、Blender、Ableton等主流创意软件，实现AI与专业创意工作流的深度整合。这是该公司本月推出Claude Design之后的又一重大动作，旨在将AI能力直接嵌入创意专业人士的日常工具链。",
        "impact_analysis": "Anthropic通过连接器战略，正在将Claude从对话式AI升级为真正的创意工作流操作系统。Photoshop、Blender和Ableton分别代表视觉设计、三维建模和音乐制作三个截然不同的创意领域——Anthropic的连接器覆盖了创意产业的核心工种。如果这套连接器能够稳定运行并获得创意社区认可，Claude将成为第一个真正进入专业创意生产线的AI助理，从本质上改变内容创作的生产方式。",
        "industry_tags": ["agent-tools", "consumer-app", "model-release"],
        "slug": "claude-creative-software-connectors",
    },
    {
        "id": 1520,
        "title": "Red Hat's OpenClaw maintainer just made enterprise Claw deployments a lot safer",
        "summary": "Tank OS puts OpenClaw AI agents into a container that lets it run reliably and more safely, especially for those running fleets of them.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "Red Hat工程师发布Tank OS：企业级OpenClaw Agent安全容器方案",
        "translated_summary": "Red Hat的OpenClaw维护者推出了一款名为Tank OS的新方案，将OpenClaw AI Agent封装在容器中运行，使其更加稳定和安全。该方案特别针对大规模部署AI AgentFleet的企业用户，帮助他们在生产环境中实现更可靠、更可控的Agent运行管理。",
        "impact_analysis": "企业级AI Agent的最大挑战从来不是模型能力，而是生产环境的稳定性和安全性。Tank OS的出现意味着AI Agent正在从实验性工具走向企业级生产系统。Red Hat作为企业级开源的主流推动者，选择在OpenClaw上开发安全容器方案，说明市场已认可Agent在企业场景的长期价值。这将进一步加速大型企业中AI Agent的规模化部署，同时推动企业AI安全的行业标准建设。",
        "industry_tags": ["agent-tools", "enterprise-app", "open-source"],
        "slug": "red-hat-tank-os-openclaw-enterprise",
    },
    {
        "id": 1490,
        "title": "Musk Testifies He's Suing OpenAI to Stop Altman's 'Looting'",
        "summary": "Elon Musk testified Tuesday he's suing OpenAI and two of its co-founders because the startup's pivot from a charity to a for-profit business is wrong and sets a concerning precedent.",
        "source_name": "Bloomberg Technology",
        "source_name_cn": "彭博科技",
        "translated_title": "马斯克庭审作证：起诉OpenAI旨在阻止阿尔特曼\"劫掠\"",
        "translated_summary": "马斯克周二在庭审中作证称，他起诉OpenAI及其两位创始人阿尔特曼和格雷格·布罗克曼，原因是该公司从慈善机构向营利性企业的转型是错误的，并为其他慈善事业树立了令人担忧的先例。马斯克强调，他的目的是阻止这种模式被其他组织复制。",
        "impact_analysis": "马斯克起诉OpenAI的核心法律论点在于：非营利组织转型为营利性公司时，其原始捐赠者和公众是否拥有主张权。如果这一主张在法律上成立，将对全球科技行业的非营利研究机构转型模式产生深远影响。同时，马斯克将阿尔特曼的行为定性为劫掠，是一次精准的舆论战——它直接针对美国社会对慈善信任的敏感神经，可能在陪审团和公众中形成强有力的情感动员。",
        "industry_tags": ["industry-trend", "policy-regulation", "enterprise-app"],
        "slug": "musk-suing-openai-altman-looting",
    },
    {
        "id": 1515,
        "title": "Amazon launches an AI-powered audio Q&A experience on product pages",
        "summary": "Amazon's new \"Join the chat\" feature lets you ask questions about products and receive AI-powered audio responses.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "亚马逊商品页上线AI语音问答：从图文时代进入语音交互时代",
        "translated_summary": "亚马逊在其商品页面推出了一项名为"参与对话"的新功能，用户可以直接向产品提问并获得AI生成的语音回答。这一功能将语音交互引入电商购物流程，改变了消费者获取商品信息的方式，是亚马逊将AI能力嵌入购物体验的核心动作。",
        "impact_analysis": "电商搜索正在从关键词匹配转向对话式交互。亚马逊的语音问答功能表面上是用户体验升级，实质上是在重构购物流程中的信息不对称——消费者不再需要浏览长篇图文，而是直接获得精准的语音答案。这将使中小卖家的图文内容价值被进一步稀释，同时也对平台型电商的搜索逻辑产生深远影响。语音优先的购物体验一旦成为主流，将倒逼品牌方调整产品信息的内容策略。",
        "industry_tags": ["consumer-app", "enterprise-app", "agent-tools"],
        "slug": "amazon-ai-audio-qa-product-pages",
    },
    {
        "id": 1517,
        "title": "Lovable launches its vibe-coding app on iOS and Android",
        "summary": "The app allows developers to vibe code web apps and websites on the go.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "Lovable推出移动端vibe-coding应用：随时随地用自然语言开发网页",
        "translated_summary": "Lovable将其流行的vibe-coding开发体验正式带入iOS和安卓平台，用户可以在移动设备上通过自然语言对话开发网页应用和网站。这一发布将vibe-coding从桌面开发者工具扩展为真正的移动原生应用，进一步降低了应用开发的门槛。",
        "impact_analysis": "vibe-coding的核心价值在于将编程能力民主化，而Lovable的移动化则将其推向了更广泛的用户群体——不仅是专业开发者，还包括创作者、小微创业者等非技术背景用户。移动端的发布意味着开发行为不再受桌面场景限制，随时随地的创意实现将成为可能。这将进一步压缩传统应用开发的时间成本，同时催生一批新型移动端原生应用的涌现。",
        "industry_tags": ["consumer-app", "agent-tools", "open-source"],
        "slug": "lovable-vibe-coding-mobile-app",
    },
    {
        "id": 1521,
        "title": "Otter's new feature lets users search across their enterprise tools",
        "summary": "With this launch, users can connect their Gmail, Google Drive, Notion, Jira, and Salesforce accounts and query that data along with existing meeting data.",
        "source_name": "TechCrunch AI",
        "source_name_cn": "TechCrunch AI 频道",
        "translated_title": "Otter推出企业工具全局搜索：Gmail、Drive、Notion、Jira、Salesforce一站式查询",
        "translated_summary": "Otter发布新功能，用户可将Gmail、谷歌云盘、Notion、Jira和Salesforce账户与现有会议数据连接，在统一界面中跨平台查询所有信息。Otter表示还将很快支持微软Outlook、Teams、SharePoint和Slack的接入。",
        "impact_analysis": "企业协作工具的碎片化是当前工作效率的主要敌人。Otter的跨平台搜索功能本质上是在建立一个企业信息检索的统一入口——它不替代任何单一工具，而是在工具之上构建了一个智能检索层。这个定位非常聪明：它避免了与Salesforce、Notion等平台的直接竞争，同时切入了企业AI搜索这一高需求场景。如果这一模式成立，企业级AI助手的入口形态可能从对话机器人转向垂直搜索层。",
        "industry_tags": ["enterprise-app", "agent-tools", "industry-trend"],
        "slug": "otter-enterprise-tools-search",
    },
]

def num_to_cn(n: str) -> str:
    mapping = {'0':'零','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'}
    return ''.join(mapping.get(c, c) for c in n)

def format_date_cn(date_str: str) -> str:
    y, m, d = date_str.split('-')
    return f"{num_to_cn(y)}年{num_to_cn(m.lstrip('0'))}月{num_to_cn(d.lstrip('0'))}日"

def build_audio_script(articles: list, date_cn: str) -> str:
    """Build TTS-ready Chinese audio script, 1500-2500 chars, no markdown, no URL."""
    lines = []
    lines.append(f"各位好，欢迎收听二零二六年四月二十九日AI科技早报。今天的音频节目将为您带来十条重要资讯，涵盖模型发布、融资动态、行业合作与技术创新。\n")

    items = [
        ("一", "马斯克在OpenAI庭审中重翻旧账：老朋友为何走向决裂",
         "这并不是马斯克第一次讲述这个故事——他曾在多次采访和传记作家沃尔特·艾萨克森为其撰写的人物传记中提及——但本周二是他首次在法庭宣誓后公开作证。庭审揭示了马斯克与阿尔特曼之间从合作到决裂的完整轨迹，以及他对OpenAI走向商业化的根本质疑。",
         "这场庭审不只是马斯克与OpenAI的法律战，更是一场关于AI公司治理结构的公开审判。马斯克的核心主张是：OpenAI从非营利机构转型为商业实体，背离了其创始使命。这一先例一旦成立，将对全球AI行业的资本结构设计产生深远影响——非营利外壳下的商业化路径将面临更大法律挑战。"),

        ("二", "微软OpenAI分手次日：AWS火速上线OpenAI新产品组合",
         "就在微软同意终止独家权利的次日，AWS迅速宣布推出包括全新Agent服务在内的OpenAI模型产品线。亚马逊不愿让谷歌云独享与OpenAI合作的红利，在二十四小时内完成产品上线。",
         "云厂商对AI模型分发权的争夺已进入白热化阶段。AWS的快速跟进意味着OpenAI模型将同时在微软Azure、亚马逊AWS和谷歌云三大平台上线，分销格局从独家垄断走向三方竞争。对企业客户而言，这意味着更强的议价能力和更灵活的部署选择。"),

        ("三", "Anthropic拒绝五角大楼后，谷歌迅速填补空白签署新合同",
         "在Anthropic拒绝允许美国国防部将Claude用于大规模监控和自主武器之后，谷歌迅速与该部门签署了一份新的AI合同，扩大了其获取谷歌AI能力的权限。Anthropic的拒绝和谷歌的接替，在AI安全圈引发了广泛讨论。",
         "这不是简单的商业决策，而是涉及AI军事化边界的原则性问题。Anthropic的拒绝将自身定位为有别于谷歌的安全优先企业；谷歌则用合同行动回答了关于AI军事应用的态度。这将强化市场对AI公司伦理定位的认知分化。"),

        ("四", "高盛香港员工被禁止使用Anthropic的Claude：地缘AI合规警钟",
         "据知情人士透露，高盛集团香港员工已无法再使用Anthropic的Claude服务。这一事件发生在地缘政治紧张局势加剧的背景下，涉及跨境数据传输合规、出口管制和金融业AI监管等多重因素。",
         "高盛禁用Claude不是孤立事件，而是地缘AI合规深化的标志性信号。当全球最大投行之一开始系统性限制AI工具使用，意味着金融业的AI采购逻辑正在从效能优先转向合规优先。本地化部署或合规认证将成为AI厂商进入金融行业的必要条件。"),

        ("五", "Anthropic发布Claude创意软件连接器：Photoshop、Blender、Ableton全面接入",
         "Anthropic为Claude发布了一套全新连接器，使其能够直接调用Photoshop、Blender、Ableton等主流创意软件，实现AI与专业创意工作流的深度整合。这是该公司本月推出Claude Design之后的又一重大动作。",
         "Anthropic正在将Claude从对话式AI升级为真正的创意工作流操作系统。Photoshop、Blender和Ableton分别代表视觉设计、三维建模和音乐制作三个截然不同的创意领域。如果这套连接器能够稳定运行并获得创意社区认可，Claude将成为第一个真正进入专业创意生产线的AI助理。"),

        ("六", "Red Hat工程师发布Tank OS：企业级OpenClaw Agent安全容器方案",
         "Red Hat的OpenClaw维护者推出了一款名为Tank OS的新方案，将OpenClaw AI Agent封装在容器中运行，使其更加稳定和安全。该方案特别针对大规模部署AI Agent Fleet的企业用户。",
         "企业级AI Agent的最大挑战从来不是模型能力，而是生产环境的稳定性和安全性。Red Hat选择在这一领域投入，说明市场已认可Agent在企业场景的长期价值。这将进一步加速大型企业中AI Agent的规模化部署，同时推动企业AI安全的行业标准建设。"),

        ("七", "马斯克庭审作证：起诉OpenAI旨在阻止阿尔特曼\"劫掠\"",
         "马斯克在庭审中作证称，他起诉OpenAI及其两位创始人，是因为该公司从慈善机构向营利性企业的转型是错误的，并为其他慈善事业树立了令人担忧的先例。马斯克强调，他的目的是阻止这种模式被其他组织复制。",
         "马斯克起诉的核心法律论点在于：非营利组织转型为营利性公司时，其原始捐赠者和公众是否拥有主张权。如果这一主张在法律上成立，将对全球科技行业的非营利研究机构转型模式产生深远影响。马斯克将阿尔特曼的行为定性为劫掠，是一次精准的舆论战。"),

        ("八", "亚马逊商品页上线AI语音问答：从图文时代进入语音交互时代",
         "亚马逊在其商品页面推出了一项名为"参与对话"的新功能，用户可以直接向产品提问并获得AI生成的语音回答。这一功能将语音交互引入电商购物流程，改变了消费者获取商品信息的方式。",
         "电商搜索正在从关键词匹配转向对话式交互。语音优先的购物体验一旦成为主流，将倒逼品牌方调整产品信息的内容策略。中小卖家的图文内容价值将被进一步稀释，品牌与平台的博弈将在新的交互维度上展开。"),

        ("九", "Lovable推出移动端vibe-coding应用：随时随地用自然语言开发网页",
         "Lovable将其流行的vibe-coding开发体验正式带入iOS和安卓平台，用户可以在移动设备上通过自然语言对话开发网页应用和网站。这一发布将vibe-coding从桌面开发者工具扩展为真正的移动原生应用。",
         "vibe-coding的核心价值在于将编程能力民主化，而Lovable的移动化则将其推向了更广泛的用户群体——包括创作者、小微创业者等非技术背景用户。移动端的发布意味着开发行为不再受桌面场景限制，随时随地的创意实现将成为可能。"),

        ("十", "Otter推出企业工具全局搜索：Gmail、Drive、Notion、Jira、Salesforce一站式查询",
         "Otter发布新功能，用户可将Gmail、谷歌云盘、Notion、Jira和Salesforce账户与现有会议数据连接，在统一界面中跨平台查询所有信息。Otter表示还将很快支持微软Outlook、Teams、SharePoint和Slack的接入。",
         "Otter的跨平台搜索功能本质上是在建立一个企业信息检索的统一入口——它不替代任何单一工具，而是在工具之上构建了一个智能检索层。如果这一模式成立，企业级AI助手的入口形态可能从对话机器人转向垂直搜索层。"),
    ]

    for num, title, summary, impact in items:
        lines.append(f"\n【头条{num}】{title}")
        lines.append(summary)
        lines.append(impact)

    lines.append("\n以上就是今天的AI科技早报全部内容，感谢收听，我们明天再见。")
    return '\n'.join(lines)

def build_briefing_md(articles: list, date_str: str) -> str:
    lines = []
    lines.append(f"# 🗞️ AI 科技早报 — {date_str}\n")
    lines.append(f"来源：TechCrunch AI、彭博科技、The Verge AI  |  AI翻译驱动\n")
    lines.append("---\n")
    for i, a in enumerate(articles, 1):
        lines.append(f"### {i}. {a['translated_title']}")
        lines.append(f"**来源：** {a['source_name_cn']}  |  **重要性：** {a.get('importance', '')}\n")
        lines.append(f"{a['translated_summary']}\n")
        lines.append(f"**影响分析：** {a['impact_analysis']}\n")
        tags = ', '.join(f'`{t}`' for t in a['industry_tags'])
        lines.append(f"**标签：** {tags}\n")
        lines.append("---\n")
    lines.append("*由 Fanli AI 驱动 | OpenClaw 认知工作流自动生成*")
    return '\n'.join(lines)

if __name__ == "__main__":
    date_str = "2026-04-29"
    date_cn = format_date_cn(date_str)

    # Build audio script
    audio_script = build_audio_script(articles, date_cn)
    audio_script_path = ARCHIVE_DIR / "audio_script.md"
    with open(audio_script_path, 'w', encoding='utf-8') as f:
        f.write(audio_script)
    print(f"✅ audio_script.md → {audio_script_path} ({len(audio_script)} chars)")

    # Build briefing markdown
    briefing_md = build_briefing_md(articles, date_str)
    briefing_path = ARCHIVE_DIR / "briefing.md"
    with open(briefing_path, 'w', encoding='utf-8') as f:
        f.write(briefing_md)
    print(f"✅ briefing.md → {briefing_path}")

    # Update DB
    with NewsDB(DB_PATH) as db:
        for a in articles:
            db.update_translation(
                article_id=a['id'],
                translated_title=a['translated_title'],
                translated_summary=a['translated_summary'],
                translated_body=a['translated_summary'],
                impact_analysis=a['impact_analysis'],
                industry_tags=a['industry_tags'],
                slug=a['slug'],
            )
            print(f"✅ DB updated: {a['id']} → {a['slug']}")

    print("\n✅ Step 3 complete.")

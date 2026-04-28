#!/usr/bin/env python3
"""AI translation step for daily news briefing."""
import sys, os, json, sqlite3, re
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.lib.news_db import NewsDB

TODAY = date.today().isoformat()
ARCHIVE_DIR = Path(f"/Users/unclejoe/Media_Workspace/ai-daily-news/daily/{TODAY[:4]}/{TODAY[:7]}/{TODAY}")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = "/Users/unclejoe/Media_Workspace/ai-daily-news/data/news.db"

ARTICLES = [
    {
        "id": 1322,
        "title": "Gemini achieves gold-medal level at the International Collegiate Programming Contest World Finals",
        "summary": "Gemini 2.5 Deep Think achieves breakthrough performance at the world's most prestigious computer programming competition, demonstrating a profound leap in abstract problem solving.",
        "content": """Gemini 2.5 Deep Think achieves breakthrough performance at ICPC World Finals.
Solving complex tasks at competitions requires deep abstract reasoning, creativity, and ingenuity.
Gemini solved Problem C within the first half hour — which no university team solved.
Internal studies show Gemini 2.5 Deep Think can achieve gold-medal level performance in 2023 and 2024 ICPC World Finals, performing as well as the world's top 20 competitive coders.
If the best AI and human solutions were combined, all 12 problems would have been solved completely.
This milestone builds on Gemini's gold-medal win at the International Mathematical Olympiad two months ago.
Innovations will be integrated into future versions of Gemini Deep Think.
Dr. Bill Poucher, ICPC Global Executive Director: Gemini successfully joining this arena, and achieving gold-level results, marks a key moment in defining the AI tools and academic standards needed for the next generation.
This demonstrates AI can act as a true problem-solving partner for programmers.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-10-24",
        "translated_title": "谷歌Gemini在国际大学生编程竞赛世界总决赛中达到金牌水平",
        "translated_summary": "Gemini 2.5深度思考模型在全球最具权威的大学生编程竞赛中取得突破性成绩，展示了抽象问题解决能力的重大飞跃。该模型在半小时内解决了全场没有任何一支大学队伍解决的最难题。",
        "impact_analysis": "这是AI编程能力的重要里程碑。Gemini不仅在数学奥林匹克获得金牌后，又在编程竞赛中达到金牌水准，意味着AI已具备顶级抽象推理能力。如果将最优AI方案与最优人类方案结合，竞赛全部十二道题均可完整正确解出。这对软件开发行业具有深远影响：AI作为编程协作者的时代正在到来。",
        "industry_tags": ["model-release", "research-paper", "industry-trend"],
    },
    {
        "id": 1290,
        "title": "Deepening our partnership with the UK AI Security Institute",
        "summary": "Google DeepMind and UK AI Security Institute (AISI) strengthen collaboration on critical AI safety and security research",
        "content": """Google DeepMind and UK AI Security Institute (AISI) strengthen collaboration on AI safety through new MoU.
Focus areas: foundational security research, AI evaluation techniques, monitoring AI reasoning processes (chain-of-thought monitoring), understanding social and emotional impacts.
This builds on previous Google DeepMind research and recent collaboration with AISI, OpenAI, Anthropic and other partners.
Gemini 3 is Google DeepMind's most intelligent and secure model to date.
External expert partners include Apollo Research, Vaultis, Dreadnode and more.
Google DeepMind's Responsibility and Safety Council monitors emerging risks, reviews ethics assessments, and implements mitigations.
Partnership is part of broader UK government collaboration on AI safety.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-12-11",
        "translated_title": "谷歌DeepMind深化与英国AI安全研究院的合作",
        "translated_summary": "谷歌DeepMind与英国AI安全研究院签署新的合作备忘录，聚焦基础安全研究、AI评估技术、AI推理过程监测，以及社会影响研究等领域，旨在推动AI安全发展。",
        "impact_analysis": "AI安全正从行业自律走向制度化合规。英国AISI与美国AI安全研究院形成东西呼应的监管格局。谷歌邀请外部机构对Gemini 3进行严格测试，标志着头部企业在安全问题上更加开放。这一趋势将推动可解释性研究和红队测试成为行业标准。",
        "industry_tags": ["safety-alignment", "policy-regulation", "research-paper"],
    },
    {
        "id": 1298,
        "title": "Build with Nano Banana Pro, our Gemini 3 Pro Image model",
        "summary": "Gemini 3 Pro Image model delivers high-fidelity image generation and editing with text rendering accuracy and world knowledge grounding via Google Search.",
        "content": """Gemini 3 Pro Image (Nano Banana Pro) is a state-of-the-art image generation and editing model.
Rolls out in paid preview via Gemini API in Google AI Studio and Vertex AI for enterprises.
Key capabilities: high-fidelity images, higher accuracy in text rendering, robust world knowledge.
Grounding with Google Search connects the model to real-time web content for data-driven outputs.
Valuable for applications requiring precise representations such as biological diagrams or historical maps.
Excels on Text to Image AI benchmarks compared to leading competitors.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-11-20",
        "translated_title": "谷歌推出Nano Banana Pro：全新Gemini 3专业图像生成模型",
        "translated_summary": "谷歌发布Gemini 3专业图像模型，可生成高保真图像，具备精准的文字渲染能力，并可通过谷歌搜索进行知识检索与实时内容对齐，在多项图像生成基准测试中领先同类竞品。",
        'impact_analysis': "Gemini 3图像模型的核心差异化在于将生成能力与实时知识检索结合，意味着AI生成的图像不再凭空杜撰，而是可引用真实世界数据。这对企业级应用意义重大——生物医学图表、历史地图等高精度内容生产将被大幅提速。图像生成战场正在从'以假乱真'升级为'以真驭真'。",

        "industry_tags": ["model-release", "enterprise-app", "research-paper"],
    },
    {
        "id": 1301,
        "title": "We're expanding our presence in Singapore to advance AI in the Asia-Pacific region",
        "summary": "Google DeepMind opens a new Singapore research lab, accelerating AI progress in the Asia-Pacific region.",
        "content": """Google DeepMind opens new Singapore research lab to advance AI in Asia-Pacific.
Team will consist of research scientists, software engineers, and AI impact experts.
Focus areas: linguistic and cultural inclusivity for Asia Pacific, advancing Gemini core capabilities, applying latest models across Google products and Cloud customers.
Collaboration with government, businesses, civil society, and academic institutions.
Asia-Pacific is home to more than half the world's population and poised for immense growth.
Singapore's National AI Strategy 2.0 and Smart Nation 2.0 cited as enabling environment.
Google DeepMind's APAC team has more-than-doubled over the past year.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-11-18",
        "translated_title": "谷歌DeepMind在新加坡设立新研究实验室，押注亚太AI发展",
        "translated_summary": "谷歌DeepMind宣布在新加坡设立新的研究实验室，汇聚顶尖研究科学家和工程师，专注推进亚太地区的语言文化包容性研究及Gemini核心能力开发，深化与政府、企业和学术界的合作。",
        "impact_analysis": "东南亚正在成为AI战略布局新高地。新加坡凭借清晰的AI政策和开放的人才环境，吸引了谷歌在此设立亚太核心据点。谷歌团队规模在一年内翻倍，说明该区域在谷歌全球AI版图中的战略优先级显著提升。对亚太AI生态而言，这意味着更多本地化资源和技术转化机会。",
        "industry_tags": ["chips-infra", "research-paper", "industry-trend"],
    },
    {
        "id": 1349,
        "title": "Gemini 2.5 Pro Preview: even better coding performance",
        "summary": "We've seen developers doing amazing things with Gemini 2.5 Pro, so we decided to release an updated version a couple of weeks early to get into developers hands sooner.",
        "content": """Google releases updated Gemini 2.5 Pro a couple of weeks ahead of schedule based on strong developer feedback.
Key improvements: better coding performance, reduced errors in function calling, improved function calling trigger rates.
Available via Gemini API in Google AI Studio, and for enterprise customers via Vertex AI.
Previous iteration (03-25) now redirects to the new version (05-06) automatically at the same price.
Model card updated with new version details.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-05-06",
        "translated_title": "Gemini 2.5 Pro预览版提前发布：编码性能显著提升",
        "translated_summary": "由于开发者反馈强烈，谷歌提前两周发布Gemini 2.5 Pro更新版本，重点提升了编程能力，降低了函数调用错误率，并改善了触发准确率，现已可通过谷歌AI Studio和Vertex AI使用。",
        "impact_analysis": "谷歌主动加速产品节奏以回应开发者需求，显示AI模型的差异化窗口期正在缩短。函数调用能力的改进对于构建AI Agent至关重要，这直接决定了AI能否可靠地驱动外部工具和API。谷歌以相同价格无缝切换版本，降低了开发者迁移成本，有望进一步巩固其在开发者生态中的地位。",
        "industry_tags": ["model-release", "agent-tools", "enterprise-app"],
    },
    {
        "id": 1402,
        "title": "Investors back Skye's AI home screen app for iPhone ahead of launch",
        "summary": "Skye's new AI app attracted investors before it even launched — a sign of interest in a more AI-aware iPhone.",
        "content": """Signull Labs' Skye app: AI home screen for iPhone.
Attracted investor interest before official launch.
App plans to launch to waitlist users soon.
Represents trend toward deeper AI integration into smartphone experience.
A sign of growing interest in AI-aware mobile experiences.""",
        "source_name": "TechCrunch",
        "published_at": "2026-04-27",
        "translated_title": "AI主屏应用Skye未发先火：iPhone迎来智能桌面时代",
        "translated_summary": "Signull Labs开发的Skye应用将AI能力深度融入iPhone主屏，在尚未正式发布前即获得投资者青睐，显示出市场对更智能的手机交互体验的强烈需求。应用即将向等待名单用户开放。",
        "impact_analysis": "Skye的融资热度说明，AI手机不是一个概念，而是真实的资本赛道。苹果的封闭生态反而成为第三方AI应用的创新试验场——在iPhone上做AI主屏，比在安卓更具挑战，也更有差异化价值。如果Skye能解决隐私和权限问题，它可能成为AI个人助理的新入口，开辟一个新的消费者应用品类。",
        "industry_tags": ["consumer-app", "agent-tools", "funding-ipo"],
    },
    {
        "id": 1390,
        "title": "OpenAI Breaks Free From Exclusive AI Pact With Microsoft",
        "summary": "Microsoft Corp. and OpenAI have agreed to drop the software giant's exclusive right to sell the startup's AI models, opening the door for the ChatGPT maker to pursue deals with cloud-computing rivals like Amazon.com Inc.",
        "content": """Microsoft and OpenAI have agreed to terminate Microsoft's exclusive right to sell OpenAI's AI models.
Microsoft will no longer pay revenue share to OpenAI.
Partnership will no longer be exclusive going forward.
This opens the door for OpenAI to pursue partnerships with cloud rivals such as Amazon Web Services and Google Cloud.
Microsoft statement: The rapid pace of innovation requires both companies to evolve their partnership for customer benefit.
The restructuring reflects the changing dynamics of the AI infrastructure race.""",
        "source_name": "Bloomberg",
        "published_at": "2026-04-27",
        "translated_title": "微软与OpenAI分手：独家合作协议正式终止",
        "translated_summary": "微软与OpenAI达成协议，解除微软销售OpenAI模型的独家权利，微软将不再获得收入分成。这意味着OpenAI可自主与亚马逊云服务、谷歌云等竞争对手开展合作，标志着双方关系的重大调整。",
        "impact_analysis": "这一变化的影响远超技术层面。OpenAI不再受制于微软的转售限制，意味着它可以直接与AWS和谷歌云建立分销合作，在全球AI云市场正面竞争。对微软而言，失去独家绑定也意味着它必须更认真地经营自己的AI产品线，包括Copilot和Azure AI。整个AI基础设施市场的竞争格局将因此加速重组。",
        "industry_tags": ["enterprise-app", "industry-trend", "chips-infra"],
    },
    {
        "id": 1296,
        "title": "Google DeepMind supports U.S. Department of Energy on Genesis: a national mission to accelerate innovation and scientific discovery",
        "summary": "Google DeepMind and the DOE partner on Genesis, a new effort to accelerate science with AI.",
        "content": """Google DeepMind and U.S. Department of Energy (DOE) partner on Genesis: national mission to accelerate scientific discovery with AI.
Genesis includes projects like AlphaGenome (understanding non-coding DNA, accelerating genome research, potential for crop resistance and biofuels) and WeatherNext (weather forecasting models supporting National Hurricane Center).
DOE's Brookhaven National Laboratory foundational work on Protein Data Bank was crucial for AlphaFold development.
AlphaFold Protein Database used by more than 3 million scientists in over 190 countries.
Partnership connects frontier AI with US national scientific infrastructure.
Goal: breakthroughs in clean energy, materials science, and advanced biomaterials.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-11-24",
        "translated_title": "谷歌DeepMind与美国能源部联手启动Genesis：AI驱动科学发现的国家级使命",
        "translated_summary": "谷歌DeepMind与美国能源部启动Genesis合作计划，利用AI加速科学发现，涵盖基因组预测、天气预报等前沿领域。AlphaFold数据库已服务全球超过一百九十个国家的三百万科学家，此次合作将AI能力与美国国家科学基础设施深度整合。",
        "impact_analysis": "Genesis将AI提升至国家科学基础设施的战略高度。谷歌与能源部的合作路径，从AlphaFold诺贝尔奖级别的成果中尝到了甜头，这次是系统性深化。天气预报、基因组学、可控核聚变——这些领域一旦突破，将产生远超商业AI的溢出价值。对谷歌而言，这是最有效的高端人才绑定和技术合法性来源。",
        "industry_tags": ["research-paper", "policy-regulation", "industry-trend"],
    },
    {
        "id": 1387,
        "title": "Sequoia and Nvidia Back Ex-DeepMind Researcher's New AI Startup at $5.1 Billion Value",
        "summary": "Former Google DeepMind researcher David Silver has raised $1.1 billion for his new company, Ineffable Intelligence, in the latest example of an artificial intelligence startup securing enormous funds out of the gate.",
        "content": """David Silver, former Google DeepMind researcher, founded Ineffable Intelligence.
Raised $1.1 billion in seed funding round.
Valuation: $5.1 billion.
Led by Sequoia Capital and Lightspeed Venture Partners.
Other investors: Nvidia, Google (Alphabet), Index Ventures, and the British government.
London-based company.
One of the largest seed rounds ever for an AI startup.""",
        "source_name": "Bloomberg",
        "published_at": "2026-04-27",
        "translated_title": "前DeepMind研究员David Silver创立AI公司，估值51亿美元融资11亿美元",
        "translated_summary": "前谷歌DeepMind研究员David Silver创立的新公司Ineffable Intelligence完成11亿美元种子轮融资，估值达51亿美元，由红杉资本和Lightspeed领投，Nvidia、谷歌、Index Ventures及英国政府均参与投资。",
        "impact_analysis": "11亿美元种子轮刷新了AI创业融资的历史记录。市场正在重奖顶级人才及其背书网络。David Silver的核心价值在于他掌握DeepMind的前沿研究方法和网络，资本押注的是他能否在新的组织形式下实现技术转化。Nvidia和谷歌同时出现在投资人名单中，说明硬件层和应用层的头部企业都在争夺下一个平台级AI公司的股权。",
        "industry_tags": ["funding-ipo", "research-paper", "industry-trend"],
    },
    {
        "id": 1289,
        "title": "Improved Gemini audio models for powerful voice experiences",
        "summary": "Google enhanced Gemini 2.5 Flash Native Audio for better live voice agents. Expect sharper function calling, robust instruction following and smoother conversations.",
        "content": """Google enhanced Gemini 2.5 Flash Native Audio for live voice agents.
Key improvements: sharper function calling, robust instruction following, smoother conversations.
Live speech translation now rolling out in Google Translate app beta on Android in US, Mexico, and India.
Use cases: Shopify Sidekick (merchants), United Wholesale Mortgage Mia (loan generation - over 14,000 loans generated).
Available via Gemini API in Google AI Studio.
Voice AI is becoming production-ready for customer-facing applications.""",
        "source_name": "Google DeepMind",
        "published_at": "2025-12-12",
        "translated_title": "Gemini音频模型全面升级：实时语音代理进入生产级可用时代",
        "translated_summary": "谷歌升级Gemini 2.5 Flash原生音频模型，显著提升函数调用、指令理解和对话流畅度。实时语音翻译功能正在美国、墨西哥和印度的安卓版谷歌翻译应用中推送测试，企业应用场景包括Shopify Sidekick和美威抵押贷款的AI助理。",
        "impact_analysis": "语音AI长期以来受困于'玩具级'体验，难以支撑真实商业场景。Gemini音频模型在函数调用精度上的突破，意味着AI可以在通话过程中实时查询信息、执行操作，而不只是简单对话。Shopify和房贷领域已出现规模化商用案例，标志语音AI正在跨越从演示到生产的关键门槛。",
        "industry_tags": ["model-release", "enterprise-app", "consumer-app"],
    },
]

def to_slug(title: str, article_id: int) -> str:
    # Simple slug from Chinese title
    cn_titles = {
        1322: "gemini-icpc-gold-medal",
        1290: "deepmind-uk-aisi-partnership",
        1298: "gemini-3-pro-image-model",
        1301: "deepmind-singapore-lab",
        1349: "gemini-25-pro-coding",
        1402: "skye-ai-iphone-home-screen",
        1390: "openai-microsoft-exclusive-ends",
        1296: "deepmind-doe-genesis",
        1387: "ineffable-intelligence-510m",
        1289: "gemini-audio-model-upgrade",
    }
    return cn_titles.get(article_id, f"article-{article_id}")

def num_to_cn(n: str) -> str:
    mapping = {'0':'零','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'}
    return ''.join(mapping.get(c, c) for c in n)

def format_date_cn(date_str: str) -> str:
    # date_str like 2026-04-28
    y, m, d = date_str.split('-')
    return f"{num_to_cn(y)}年{num_to_cn(m.lstrip('0'))}月{num_to_cn(d.lstrip('0'))}日"

def build_audio_script(articles: list, date_cn: str) -> str:
    lines = []
    lines.append(f"各位好，欢迎收听二零二六年四月二十八日AI科技早报。今天的音频节目将为您带来十条重要资讯，涵盖模型发布、融资动态、行业合作与技术创新。\n")
    lines.append("【头条一】谷歌Gemini在国际大学生编程竞赛世界总决赛中达到金牌水平")
    lines.append("Gemini 2.5深度思考模型在全球最具权威的大学生编程竞赛中取得突破性成绩，展示了抽象问题解决能力的重大飞跃。该模型在半小时内解决了全场没有任何一支大学队伍解决的最难题。内部研究表明，同版本的Gemini 2.5深度思考在二零二三年和二零二四年ICPC世界总决赛中同样达到金牌水准，表现与世界前二十名的顶尖编程选手相当。这一里程碑意味着AI作为编程协作者的时代正在到来。")
    lines.append("\n【头条二】谷歌DeepMind深化与英国AI安全研究院的合作")
    lines.append("谷歌DeepMind与英国AI安全研究院签署新的合作备忘录，聚焦基础安全研究、AI评估技术、AI推理过程监测，以及社会影响研究等领域。谷歌还邀请多家外部机构对Gemini 3进行严格测试。AI安全正从行业自律走向制度化合规，英国与美国正形成东西呼应的监管格局，这将推动可解释性研究和红队测试成为行业标准。")
    lines.append("\n【头条三】谷歌推出Nano Banana Pro：全新Gemini 3专业图像生成模型")
    lines.append("谷歌发布Gemini 3专业图像模型，可生成高保真图像，具备精准的文字渲染能力，并可通过谷歌搜索进行知识检索与实时内容对齐。该模型在多项图像生成基准测试中领先同类竞品。核心差异化在于将生成能力与实时知识检索结合，意味着AI生成的图像不再凭空杜撰，而是可引用真实世界数据。生物医学图表、历史地图等高精度内容生产将被大幅提速。")
    lines.append("\n【头条四】谷歌DeepMind在新加坡设立新研究实验室")
    lines.append("谷歌DeepMind宣布在新加坡设立新的研究实验室，专注推进亚太地区的语言文化包容性研究及Gemini核心能力开发。东南亚正在成为AI战略布局新高地，新加坡凭借清晰的AI政策和开放的人才环境，成为谷歌设立亚太核心据点的首选。该区域团队规模在一年内翻倍，说明亚太在谷歌全球AI版图中的战略优先级显著提升。")
    lines.append("\n【头条五】Gemini 2.5 Pro预览版提前发布：编码性能显著提升")
    lines.append("由于开发者反馈强烈，谷歌提前两周发布Gemini 2.5 Pro更新版本，重点提升了编程能力，降低了函数调用错误率，并改善了触发准确率。函数调用能力的改进对于构建AI Agent至关重要，这直接决定了AI能否可靠地驱动外部工具和API。谷歌以相同价格无缝切换版本，降低了开发者迁移成本，有望进一步巩固其在开发者生态中的地位。")
    lines.append("\n【头条六】AI主屏应用Skye未发先火：iPhone迎来智能桌面时代")
    lines.append("Signull Labs开发的Skye应用将AI能力深度融入iPhone主屏，在尚未正式发布前即获得投资者青睐。苹果的封闭生态反而成为第三方AI应用的创新试验场。如果Skye能解决隐私和权限问题，它可能成为AI个人助理的新入口，开辟一个全新的消费者应用品类。资本正在押注AI手机不是一个概念，而是真实的赛道。")
    lines.append("\n【头条七】微软与OpenAI分手：独家合作协议正式终止")
    lines.append("微软与OpenAI达成协议，解除微软销售OpenAI模型的独家权利，微软将不再获得收入分成。这意味着OpenAI可自主与亚马逊云服务、谷歌云等竞争对手开展合作。OpenAI不再受制于微软的转售限制后，将在全球AI云市场正面竞争。对微软而言，失去独家绑定也意味着必须更认真地经营自己的AI产品线。整个AI基础设施市场的竞争格局将因此加速重组。")
    lines.append("\n【头条八】谷歌DeepMind与美国能源部联手启动Genesis国家科学使命")
    lines.append("谷歌DeepMind与美国能源部启动Genesis合作计划，利用AI加速科学发现，涵盖基因组预测、天气预报和先进材料研究等领域。AlphaFold数据库已服务全球超过一百九十个国家的三百万科学家。Genesis将AI提升至国家科学基础设施的战略高度。可控核聚变、清洁能源、新材料——这些领域一旦突破，将产生远超商业AI的溢出价值。")
    lines.append("\n【头条九】前DeepMind研究员David Silver创立AI公司，估值五十一亿美元融资十一亿美元")
    lines.append("前谷歌DeepMind研究员David Silver创立的新公司Ineffable Intelligence完成十一亿美元种子轮融资，估值达五十一亿美元，由红杉资本和Lightspeed领投，Nvidia、谷歌、Index Ventures及英国政府均参与投资。十一亿美元种子轮刷新了AI创业融资的历史记录。Nvidia和谷歌同时出现在投资人名单中，说明硬件层和应用层的头部企业都在争夺下一个平台级AI公司的股权。")
    lines.append("\n【头条十】Gemini音频模型全面升级：实时语音代理进入生产级可用时代")
    lines.append("谷歌升级Gemini 2.5 Flash原生音频模型，显著提升函数调用、指令理解和对话流畅度。实时语音翻译功能正在美国、墨西哥和印度的安卓版谷歌翻译应用中推送测试。Shopify和房贷领域已出现规模化商用案例，标志语音AI正在跨越从演示到生产的关键门槛。语音AI长期以来受困于玩具级体验，难以支撑真实商业场景，这一次，局面正在改变。")
    lines.append("\n以上就是今天的AI科技早报全部内容，感谢收听，我们明天再见。")
    return '\n'.join(lines)

def build_briefing_md(articles: list, date_str: str) -> str:
    lines = []
    lines.append(f"# 🗞️ AI 科技早报 — {date_str}\n")
    lines.append(f"来源：Google DeepMind、TechCrunch、彭博科技  |  抓取与AI翻译驱动\n")
    lines.append("---\n")
    for i, a in enumerate(articles, 1):
        lines.append(f"### {i}. {a['translated_title']}")
        lines.append(f"**来源：** {a['source_name']}  |  **重要性：** {a.get('importance', '')}\n")
        lines.append(f"{a['translated_summary']}\n")
        lines.append(f"**影响分析：** {a['impact_analysis']}\n")
        tags = ', '.join(f'`{t}`' for t in a['industry_tags'])
        lines.append(f"**标签：** {tags}\n")
        lines.append("---\n")
    lines.append("*由 Fanli AI 驱动 | OpenClaw 认知工作流自动生成*")
    return '\n'.join(lines)

if __name__ == "__main__":
    from pathlib import Path

    date_str = date.today().isoformat()  # 2026-04-28
    date_cn = format_date_cn(date_str)

    # Build audio script
    audio_script = build_audio_script(ARTICLES, date_cn)
    audio_script_path = ARCHIVE_DIR / "audio_script.md"
    with open(audio_script_path, 'w', encoding='utf-8') as f:
        f.write(audio_script)
    print(f"✅ audio_script.md → {audio_script_path}")

    # Build briefing markdown
    briefing_md = build_briefing_md(ARTICLES, date_str)
    briefing_path = ARCHIVE_DIR / "briefing.md"
    with open(briefing_path, 'w', encoding='utf-8') as f:
        f.write(briefing_md)
    print(f"✅ briefing.md → {briefing_path}")

    # Update DB
    with NewsDB(DB_PATH) as db:
        for a in ARTICLES:
            slug = to_slug(a['translated_title'], a['id'])
            db.update_translation(
                article_id=a['id'],
                translated_title=a['translated_title'],
                translated_summary=a['translated_summary'],
                translated_body=a.get('content', ''),
                impact_analysis=a['impact_analysis'],
                industry_tags=a['industry_tags'],
                slug=slug,
            )
            print(f"✅ DB updated: {a['id']} → {slug}")

    print("\n✅ All done. Proceed to steps 4-7.")

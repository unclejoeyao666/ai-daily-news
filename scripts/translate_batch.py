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
        "id": 1812,
        "title": "Pentagon inks deals with Nvidia, Microsoft, and AWS to deploy AI on classified networks",
        "summary": "The deals come as the DOD has doubled down on diversifying its exposure to AI vendors in the wake of its controversial dispute with Anthropic over usage terms of its AI models.",
        "content": "The Pentagon has diversified its AI vendor relationships following a dispute with Anthropic. Nvidia, Microsoft, and AWS will provide AI tools for classified networks.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-05-01",
        "translated_title": "五角大楼与Nvidia、微软、AWS签署协议，在机密网络上部署AI",
        "translated_summary": "在美国国防部与Anthropic因AI模型使用条款发生争议后，五角大楼正在多元化其AI供应商合作。Nvidia、微软和AWS将获得在机密网络上部署AI工具的合同。",
        "impact_analysis": "此次合作标志着美国军方在AI部署上的重大转向。Nvidia、微软、AWS三家联手，表明AI基础设施竞争已从商业市场延伸至国家安全领域。Anthropic被排除在外，反映出AI安全与商业利益之间的深层矛盾正在加剧。",
        "industry_tags": ["policy-regulation", "chips-infra", "ai-research"],
    },
    {
        "id": 1815,
        "title": "Pentagon strikes classified AI deals with OpenAI, Google, and Nvidia — but not Anthropic",
        "summary": "The Pentagon has struck deals with OpenAI, Google, Microsoft, Amazon, Nvidia, xAI, and Reflection, allowing the agency to use their AI tools in classified settings.",
        "content": "The Pentagon has signed agreements with multiple AI vendors including OpenAI, Google, Nvidia, Microsoft, Amazon, xAI and Reflection for classified AI deployment.",
        "source_name": "The Verge AI",
        "published_at": "2026-05-01",
        "translated_title": "五角大楼与OpenAI、谷歌、Nvidia签署机密AI协议——Anthropic被排除在外",
        "translated_summary": "五角大楼已与OpenAI、谷歌、微软、亚马逊、Nvidia、xAI及Reflection达成协议，允许该机构在机密环境中使用这些公司的AI工具。",
        "impact_analysis": "Anthropic因拒绝允许将Claude用于国内大规模监控和自主武器而被排除在外，成为本轮AI军事采购的最大输家。头部AI厂商正在通过军事合同争夺战略高地，AI军事化趋势不可逆转。",
        "industry_tags": ["policy-regulation", "ai-research", "chips-infra"],
    },
    {
        "id": 1811,
        "title": "Did you know you can't steal a charity? Don't worry. Elon Musk will remind you.",
        "summary": "Elon Musk spent three days on the witness stand this week in his lawsuit against OpenAI, and it's already getting messy.",
        "content": "Elon Musk testified for three days in his lawsuit against OpenAI, with emails, texts and tweets being used as evidence.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-05-01",
        "translated_title": "你听说过偷慈善机构的故事吗？没关系，马斯克会提醒你的",
        "translated_summary": "埃隆·马斯克本周在针对OpenAI的诉讼中出庭作证三天，邮件、短信和他自己的推文不断被翻出，局面正在变得复杂。",
        "impact_analysis": "这起诉讼的实质是关于AI发展方向的路线之争：开源公益化与商业化封闭之间的冲突。无论判决结果如何，它都将对AI行业的治理模式产生深远影响。",
        "industry_tags": ["ai-research", "policy-regulation", "funding-ipo"],
    },
    {
        "id": 1813,
        "title": "Musk v. Altman is just getting started",
        "summary": "Elon Musk's lawsuit against OpenAI and Sam Altman is in its early stages with significant implications for AI governance.",
        "content": "The Musk v. Altman legal battle represents a fundamental dispute over AI governance and the direction of artificial intelligence development.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-05-01",
        "translated_title": "马斯克诉阿尔特曼案才刚刚开始",
        "translated_summary": "埃隆·马斯克对OpenAI及萨姆·阿尔特曼的诉讼处于早期阶段，此案对AI治理结构具有深远影响。",
        "impact_analysis": "马斯克与阿尔特曼的法律战争不仅是个人恩怨，更关乎AI行业的未来走向。若OpenAI被认定违反公益使命条款，可能引发整个AI行业对组织结构的重新审视。",
        "industry_tags": ["ai-research", "policy-regulation", "funding-ipo"],
    },
    {
        "id": 1617,
        "title": "Is AI video just a prequel? Runway's CEO thinks world models are next",
        "summary": "AI-generated video has gone from novelty to creative tool almost overnight, and Runway sees world models as the next frontier.",
        "content": "Runway's CEO discusses the evolution of AI video generation and positions world models as the next major breakthrough in AI.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-04-30",
        "translated_title": "AI视频只是前传？Runway CEO认为世界模型才是下一步",
        "translated_summary": "AI生成视频已从新鲜事物迅速转变为创意工具，Runway CEO认为世界模型（World Models）是下一个主战场。",
        "impact_analysis": "世界模型代表了AI从感知到认知的关键跨越。若AI能理解物理世界的运行规律并在其中进行模拟推理，将打开自动驾驶、机器人、科学发现等领域的巨大空间。Runway提前布局，有望在下一代视频AI竞争中占据先机。",
        "industry_tags": ["model-release", "consumer-app", "ai-research"],
    },
    {
        "id": 1623,
        "title": "Colby Adcock's Scout AI raises $100M to train its models for war",
        "summary": "Scout AI has raised $100M to train AI agents for military applications, working on systems that help soldiers control autonomous vehicles.",
        "content": "Scout AI's $100M funding round targets military AI agent development for autonomous vehicle fleet control by individual soldiers.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-04-30",
        "translated_title": "Scout AI融资1亿美元训练战争AI模型：我们实地探访了其训练营",
        "translated_summary": "Scout AI已融资1亿美元，用于训练军事应用AI智能体，专注于帮助士兵控制自动驾驶车辆编队的技术。",
        "impact_analysis": "军事AI智能体正在从概念走向实战。Scout AI的1亿美元融资表明，AI战争应用已不是遥远的未来，而是正在发生的现在。无人车辆编队协同作战一旦成熟，将彻底改变地面作战模式。",
        "industry_tags": ["ai-research", "policy-regulation", "funding-ipo"],
    },
    {
        "id": 1513,
        "title": "At his OpenAI trial, Musk relitigates an old friendship",
        "summary": "Musk testified at the OpenAI trial about his past friendship with Altman, a story he's told before in interviews.",
        "content": "Elon Musk recounts his history with Sam Altman during OpenAI testimony, revisiting a narrative previously shared in interviews and biography.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-04-29",
        "translated_title": "马斯克在OpenAI诉讼中重新审视与阿尔特曼的旧日友情",
        "translated_summary": "马斯克在OpenAI诉讼中作证，重提他与阿尔特曼的旧日友谊——这一故事他曾在采访和沃尔特·艾萨克森为其撰写的传记中讲述过。",
        "impact_analysis": "从昔日战友到今日对簿公堂，马斯克与阿尔特曼的决裂折射出AI行业理想与资本之间的深层张力。OpenAI从非营利向商业化的转型，是这起诉讼的核心争议。",
        "industry_tags": ["ai-research", "policy-regulation", "funding-ipo"],
    },
    {
        "id": 1514,
        "title": "Amazon is already offering new OpenAI products on AWS",
        "summary": "A day after OpenAI ended Microsoft's exclusive rights, AWS announced a slate of OpenAI model offerings including a new agent service.",
        "content": "AWS quickly moved to offer OpenAI models after Microsoft's exclusive arrangement ended, launching a new agent service.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-04-29",
        "translated_title": "微软与OpenAI分手次日，AWS即上线OpenAI新产品",
        "translated_summary": "在OpenAI解除微软独家权利的次日，AWS即宣布推出一系列OpenAI模型产品，其中包括新的Agent服务。",
        "impact_analysis": "微软失去OpenAI独家权后，AWS迅速填补空白。OpenAI的云分发渠道正在从独占走向多元，这意味着其AI能力将更广泛地渗透企业市场，同时加剧云服务商的AI产品竞争。",
        "industry_tags": ["model-release", "enterprise-app", "ai-research"],
    },
    {
        "id": 1516,
        "title": "Google expands Pentagon's access to its AI after Anthropic's refusal",
        "summary": "After Anthropic refused to allow the DoD to use Claude for domestic surveillance and autonomous weapons, Google signed a new contract with the department.",
        "content": "Google has expanded its AI contract with the Pentagon after Anthropic declined to provide Claude for domestic surveillance and autonomous weapons applications.",
        "source_name": "TechCrunch AI",
        "published_at": "2026-04-29",
        "translated_title": "Anthropic拒绝后，谷歌扩大与五角大楼的AI合作",
        "translated_summary": "在Anthropic拒绝允许美国国防部将Claude用于国内监控和自主武器后，谷歌与该部门签署了一份新合同。",
        "impact_analysis": "Anthropic因坚守安全原则失去军事合同，谷歌则借此机会扩大政府AI市场份额。这一案例将成为AI安全与商业利益冲突的经典判例，影响后续AI厂商与政府合作的政策制定。",
        "industry_tags": ["policy-regulation", "ai-research", "safety-alignment"],
    },
    {
        "id": 1487,
        "title": "Goldman Staff in Hong Kong Lose Access to Anthropic's Claude",
        "summary": "Goldman Sachs staff in Hong Kong no longer have access to Anthropic's Claude, an AI agent used for writing computer software.",
        "content": "Goldman Sachs employees in Hong Kong have been denied access to Anthropic's Claude AI coding assistant.",
        "source_name": "Bloomberg Technology",
        "published_at": "2026-04-29",
        "translated_title": "高盛香港员工失去Anthropic Claude访问权限",
        "translated_summary": "据知情人士透露，高盛集团香港员工已无法使用Anthropic的Claude AI助手——此前该工具被用于加速编写计算机软件。",
        "impact_analysis": "高盛撤停Claude可能与Anthropic近期与五角大楼的纠纷有关。AI在金融行业的应用正在受到地缘政治和企业合规的双重约束，AI代理的企业采纳路径面临新的不确定性。",
        "industry_tags": ["enterprise-app", "policy-regulation", "ai-research"],
    }
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

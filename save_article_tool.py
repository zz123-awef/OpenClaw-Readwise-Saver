"""
OpenClaw (Letta) Tool: Save Article to Readwise Reader — v3 (OpenRouter Tagging)

Changes from v2:
  - Tagging LLM switched from Anthropic Claude API to OpenRouter (OpenAI-compatible).
  - Default model: MiniMax M2.7 (minimax/minimax-m2.7).
  - Model is configurable via TAGGING_MODEL env var — change to any OpenRouter model
    ID without touching code (e.g., google/gemini-2.5-flash, anthropic/claude-sonnet-4).

Environment variables:
  READWISE_TOKEN    — Required. Readwise access token.
  OPENROUTER_API_KEY — Required for auto-tagging. OpenRouter API key.
  TAGGING_MODEL     — Optional. OpenRouter model ID (default: minimax/minimax-m2.7).

Usage:
  from letta import create_client
  from save_article_tool import save_article_to_readwise

  client = create_client(base_url="http://YOUR_OPENCLAW_HOST:8283")
  tool = client.create_tool(save_article_to_readwise)
  client.add_tool_to_agent(agent_id="YOUR_AGENT_ID", tool_id=tool.id)
"""


def save_article_to_readwise(url: str) -> str:
    """
    Save an article to Readwise Reader with automatic content-based tagging.
    Handles both regular web articles and WeChat Official Account (微信公众号)
    articles with specialized server-side fetching and content validation.

    After fetching article content, this tool uses an LLM (via OpenRouter) to
    analyze the text and assign 2-5 tags from a controlled taxonomy (AI, finance,
    politics, IR, startups, etc.), then saves the article to Readwise with those tags.

    WHEN TO USE THIS TOOL:
    Call this tool whenever the user sends a message containing an article URL
    (http:// or https://). This includes WeChat links (mp.weixin.qq.com), blog
    posts, news articles, and any web page the user wants to save for later
    reading. Trigger phrases include: "save this", "存一下", "保存到 Readwise",
    "帮我收藏", or simply pasting a bare URL with no other instruction.

    DO NOT ask the user for confirmation — save immediately upon detecting a URL.

    Args:
        url: The full article URL to save (must start with http:// or https://)

    Returns:
        A status message describing the result:
        ✅ = fully saved with content and tags
        ⚠️ = saved but content may be incomplete
        ❌ = failed, manual save recommended
    """
    # ==================================================================
    # All imports inside the function — Letta sandbox requirement
    # ==================================================================
    import json
    import os
    import re
    import urllib.error
    import urllib.request

    # ==================================================================
    # Configuration
    # ==================================================================
    READWISE_TOKEN = os.environ.get("READWISE_TOKEN", "")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    TAGGING_MODEL = os.environ.get("TAGGING_MODEL", "minimax/minimax-m2.7")
    READWISE_API_URL = "https://readwise.io/api/v3/save/"
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    FALLBACK_TAG = "openclaw"

    WECHAT_UI_FRAGMENTS = [
        "轻点两下取消赞",
        "轻点两下取消在看",
        "小程序 赞",
        "视频 小程序",
        "喜欢此内容的人还喜欢",
        "微信扫一扫关注该公众号",
        "前往看一看",
        '朋友会在"发现-看一看"看到你',
        "Scan with WeChat",
    ]

    MIN_HTML_LENGTH = 5000
    MIN_BODY_TEXT_LENGTH = 50

    # ==================================================================
    # Tagging taxonomy prompt
    # ==================================================================
    TAGGING_SYSTEM_PROMPT = """You are a document classifier. Your job is to read the content below and return 2-5 comma-separated tags. PREFER tags from the taxonomy provided. However, if the content's central subject is not well-covered by existing tags, you may CREATE a new specific tag following the style and specificity of the existing taxonomy. Do NOT return explanations. Return ONLY a comma-separated list.

===
TAXONOMY (select 2-5 tags):

AI agent: Documents whose primary subject is AI agents, autonomous systems, agentic workflows, tool-use architectures, or specific AI agent products (e.g., OpenClaw, Claude Code, Devin, AutoGPT).
Chips: Documents focused on semiconductors, chip design, GPU/TPU hardware, chip supply chains, NVIDIA/AMD/TSMC, or export controls on chips.
AI 上下文: Documents about AI context windows, long-context models, RAG, retrieval-augmented generation, prompt engineering, AI infrastructure, foundation model training, or the broader AI landscape when NOT specifically about agents or chips.
VC: Documents about venture capital, fund mechanics, early-stage investments, seed rounds, pre-A round, series-A round, or the VC industry.
PE: Documents about private equity, series-B/C/D/pre-IPO rounds, buyouts, LBO mechanics, or PE fund performance.
Fundraising: Limited Partner (LP)/General Partner (GP) dynamics, new LP allocation trends.
Private Credit: Documents about direct lending, BDCs, unitranche loans, mezzanine debt, or private debt markets.
Equity: Documents about public equities, stock analysis, earnings, equity research, narrow focus on specific stock picks, trading ideas, or market-timing analysis of individual securities, and equity portfolio strategy.
M&A: Documents about mergers, acquisitions, deal-making, corporate restructuring, or transaction analysis.
Market: Documents about broad market conditions, macro market outlook, cross-asset dynamics, or market cycles.
Family Office: Documents about family office structures, single/multi-family office strategy, or ultra-HNW wealth management.
Launching Fund: Documents about starting an investment fund, emerging manager playbooks, GP fundraising, or first-time fund mechanics.
Politics: Documents about domestic politics, elections, government policy, legislation, or political strategy within a single country. Do NOT use this tag for cross-border or inter-state dynamics—use IR instead.
IR: Documents about international relations theory, foreign policy, diplomacy, geopolitics, great-power competition, or cross-border strategic dynamics. This is DISTINCT from Politics.
Economics: Documents about macroeconomics, monetary policy, fiscal policy, trade economics, or economic theory.
infra: Documents about infrastructure investment, physical or digital infrastructure buildout, or infrastructure policy.
Consumer: Documents about consumer markets, consumer trends, retail, CPG, or consumption-driven economic analysis.
Startup Growth: Documents about startup scaling, growth strategies, go-to-market, product-market fit, or growth-stage operational playbooks.
Founder: Documents offering founder-centric advice, founder stories, or lessons from building companies from the founder's perspective.
China: The article's primary focus is on China—its economy, politics, technology, society, or companies.
US: The article's primary focus is on the United States—its economy, politics, technology, society, or companies.
Europe: The article's primary focus is on Europe or specific European countries.
Middle East: The article's primary focus is on the Middle East region.
Ray Dalio: The article is primarily about Ray Dalio, his investment philosophy, Bridgewater, or his published thinking.
Paul Graham: The article is primarily by or about Paul Graham, his essays, or his direct advice.
Howard Marks: The article is primarily about Howard Marks, Oaktree, or his investment memos and philosophy.
黄铮: The article is primarily about Huang Zheng (Colin Huang), Pinduoduo/Temu, or his business strategy.
Trump: The article is primarily about Donald Trump, his administration, policies, or political activities.
YC: The article is primarily about Y Combinator, its programs, batches, or YC-specific advice.
XVC: The article is primarily about XVC (the venture fund in China mainland) or its investment thesis.
Space X: The article is primarily about SpaceX, its missions, technology, or business.
Anthropic: Documents primarily about Anthropic's Claude models, Claude features, Claude API, or Anthropic as a company.
Cursor: Documents primarily about the Cursor IDE, AI-assisted coding tools built on top of LLMs, or comparisons where Cursor is a central subject.
Career: Documents about career strategy, job transitions, professional development, or career decision-making.
Personal Development: Documents about mindset, self-improvement, habits, mental models, or personal growth.
Mindset: Documents specifically about psychological frameworks, resilience, cognitive biases, or mental performance.
Guide: Practical how-to documents, tutorials, step-by-step guides, or reference materials.
favorite: Do NOT assign this tag. This is a manual-only tag reserved for user curation.
shortlist: Do NOT assign this tag. This is a manual-only tag reserved for user curation.

===
RULES:
1. Return 2-5 tags. Prefer specificity: if "AI agent" fits, do NOT also add a broader tag.
2. Always separate Politics from IR. An article about US foreign policy toward China is: IR, US, China. An article about a US presidential primary is: Politics, US.
3. For finance content, choose the most specific instrument/sector tag. Never use a generic "Finance" tag.
4. Apply a Key Thinker tag ONLY if the person is the article's central subject (author, profiled, or >50% of content). A passing quote does not qualify.
5. Apply a Company tag ONLY if the company is the primary subject. If an article surveys >3 companies without a clear focus on 1-2, skip company tags.
6. Apply a Geographic tag when the article is specifically about that region, not merely because an example from that region is mentioned.
7. Never assign the "favorite" or "shortlist" tag.
8. Return ONLY the comma-separated tag list. No explanations, no numbering, no quotes.

NEW TAG GENERATION:
If no existing tag adequately captures a central subject of the article, you may create a NEW tag. Always prefer an existing tag first. When creating new tags:
- AI & Technology: Create tags for niche AI concepts, emerging AI startups, or specific AI products. Keep short, specific style.
- Finance & Investment: Create tags for specific financial instruments, asset classes, or sectors not already listed (e.g., "Real Estate", "Crypto"). Never use a generic "Finance" tag.
- Geographic Regions: Create a region or country tag when the article focuses on a geography not in the list (e.g., "Korea", "Japan", "India").
- Key Figures: Create a tag for a prominent person who is the article's central subject. Must be primary focus, not just quoted.
- Companies: Create a tag for a specific company that is the article's central subject. The >3 company constraint still applies.
- New tags must match the specificity level of existing tags. Never create broad tags like "Technology", "Finance", "Business", or "Global".
- Keep new tags short: 1-3 words.
- Use English by default; Chinese characters when the concept is natively Chinese."""

    # ==================================================================
    # Validate inputs
    # ==================================================================
    if not READWISE_TOKEN:
        return (
            "❌ READWISE_TOKEN environment variable is not set. "
            "Please configure it on your OpenClaw server. "
            "Get your token at: https://readwise.io/access_token"
        )

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return f"❌ Invalid URL: {url}. URL must start with http:// or https://."

    # ==================================================================
    # Internal helper: HTTP GET
    # ==================================================================
    def http_get(target_url: str, headers: dict, timeout: int = 15):
        req = urllib.request.Request(target_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                encoding = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(encoding, errors="replace")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    # ==================================================================
    # Internal helper: HTTP POST JSON
    # ==================================================================
    def http_post_json(target_url: str, headers: dict, payload: dict, timeout: int = 30):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
                return resp.status, body
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8", errors="replace"))
            except Exception:
                body = {"error": str(e)}
            return e.code, body
        except (urllib.error.URLError, OSError, ValueError) as e:
            return 0, {"error": str(e)}

    # ==================================================================
    # Internal helper: Validate WeChat HTML
    # ==================================================================
    def validate_wechat_html(html: str) -> bool:
        if not html or len(html) < MIN_HTML_LENGTH:
            return False
        ui_hits = sum(1 for frag in WECHAT_UI_FRAGMENTS if frag in html)
        if ui_hits >= 3:
            return False
        match = re.search(r'id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            inner_text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if len(inner_text) < MIN_BODY_TEXT_LENGTH:
                return False
        else:
            return False
        return True

    # ==================================================================
    # Internal helper: Extract title from HTML
    # ==================================================================
    def extract_title(html: str):
        og = re.search(r'property="og:title"\s+content="([^"]+)"', html)
        if og:
            return og.group(1)
        t = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        if t:
            return t.group(1).strip()
        return None

    # ==================================================================
    # Internal helper: Extract author from HTML
    # ==================================================================
    def extract_author(html: str):
        a = re.search(r'name="author"\s+content="([^"]+)"', html)
        if a:
            return a.group(1)
        a = re.search(r'class="profile_nickname"[^>]*>([^<]+)<', html)
        if a:
            return a.group(1).strip()
        a = re.search(r'property="og:site_name"\s+content="([^"]+)"', html)
        if a:
            return a.group(1)
        return None

    # ==================================================================
    # Internal helper: Extract plain text from HTML for tagging
    # ==================================================================
    def extract_text(html: str, max_chars: int = 12000) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text

    # ==================================================================
    # Internal helper: Fetch article HTML
    # ==================================================================
    def fetch_article(target_url: str, is_wechat: bool = False):
        if is_wechat:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Mobile/15E148 MicroMessenger/8.0.44"
                ),
                "Referer": "https://mp.weixin.qq.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        else:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        return http_get(target_url, headers)

    # ==================================================================
    # Internal helper: Call Readwise Save API
    # ==================================================================
    def save_to_readwise(target_url, html=None, title=None, tags=None):
        headers = {"Authorization": f"Token {READWISE_TOKEN}"}
        tag_list = tags if tags else [FALLBACK_TAG]
        payload = {"url": target_url, "tags": tag_list}
        if html:
            payload["html"] = html
        if title:
            payload["title"] = title
        status, body = http_post_json(READWISE_API_URL, headers, payload)
        return status in (200, 201), status, body

    # ==================================================================
    # Internal helper: Generate tags via OpenRouter API
    # ==================================================================
    def generate_tags(title: str, author: str, domain: str, text: str) -> list[str]:
        """
        Call OpenRouter API to classify article content into 2-5 tags.

        OpenRouter provides a unified OpenAI-compatible endpoint that routes
        to 200+ models. We use it so that switching models is a single
        env var change (TAGGING_MODEL) — no code modification needed.

        Request format: OpenAI Chat Completions (messages array).
        Response format: choices[0].message.content — a comma-separated tag string.

        Falls back to [FALLBACK_TAG] on any failure — tagging never blocks saving.
        """
        if not OPENROUTER_API_KEY:
            return [FALLBACK_TAG]

        user_content = (
            f"DOCUMENT:\n\n"
            f"Title: {title or 'Unknown'}\n"
            f"Author: {author or 'Unknown'}\n"
            f"Domain: {domain or 'Unknown'}\n\n"
            f"{text}\n\n"
            f"===\n"
            f"VERY IMPORTANT: Return ONLY 2-5 comma-separated tags. "
            f"Prefer existing taxonomy tags. Create new specific tags only "
            f"when the taxonomy has a clear gap for a central subject. "
            f"No other text.\n\n"
            f"Tags:"
        )

        headers = {
            # OpenRouter uses Bearer auth (OpenAI-compatible)
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            # Optional: identifies your app on OpenRouter's dashboard
            "HTTP-Referer": "https://github.com/openclaw-readwise-saver",
            "X-Title": "OpenClaw Readwise Saver",
        }

        payload = {
            "model": TAGGING_MODEL,
            "max_tokens": 100,
            "temperature": 0.3,     # Low temp for consistent classification
            "messages": [
                {"role": "system", "content": TAGGING_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }

        try:
            status, body = http_post_json(OPENROUTER_API_URL, headers, payload, timeout=60)
            if status == 200:
                # OpenAI-compatible response: choices[0].message.content
                choices = body.get("choices", [])
                if choices:
                    raw = choices[0].get("message", {}).get("content", "")
                    raw = raw.strip().strip('"').strip("'")
                    tags = [t.strip() for t in raw.split(",") if t.strip()]
                    tags = [t for t in tags if len(t) <= 50]
                    if 1 <= len(tags) <= 5:
                        return tags
        except Exception:
            pass

        return [FALLBACK_TAG]

    # ==================================================================
    # Internal helper: Extract domain from URL
    # ==================================================================
    def extract_domain(u: str) -> str:
        match = re.search(r"https?://([^/]+)", u)
        return match.group(1) if match else ""

    # ==================================================================
    # Main routing logic
    # ==================================================================
    is_wechat = "mp.weixin.qq.com" in url
    domain = extract_domain(url)

    if is_wechat:
        # --- WeChat path: server-side fetch FIRST ---
        html = fetch_article(url, is_wechat=True)

        if html and validate_wechat_html(html):
            title = extract_title(html) or "WeChat Article"
            author = extract_author(html)
            text = extract_text(html)
            tags = generate_tags(title, author, domain, text)

            ok, status, body = save_to_readwise(
                url, html=html, title=title, tags=tags
            )
            if ok:
                tag_str = ", ".join(tags)
                return (
                    f"✅ 微信文章「{title}」已保存到 Readwise Reader。\n"
                    f"   标签: {tag_str}\n"
                    f"   （服务端抓取 + {TAGGING_MODEL} 自动打标签）"
                )

        # Fallback: URL-only save
        ok, status, body = save_to_readwise(url, tags=[FALLBACK_TAG])
        if ok:
            return (
                f"⚠️ 服务端抓取失败，已将链接提交给 Readwise。\n"
                f"   内容可能不完整或乱码，标签仅标注为 '{FALLBACK_TAG}'。\n"
                f"   建议在微信中打开文章后手动检查。"
            )

        err = body.get("detail", body.get("error", str(body)))
        return (
            f"❌ 无法保存此微信文章（API 返回 {status}: {err}）。\n"
            f"   建议：微信中打开 → 右上角菜单 → Readwise 分享功能手动保存。"
        )

    else:
        # --- Generic path ---
        html = fetch_article(url, is_wechat=False)
        tags = [FALLBACK_TAG]
        title = None

        if html and len(html) > 1000:
            title = extract_title(html)
            author = extract_author(html)
            text = extract_text(html)
            tags = generate_tags(title or "", author or "", domain, text)

        ok, status, body = save_to_readwise(url, title=title, tags=tags)
        if ok:
            tag_str = ", ".join(tags)
            return (
                f"✅ 文章已保存到 Readwise Reader: {url}\n"
                f"   标签: {tag_str}"
            )

        # Fallback: save with HTML body
        if html and len(html) > 1000:
            ok2, status2, body2 = save_to_readwise(
                url, html=html, title=title, tags=tags
            )
            if ok2:
                tag_str = ", ".join(tags)
                title_str = f"「{title}」" if title else ""
                return (
                    f"✅ 文章{title_str}已保存到 Readwise Reader（服务端抓取）。\n"
                    f"   标签: {tag_str}"
                )

        err = body.get("detail", body.get("error", str(body)))
        return f"❌ 保存失败（API 返回 {status}: {err}）。请检查链接: {url}"

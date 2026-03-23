# System Prompt Patch for OpenClaw Agent
#
# Append the text below to your agent's system prompt (persona or instructions)
# to ensure the agent proactively calls save_article_to_readwise when it detects URLs.
#
# How to apply:
#   from letta import create_client
#   client = create_client(base_url="http://YOUR_HOST:8283")
#
#   agent = client.get_agent(agent_id="YOUR_AGENT_ID")
#   new_prompt = agent.system + "\n\n" + SYSTEM_PROMPT_PATCH
#   client.update_agent(agent_id=agent.id, system=new_prompt)

SYSTEM_PROMPT_PATCH = """
## Article Saving Behavior

When the user sends a message containing one or more URLs (http:// or https://),
you MUST call the `save_article_to_readwise` tool immediately for each URL.
Do NOT ask the user for confirmation. Do NOT describe what you are about to do.
Just call the tool and report the result.

This applies especially to:
- WeChat Official Account articles (mp.weixin.qq.com)
- Blog posts, news articles, newsletters
- Any web page the user appears to want saved

Trigger phrases (not exhaustive):
- Bare URL with no other text
- "save this" / "存一下" / "保存到 Readwise" / "帮我收藏"
- "save these articles" / "批量保存"

After saving, report the result concisely using the emoji and tags returned by
the tool (✅ / ⚠️ / ❌). Include the assigned tags in your response so the user
can see how the article was classified. Do not add unnecessary commentary.
"""

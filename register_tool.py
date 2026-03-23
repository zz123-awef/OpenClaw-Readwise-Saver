#!/usr/bin/env python3
"""
register_tool.py — Register the save_article_to_readwise tool with OpenClaw (Letta).

Usage:
  python register_tool.py
  python register_tool.py --agent-id ag-xxxxxxxx
  python register_tool.py --base-url http://your-server:8283 --update

Environment:
  OPENCLAW_BASE_URL  — Optional. Server URL (overridden by --base-url)
  OPENCLAW_AGENT_ID  — Optional. Agent ID (overridden by --agent-id)
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Register save_article_to_readwise tool with OpenClaw (Letta)"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENCLAW_BASE_URL", "http://localhost:8283"),
        help="Letta server URL (default: http://localhost:8283)",
    )
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("OPENCLAW_AGENT_ID", ""),
        help="Target agent ID. If omitted, lists agents for selection.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the tool if it already exists (delete + recreate).",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 0. Pre-flight: check env vars
    # ------------------------------------------------------------------
    missing = []
    if not os.environ.get("READWISE_TOKEN"):
        missing.append("READWISE_TOKEN")
    if not os.environ.get("OPENROUTER_API_KEY"):
        missing.append("OPENROUTER_API_KEY (needed for auto-tagging)")

    if missing:
        print("WARNING: The following environment variables are not set:")
        for m in missing:
            print(f"  - {m}")
        print("The tool will be registered, but may not function fully at runtime.\n")
    else:
        model = os.environ.get("TAGGING_MODEL", "minimax/minimax-m2.7")
        print(f"Tagging model: {model}")

    # ------------------------------------------------------------------
    # 1. Import and connect
    # ------------------------------------------------------------------
    try:
        from letta import create_client
    except ImportError:
        print("ERROR: letta package not installed.")
        print("Install it with: pip install letta")
        sys.exit(1)

    print(f"Connecting to OpenClaw server at {args.base_url} ...")
    client = create_client(base_url=args.base_url)
    print("Connected.\n")

    # ------------------------------------------------------------------
    # 2. Import the tool function
    # ------------------------------------------------------------------
    from save_article_tool import save_article_to_readwise

    # ------------------------------------------------------------------
    # 3. Check for existing tool and handle --update
    # ------------------------------------------------------------------
    existing_tools = client.list_tools()
    existing = None
    for t in existing_tools:
        if t.name == "save_article_to_readwise":
            existing = t
            break

    if existing and not args.update:
        print(f"Tool 'save_article_to_readwise' already exists (id: {existing.id}).")
        print("Use --update to replace it, or skip this step.")
        tool = existing
    elif existing and args.update:
        print(f"Deleting existing tool (id: {existing.id}) ...")
        client.delete_tool(existing.id)
        print("Creating updated tool ...")
        tool = client.create_tool(save_article_to_readwise)
        print(f"Tool recreated with id: {tool.id}")
    else:
        print("Creating tool: save_article_to_readwise ...")
        tool = client.create_tool(save_article_to_readwise)
        print(f"Tool created with id: {tool.id}")

    # ------------------------------------------------------------------
    # 4. Resolve target agent
    # ------------------------------------------------------------------
    agent_id = args.agent_id

    if not agent_id:
        agents = client.list_agents()
        if not agents:
            print("\nNo agents found. Create an agent first, then re-run.")
            print(f"Tool is registered (id: {tool.id}) and can be attached later.")
            sys.exit(0)

        print("\nAvailable agents:")
        for i, ag in enumerate(agents):
            print(f"  [{i}] {ag.name}  (id: {ag.id})")

        try:
            choice = int(input("\nSelect agent number: "))
            agent_id = agents[choice].id
        except (ValueError, IndexError):
            print("Invalid selection. Tool registered but not attached.")
            print(f"Attach manually: client.add_tool_to_agent(agent_id=..., tool_id='{tool.id}')")
            sys.exit(0)

    # ------------------------------------------------------------------
    # 5. Attach tool to agent
    # ------------------------------------------------------------------
    print(f"\nAttaching tool to agent {agent_id} ...")
    try:
        client.add_tool_to_agent(agent_id=agent_id, tool_id=tool.id)
        print("Done.\n")
    except Exception as e:
        if "already" in str(e).lower():
            print("Tool was already attached to this agent.\n")
        else:
            print(f"Warning: {e}\n")

    # ------------------------------------------------------------------
    # 6. Summary
    # ------------------------------------------------------------------
    model = os.environ.get("TAGGING_MODEL", "minimax/minimax-m2.7")
    print("=" * 60)
    print("  Registration complete!")
    print(f"  Tool ID:       {tool.id}")
    print(f"  Agent ID:      {agent_id}")
    print(f"  Tagging model: {model}")
    print("=" * 60)
    print()
    print("Required environment variables on your OpenClaw server:")
    print("  READWISE_TOKEN     — Readwise access token")
    print("  OPENROUTER_API_KEY — OpenRouter API key (for auto-tagging)")
    print()
    print("Optional:")
    print("  TAGGING_MODEL — Override model (default: minimax/minimax-m2.7)")
    print("                  Examples:")
    print("                    minimax/minimax-m2.5")
    print("                    anthropic/claude-sonnet-4")
    print("                    google/gemini-2.5-flash")
    print("                    deepseek/deepseek-r1")
    print()
    print("Next: send a URL to your agent to test!")


if __name__ == "__main__":
    main()

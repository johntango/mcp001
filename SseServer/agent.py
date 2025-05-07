#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import json5
import os
import sys
from pathlib import Path
from typing import List

from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings

# Paths to your config and runtime files
MCP_CONFIG = Path("/workspaces/mcp001/SseServer/.vscode/mcp.json")
# Path to write runtime server endpoints
MCP_RUNTIME = Path("/workspaces/mcp001/SseServer/.vscode") / "mcp-runtime.json"

async def load_runtime(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"Runtime map not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def load_mcp_config(path: Path) -> dict:
    if not path.exists():
        print(f"Config not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json5.loads(path.read_text())


async def build_and_connect_servers(
    config: dict,
    runtime: dict[str, str]
) -> List[MCPServerSse]:
    """
    For each entry in runtime (name → base_url), verify an SSE endpoint
    exists at base_url + '/sse', then connect via MCPServerSse.
    """
    servers: List[MCPServerSse] = []
    async with aiohttp.ClientSession() as session:
        for name, base in runtime.items():
            if name not in config.get("servers", {}):
                print(f"[!] Skipping unknown server '{name}'", file=sys.stderr)
                continue

            # Build the full SSE URL
            sse_url = f"{base.rstrip('/')}/sse"
            try:
                async with session.get(sse_url, headers={"Accept": "text/event-stream"}) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                    content_type = resp.headers.get("Content-Type", "")
                    if "event-stream" not in content_type:
                        raise RuntimeError(f"Unexpected Content-Type: {content_type}")
            except Exception as e:
                raise RuntimeError(f"SSE check failed for '{name}' at {sse_url}: {e}")

            # Connect the MCP SSE client

            params: MCPServerSseParams = {
                "url": sse_url,
                # bump the per-request wait window from 5s → 60s
                "timeout": 60.0
            }

            srv = MCPServerSse(params=params, name=name)
            await srv.connect()
            tools = await srv.list_tools()
            print(f"[+] Connected '{name}' → tools: {tools}")
            servers.append(srv)

    return servers


async def run_agent(mcp_servers: List[MCPServerSse]) -> None:
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings(max_tokens=1000, temperature=0.7)
    agent = Agent(
        name="SEC Agent",
        model="gpt-4o-mini",
        instructions="Use the available files from RAG Vector Store to answer the questions.",
        mcp_servers=mcp_servers,
        model_settings=model_settings,
    )

    examples = [

        "Get SEC data for Microsoft MSFT.'",
        "Tell me about CrewAI?"
       
    ]
    for msg in examples:
        print(f"\n>> Query: {msg}")
        resp = await Runner.run(starting_agent=agent, input=msg)
        print("→", resp)

    return


async def disconnect_servers(mcp_servers: List[MCPServerSse]) -> None:
    for srv in reversed(mcp_servers):
        try:
            await srv.cleanup()
            print(f"[+] Disconnected '{srv.name}'")
        except Exception as e:
            print(f"[!] Error disconnecting '{srv.name}': {e}", file=sys.stderr)


async def main() -> None:
    if "OPENAI_API_KEY" not in os.environ:
        print("Set OPENAI_API_KEY in env", file=sys.stderr)
        sys.exit(1)

    config  = load_mcp_config(MCP_CONFIG)
    runtime = await load_runtime(MCP_RUNTIME)

    mcp_servers = await build_and_connect_servers(config, runtime)
    trace_id = gen_trace_id()
    with trace(workflow_name="MCP SSE Agent", trace_id=trace_id):
        print(f"Trace URL: https://platform.openai.com/traces/trace?trace_id={trace_id}\n")
        try:
            await run_agent(mcp_servers)
        finally:
            await disconnect_servers(mcp_servers)


if __name__ == "__main__":
    asyncio.run(main())

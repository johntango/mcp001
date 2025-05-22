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
from pydantic import BaseModel


class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

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
    timeout = aiohttp.ClientTimeout(total=600)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for name, base in runtime.items():
            if name not in config.get("servers", {}):
                print(f"[!] Skipping unknown server '{name}'", file=sys.stderr)
                continue

            sse_url = f"{base.rstrip('/')}/sse"
            try:
                async with session.get(sse_url, headers={"Accept": "text/event-stream"}) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                    content_type = resp.headers.get("Content-Type", "")
                    if "event-stream" not in content_type:
                        raise RuntimeError(f"Unexpected Content-Type: {content_type}")
            except asyncio.TimeoutError:
                print(f"[!] Timeout occurred connecting to {sse_url}")
                continue
            except Exception as e:
                print(f"[!] SSE check failed for '{name}' at {sse_url}: {e}", file=sys.stderr)
                continue

            # Connect the MCP SSE client
            params: MCPServerSseParams = {
                "url": sse_url,
                "timeout": 600.0,  # Extended timeout
                "sse_read_timeout": 600.0,  # Extended read timeout
            }

            try:
                # Create and connect the server
                print(f"[+] Connecting '{name}' to {sse_url} …")
                # set the timeout because the default is 5 seconds. 
                srv = MCPServerSse(params=params, name=name, client_session_timeout_seconds= 600.0,)
                await srv.connect()
                tools = await srv.list_tools()
                print(f"[+] Connected '{name}' → tools: {tools}")
                servers.append(srv)
            except Exception as e:
                print(f"[!] Error connecting/listing tools for '{name}': {e}", file=sys.stderr)

    return servers

async def run_agent(mcp_servers: List[MCPServerSse]) -> None:
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings(max_tokens=1000, temperature=0.8, )

    context_summary = "\n".join(memory.search("next step for sub-agent"))

# 2. Decide which agent to call next (deterministic)
    next_agent = determine_next_sub_agent(context_summary, sub_agent_output)

# 3. Call the next sub-agent
    sub_agent_output = run_sub_agent(next_agent, context_summary)

# 4. Store sub-agent response in vector store
    memory.add(sub_agent_output["response_text"])
    sentiment_agent = Agent(
        name="SEC Agent",
        model="gpt-3.5-turbo-16k",
        instructions="Use the analyze_stock_sentiment tool to produce a sentiment between -1 and +1.",
        mcp_servers=mcp_servers,
        model_settings=model_settings,
    )

    data_agent = Agent(
        name="SEC Data Agent",
        model="gpt-3.5-turbo-16k",
        instructions="Use use getSECData tool to get data from SEC.",
        mcp_servers=mcp_servers,
        model_settings=model_settings,
        handoffs=[sentiment_agent],
    )
    examples = [
        "Use SEC data to generate a sentiment for Microsoft MSFT ?",
        "Yes proceed and give as much detail as possible about the sentiment of Microsoft MSFT.",
    ]
    for msg in examples:
        print(f"\n>> Query: {msg}")
        #resp = await Runner.run_sync(starting_agent=agent, input=msg)
        #resp = Runner.run_sync()(agent=agent, input=msg)
        try:
            resp = await Runner.run(starting_agent=data_agent, input=msg)
            print("Sentiment Adjustment: ", resp.final_output)
        except TimeoutError:
            print("Timed out waiting for response")

    return {"sentiment": resp.final_output}


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
        try:
            await run_agent(mcp_servers)
        finally:
            await disconnect_servers(mcp_servers)


if __name__ == "__main__":
    asyncio.run(main())

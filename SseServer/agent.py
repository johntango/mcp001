#!/usr/bin/env python3
import asyncio
import aiohttp
import json, json5, os, sys
from pathlib import Path
from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings
from typing import Any, List
MCP_CONFIG =  Path("/workspaces/mcp001/SseServer/.vscode") / "mcp.json"
MCP_RUNTIME = Path("/workspaces/mcp001/SseServer/.vscode") / "mcp-runtime.json"

async def load_runtime(path):
    if not path.exists():
        print(f"Runtime map not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())

def load_mcp_config(path):
    if not path.exists():
        print(f"Config not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json5.loads(path.read_text())

async def build_and_connect_servers(config, runtime) -> list[MCPServerSse]:
    servers = []
    for name, port in runtime.items():
        # validate that name is in config
        if name not in config["servers"]:
            continue
        
         # 1) Verify that this endpoint is really SSE, not stdio
        url = f"{port}/sse"
        async with aiohttp.ClientSession() as session:
           async with session.get(url, headers={"Accept": "text/event-stream"}) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"SSE check failed for '{name}' at {url}: HTTP {resp.status}")
                content_type = resp.headers.get("Content-Type", "")
                if "event-stream" not in content_type:
                    raise RuntimeError(
                        f"Expected SSE `Content-Type: text/event-stream` for '{name}', got '{content_type}'"
                    )

        
        
        
        url = f"http://localhost:{port}/{name}/sse"
        params: MCPServerSseParams = {"url": url}
        srv = MCPServerSse(params=params, name=name)
        await srv.connect()
        tools = await srv.list_tools()
        print(f"[+] Connected '{name}' → tools: {tools}")
        servers.append(srv)
    return servers

async def run_agent(mcp_servers):
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings(max_tokens=1000, temperature=0.7)
    agent = Agent(
        name="Assistant",
        instructions="Use the available MCP tools to answer the questions.",
        mcp_servers=mcp_servers,
        model_settings=model_settings,
    )

    examples = [
        "Add these numbers: 7 and 22.",
        "Get vector database named MyVectorStore?",
        "What does John like?",
    ]
    for msg in examples:
        print(f"\n>> Query: {msg}")
        resp = await Runner.run(starting_agent=agent, input=msg)
        print("→", resp.final_output)

async def disconnect_servers(mcp_servers: List[MCPServerSse]) -> None:
    # Tear down in reverse order of connect() to unwind nested cancel scopes properly
    for srv in reversed(mcp_servers):
        try:
            await srv.cleanup()
            print(f"[+] Disconnected '{srv.name}'")
        except Exception as e:
            print(f"[!] Error disconnecting '{srv.name}': {e}", file=sys.stderr)

async def main():
    config  = load_mcp_config(MCP_CONFIG)
    runtime = await load_runtime(MCP_RUNTIME)

    mcp_servers = await build_and_connect_servers(config, runtime)
    trace_id = gen_trace_id()
    with trace(workflow_name="MCP SSE Agent", trace_id=trace_id):
        print(f"Trace URL: https://platform.openai.com/traces/trace?trace_id={trace_id}\n")
        try:
            await run_agent(mcp_servers)
        finally:
        # ← This is what calls disconnect_servers:
            await disconnect_servers(mcp_servers)
        


if __name__ == "__main__":
    if "OPENAI_API_KEY" not in os.environ:
        print("Set OPENAI_API_KEY in env", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main())

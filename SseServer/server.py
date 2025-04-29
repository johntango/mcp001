#!/usr/bin/env python3
import asyncio
import json5
import os
import shlex
import signal
import shutil
import subprocess
import sys
import time
from typing import Any, List

from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServer, MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings

#config_path = Path("/workspaces/mcp001/SseServer/.vscode/mcp.json")
MCP_CONFIG_PATH = os.path.join("/workspaces/mcp001/SseServer/.vscode", "mcp.json")
DEFAULT_BASE_PORT = 8000

api_key = os.environ["OPENAI_API_KEY"] 
print(f"Using OpenAI API key: {api_key}")
set_default_openai_key(api_key)

# get Brave-search key
brave_key = os.environ["BRAVE_API_KEY"]
print(f"Using Brave Search API key: {brave_key}")

def load_mcp_config(path: str) -> dict:
    """Load the MCP JSON config from .vscode/mcp.json."""
    with open(path, "r") as f:
        return json5.load(f)


def start_sse_gateways(servers: dict, base_port: int) -> List[tuple[str, int, subprocess.Popen]]:
    """
    For each server entry in `servers`, launch a supergateway subprocess that wraps
    the MCP stdio server as SSE endpoints. Any env-vars declared in mcp.json get pulled
    from os.environ.
    Returns a list of (name, port, process).
    """
    gateways: List[tuple[str, int, subprocess.Popen]] = []
    port = base_port

    for name, cfg in servers.items():
        # 1) Build the stdio command (strip existing --port flags)
        stdio_parts = [cfg["command"]] + cfg.get("args", [])
        stdio_cmd = " ".join(
            shlex.quote(arg) for arg in stdio_parts if not arg.startswith("--port")
        )

        # 2) Prepare environment: copy os.environ, then overlay only the declared keys
        env = os.environ.copy()
        for var_name in cfg.get("env", {}):
            if var_name not in os.environ:
                raise RuntimeError(
                    f"Missing required environment variable '{var_name}' for MCP server '{name}'"
                )
            env[var_name] = os.environ[var_name]

        # 3) Assign next port
        port += 1

        # 4) Build supergateway command
        gateway_cmd = [
            "npx", "-y", "supergateway",
            "--stdio", stdio_cmd,
            "--port", str(port),
            "--baseUrl", f"http://localhost:{port}",
            "--ssePath", f"/{name}/sse",
            "--messagePath", f"/{name}/message",
        ]

        print(f"[+] Launching SSE gateway for '{name}' on port {port}")
        proc = subprocess.Popen(
            gateway_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        gateways.append((name, port, proc))

    return gateways



def build_mcp_servers(gateways: List[tuple[str, int, subprocess.Popen]]) -> List[MCPServer]:
    """
    Given list of (name, port, proc), return one MCPServerSse per gateway.
    """
    mcp_servers: List[MCPServer] = []
    for name, port, _ in gateways:
        # Build the SSE endpoint URL
        sse_url = f"http://localhost:{port}/{name}/sse"

        # Construct the MCPServerSseParams dict
        params: MCPServerSseParams = {
            "url": sse_url,
            # you can also set "headers", "timeout", "sse_read_timeout" here if needed
        }

        # Instantiate the SSE‐backed MCP server
        mcp = MCPServerSse(
            params=params,
            name=name,
        )

        print(f"[+] Connected to MCP server '{name}' at {sse_url}")
        mcp_servers.append(mcp)
       

    return mcp_servers


def shutdown_gateways(gateways: List[tuple[str, int, subprocess.Popen]]) -> None:
    """Terminate all gateway subprocesses cleanly."""
    for name, port, proc in gateways:
        print(f"[–] Shutting down gateway '{name}' (pid={proc.pid})")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def run_agent(mcp_servers: List[MCPServer]) -> None:
    """
    Instantiate an Agent with the given MCP servers and run a few example messages.
    """
  


    model_settings = ModelSettings(
        max_tokens=1000,
        temperature=0.7,
    )
    agent = Agent(
        name="Assistant",
        instructions="Use the available MCP tools to answer the questions.",
        mcp_servers=mcp_servers,
        model_settings=model_settings
    )

    examples = [
        "Add these numbers: 7 and 22.",
        "latest News for NFL draft",
        "John likes ice cream. ",
    ]

    for message in examples:
        print(f"\n>> Running: {message}")
        result = await Runner.run(starting_agent=agent, input=message)
        print(result.final_output)

async def connect_servers(mcp_servers: List[MCPServer]) -> None:
    """
    Connect to all MCP servers and print available tools.
    """
    for mcp in mcp_servers:
        await mcp.connect()
        tools = await mcp.list_tools()
        print(f"[+] Available tools in '{mcp.name}': {tools}")

async def disconnect_servers(mcp_servers: List[MCPServer]) -> None:
    # Tear down in reverse order of connect() to unwind nested cancel scopes properly
    for srv in reversed(mcp_servers):
        try:
            await srv.disconnect()
            print(f"[+] Disconnected '{srv.name}'")
        except Exception as e:
            print(f"[!] Error disconnecting '{srv.name}': {e}", file=sys.stderr)

async def main(gateways: List[tuple[str, int, subprocess.Popen]]) -> None:
    trace_id = gen_trace_id()
    with trace(workflow_name="MCP SSE Agent Example", trace_id=trace_id):
        print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}\n")
        mcp_servers = build_mcp_servers(gateways)
        await connect_servers(mcp_servers)
        try:
            await run_agent(mcp_servers)
        finally:
        # ← This is what calls disconnect_servers:
            await disconnect_servers(mcp_servers)
        


if __name__ == "__main__":
    if not shutil.which("npx"):
        print("Error: 'npx' not found. Install Node.js/npm.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(MCP_CONFIG_PATH):
        print(f"Error: MCP config not found at {MCP_CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    cfg = load_mcp_config(MCP_CONFIG_PATH)
    servers = cfg.get("servers", {})
    if not servers:
        print("Error: No servers defined in MCP config.", file=sys.stderr)
        sys.exit(1)

    # start supergateway subprocesses
    gateways = start_sse_gateways(servers, DEFAULT_BASE_PORT)
    time.sleep(3)  # allow them to spin up

    try:
        asyncio.run(main(gateways))
    finally:
        # after all disconnects are complete, terminate OS processes
        for name, _, proc in gateways:
            print(f"[–] Terminating gateway '{name}' (pid={proc.pid})")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

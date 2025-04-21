import asyncio
import json
import os
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Callable
import httpx
from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServer
from agents.model_settings import ModelSettings

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

# Resolve config file relative to this script
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "../.vscode" / "mcp.json"

# Global registries and client
FUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {}
SLAVE_HANDLES: Dict[str, subprocess.Popen] = {}
AGENT: Agent = None
client = httpx.AsyncClient()


def infer_port(name: str) -> int:
    if name == "brave-search":
        return 3030
    # Default ports: 8001, 8002, … based on registration order
    return 8000 + list(SLAVE_HANDLES.keys()).index(name) + 1


async def launch_slave_servers():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_FILE}")

    config = json.loads(CONFIG_FILE.read_text())
    servers = config.get("servers", {})

    for name, spec in servers.items():
        env = os.environ.copy()
        env.update(spec.get("env", {}))
        cmd = [spec["command"]] + spec.get("args", [])
        print(f"Launching slave server '{name}': {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, env=env)
        SLAVE_HANDLES[name] = proc


async def load_functions():
    for name, proc in SLAVE_HANDLES.items():
        port = infer_port(name)
        base_url = f"http://localhost:{port}"
        try:
            resp = await client.get(f"{base_url}/functions")
            resp.raise_for_status()
            funcs = resp.json()
            for fn in funcs:
                qualified = f"{name}.{fn['name']}"
                FUNCTION_REGISTRY[qualified] = {
                    "server": base_url,
                    "function": fn
                }
        except Exception as e:
            print(f"Error loading from {base_url}: {e}")


async def call_function_internal(name: str, args: Dict[str, Any]) -> Any:
    entry = FUNCTION_REGISTRY.get(name)
    if not entry:
        raise ValueError(f"Function '{name}' not registered")

    payload = {"name": entry['function']['name'], "arguments": args}
    resp = await client.post(f"{entry['server']}/call", json=payload)
    resp.raise_for_status()
    return resp.json()


async def create_agent():
    global AGENT
    tools: List[ToolSpecification] = []

    for name, entry in FUNCTION_REGISTRY.items():
        async def runner(args: Dict[str, Any], _name=name):
            return await call_function_internal(_name, args)
        spec = ToolSpecification(
            name=name,
            description=entry['function'].get('description', ''),
            parameters=entry['function'].get('parameters', {}),
            function=ToolFunction(call=runner)
        )
        tools.append(spec)

    AGENT = Agent(tools=tools)


async def lifespan(app: FastAPI):
    # Startup sequence
    await launch_slave_servers()
    # Wait briefly for all servers to start
    await asyncio.sleep(2)
    await load_functions()
    await create_agent()
    yield
    # Shutdown sequence: terminate subprocesses and close client
    for proc in SLAVE_HANDLES.values():
        proc.terminate()
    await client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
      <head><title>MCP Master Server</title></head>
      <body>
        <h1>MCP Master Server Dashboard</h1>
        <ul>
          <li><code>/functions</code> – list registered functions</li>
          <li><code>/call</code> – POST to invoke a function</li>
          <li><code>/ask</code> – POST to query the OpenAI Agent</li>
        </ul>
      </body>
    </html>
    """


@app.get("/functions")
async def list_functions():
    return [
        {"name": name,
         "description": entry['function'].get('description', ''),
         "parameters": entry['function'].get('parameters', {})}
        for name, entry in FUNCTION_REGISTRY.items()
    ]


class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]


@app.post("/call")
async def call_function(request: ToolCallRequest):
    result = await call_function_internal(request.name, request.arguments)
    return result


class AskRequest(BaseModel):
    prompt: str


@app.post("/ask")
async def ask_agent(request: AskRequest):
    if AGENT is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    resp = await AGENT.run(prompt=request.prompt)
    return {"response": resp}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)

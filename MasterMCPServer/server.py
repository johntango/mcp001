import asyncio
import json
import os
import subprocess
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any
import httpx

CONFIG_FILE = ".vscode/mcp.json"
FUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {}
SLAVE_HANDLES: Dict[str, subprocess.Popen] = {}
client = httpx.AsyncClient()

def create_master_server() -> FastAPI:
    app = FastAPI()

    async def launch_slave_servers():
        if not os.path.exists(CONFIG_FILE):
            raise FileNotFoundError(f"Missing config file: {CONFIG_FILE}")

        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        servers = config.get("servers", {})
        for name, spec in servers.items():
            env = os.environ.copy()
            env.update(spec.get("env", {}))
            command = [spec["command"]] + spec.get("args", [])
            print(f"Launching slave server: {name} with command: {' '.join(command)}")
            proc = subprocess.Popen(command, env=env)
            SLAVE_HANDLES[name] = proc

    async def load_functions():
        for name in SLAVE_HANDLES:
            base_url = f"http://localhost:{infer_port(name)}"
            try:
                response = await client.get(f"{base_url}/functions")
                response.raise_for_status()
                functions = response.json()

                for func in functions:
                    qualified_name = f"{name}.{func['name']}"
                    FUNCTION_REGISTRY[qualified_name] = {
                        "server": base_url,
                        "function": func
                    }
            except Exception as e:
                print(f"Failed to load functions from {base_url}: {e}")

    def infer_port(name: str) -> int:
        if name == "brave-search":
            return 3030
        return 8000 + list(SLAVE_HANDLES.keys()).index(name) + 1

    @app.on_event("startup")
    async def startup():
        await launch_slave_servers()
        await asyncio.sleep(2)  # Allow some time for servers to be up
        await load_functions()

    @app.get("/")
    async def home():
        html_content = """
        <html>
        <head><title>MCP Master Server</title></head>
        <body>
            <h1>MCP Master Server Dashboard</h1>
            <p>Use the endpoints:</p>
            <ul>
                <li><code>/functions</code> - List all available functions</li>
                <li><code>/call</code> - Call a function via POST</li>
            </ul>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    @app.get("/functions")
    async def list_functions():
        return [
            {
                "name": name,
                "description": entry["function"].get("description", ""),
                "parameters": entry["function"].get("parameters", {})
            }
            for name, entry in FUNCTION_REGISTRY.items()
        ]

    class ToolCallRequest(BaseModel):
        name: str
        arguments: Dict[str, Any]

    @app.post("/call")
    async def call_function(request: ToolCallRequest):
        entry = FUNCTION_REGISTRY.get(request.name)
        if not entry:
            raise HTTPException(status_code=404, detail="Function not found")

        try:
            response = await client.post(
                f"{entry['server']}/call",
                json={
                    "name": entry['function']['name'],
                    "arguments": request.arguments
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error calling slave function: {e}")

    return app

app =
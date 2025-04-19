from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from agents import Agent, Runner, function_tool
from agents import set_default_openai_key,gen_trace_id, trace
from pydantic import create_model
from agents.mcp import MCPServer, MCPServerStdio, MCPServerSse
from agents.mcp import MCPServerSseParams 

import os
import json
import asyncio

set_default_openai_key(os.getenv("OPENAI_API_KEY"))
GIT_PERSONAL_KEY = os.getenv("GIT_PERSONAL_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

# Initialize FastAPI app
app = FastAPI()

# Mount static files and templates
templates = Jinja2Templates(directory="templates")

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@function_tool
def get_weather(city: str):
    return f"The weather in {city} is sunny."


async def get_mcp_servers():
    # Load the MCP server configurations from the .vscode/mcp.json file
    # Use an absolute path to ensure the file is found
    # Example configuration: if not provided in file .vscode/mcp.json
    mcp_config = {
        "servers": {
            "memory": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-memory",
                    "--persist",
                    "--file",
                    "memory.json"
                ]
            },
            "brave-search": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-brave-search",
                ],
                "env": {
                    "BRAVE_API_KEY": BRAVE_API_KEY
                }
            },
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/workspaces"
            ]
        },
        "github": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-github"
            ],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": GIT_PERSONAL_KEY
            }
        }
    }
 }


    mcp_config_path = os.path.join(os.path.dirname(__file__), "../.vscode", "mcp.json")
    if not os.path.exists(mcp_config_path):
        print(f"Configuration file not found at {mcp_config_path}")
        return []
    
    #with open(mcp_config_path, "r") as file:
    #    mcp_config = json.load(file)
    if not mcp_config:
        print("Configuration file is empty.")
        return []
    
    print(f"Loaded MCP configuration:")
    servers = mcp_config.get("servers", {})
    if not servers:
        print("No MCP servers found in configuration.")
        return []

    print(f"Found {len(servers)} MCP servers in configuration.")

    server_handles = []  # List to store MCP server handles
    task_server_map = {}  # Dictionary to map tasks to MCP servers
   
    async def start_server(server_name, server_config, n):
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        print(f"Starting MCP server: {server_name}")
        if n == 1:
            url = "http://localhost:7070/sse"
        else:
            url = "http://lcoalhost:7071/sse"

        try:
            mcp_server = MCPServerSse(
                params=MCPServerSseParams(
                url=url,  # sse URL
                ),
            )
            print(f"started Sse on url: {url}")
            """
            mcp_server = MCPServerStdio(
                name=server_name,
                params={
                    "command": command,
                    "args": args,
                    "env": env,
                    "cache_tool_list": True
                }
            )
            """
            await mcp_server.connect()  # Ensure the server is connected
            print(f"Connected to MCP server: {server_name}")
            tools = await mcp_server.list_tools()
            print(f"Tools available in {server_name}: {tools}")
            print(f"MCP server {server_name} started.")
            return mcp_server
        except Exception as e:
            print(f"Failed to connect to MCP server {server_name}: {e}")
            return None

    tasks = []
    n = 0
    for server_name, server_config in servers.items():
        task = asyncio.create_task(start_server(server_name, server_config, n))
        n = n + 1
        tasks.append(task)
       

    results = await asyncio.gather(*tasks)

    for task, mcp_server in zip(tasks, results):
        if mcp_server:
            server_handles.append(mcp_server)
            task_server_map[id(task)] = mcp_server  # Map the task to the server

    print(f"Started {len(server_handles)} MCP servers.")
    print("Task to Server Map:")
    for task_id, server in task_server_map.items():
        print(f"Task ID: {task_id}, Server Name: {server.name}")

    return server_handles, task_server_map


async def run_agent_with_servers(mcp_servers, prompt_text: str):
    print (f"Running agent with prompt: {prompt_text}")

    # Set the OpenAI API key
    # Initialize OpenAI Agent
    agent = Agent(
        name="Private Agent",
        instructions="You are a helpful agent that answers {prompt_text}.",
        mcp_servers=mcp_servers,
        tools=[get_weather]
        
    )
    
    result = await Runner.run(
        agent,
        input=prompt_text
    )

    # Return the final output from the agent
    print(f"Final output: {result.final_output}")
    return result  # Ensure result is an array of strings



@app.on_event("startup")
async def startup_event():
    # Start tracing on application startup
    #trace.start()
    print("Starting application...")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop tracing on application shutdown
    #trace.stop()
    print("Shutting down application...")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/send-prompt")
async def send_prompt(request: Request):
    try:
        data = await request.json()
        prompt_text = data.get("prompt")
        print(f"Received prompt: {prompt_text}")

        set_default_openai_key(os.getenv("OPENAI_API_KEY"))

        servers, task_server_map = await get_mcp_servers()
        print(f"Started MCP servers: {servers}")
        result = await run_agent_with_servers(servers, prompt_text)

        # Shut down MCP servers one by one
        for task_id, server in task_server_map.items():
            try:
                print(f"Shutting down MCP server {server.name} in task {task_id}")
                await server.cleanup()
                print(f"Successfully shut down MCP server {server.name}")
            except Exception as cleanup_error:
                print(f"Error during cleanup of MCP server {server.name}: {cleanup_error}")
        print(f"All MCP servers have been shut down.")

        # Validate and return the final output
        if not result or not hasattr(result, 'final_output'):
            print("No valid response from the agent.")
            return JSONResponse(content={"error": "No valid response from the agent."}, status_code=500)

        print(f"Final output: {result.final_output}")
        return JSONResponse(content={"response": result.final_output}, status_code=200)

    except Exception as e:
        print(f"Unhandled error: {e}")
        return JSONResponse(content={"error": "Internal Server Error", "details": str(e)}, status_code=500)




if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
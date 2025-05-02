# Multi‑MCP SSE Gateway Manager (SseServer)

## Overview

**This repository provides a framework for standing up multiple Model Context Protocol (MCP) SSE servers**—each hosting its own set of tools—automatically via a single gateway runner. The global URLs are written to `mcp-runtime.json`, which can be provided to “apps” or “Agents” on other machines. Those clients can then access the servers and invoke tools without worrying about transport or process wiring.

---

## mcp-runtime.json

| Service        | SSE Endpoint                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **lookup**         | `https://ominous-space-chainsaw-7p9qvpvw76jfp9p7-8000.app.github.dev`                                                 |
| **brave-search**   | `https://ominous-space-chainsaw-7p9qvpvw76jfp9p7-8001.app.github.dev`                                                 |
| **memory**         | `https://ominous-space-chainsaw-7p9qvpvw76jfp9p7-8002.app.github.dev`                                                 |

For Testing 

| Service        | SSE Endpoint                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **lookup**         | `https://localhost:8000/sse`                                                 |
| **brave-search**   | `https://localhost:8001/sse`                                                 |
| **memory**         | `https://localhost:8002/sse`                                                 |

---

## Capabilities

The endpoints above provide:

- **VectorDB RAG lookup** (`lookup`)  
  A FastMCP server exposing SSE directly to answer queries by retrieving vector store documents via OpenAI’s Vector Stores API.

- **Web Search** (`brave-search`)  
  The `@modelcontextprotocol/server-brave-search` package, run via `npx` (stdio), wrapped by **supergateway** to expose an SSE endpoint.

- **Graph-Based Memory** (`memory`)  
  Another stdio‑based MCP server from `modelcontextprotocol`, wrapped by **supergateway** for SSE access.

Agents (see `agent.py`) can read `mcp-runtime.json`, connect to each URL, list available tools, and execute workflows combining lookup, web‑search, and memory operations seamlessly.


## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Configuration](#configuration)
4. [FastMCP Server: Basic Test](#fastmcp-server-basic-test)
5. [Gateway Runner (`gateway_runner.py`)](#gateway-runner-gateway_runnerpy)
6. [Testing with `client.py`](#testing-with-clientpy)
7. [Running an Agent (`agent.py`)](#running-an-agent-agentpy)
8. [MCP Transport Modes](#mcp-transport-modes)
9. [Security](#security)
10. [Sample `.vscode/mcp.json`](#sample-vscodemcpjson)
11. [Extending with FastMCP](#extending-with-fastmcp)

---

## Overview

- **Goal**: Launch multiple MCP servers on distinct HTTP/SSE endpoints, collect their URLs in a runtime file, and allow OpenAI Agents (via the `openai-agents` SDK) to discover and invoke tools across servers seamlessly.
- **Components**:
  - **MCP Servers**: Individual SSE or stdio processes exposing tool methods.
  - **gateway_runner.py**: Reads `.vscode/mcp.json`, starts each server (wrapping stdio via `supergateway`), and writes `.vscode/mcp-runtime.json`.
  - **client.py**: Example script to hit a single SSE endpoint and list/call tools.
  - **agent.py**: Demonstrates how to load the runtime map, connect to all servers, and run prompts via tools.

---

## Prerequisites

- Python 3.8+
- `npm` (for stdio‐based JavaScript servers)
- An OpenAI API key set in `OPENAI_API_KEY`
- Install dependencies:
  ```bash
  pip install fastmcp openai json5
  npm install -g supergateway
  ```

---

## Configuration

All server definitions live in `.vscode/mcp.json`. Each entry must specify:

- `command`: executable to run (string)
- `args`: list of args passed to the executable
- Optional `type`: set to `"stdio"` if wrapping via `supergateway`; omit or set to `"sse"` for native SSE.
- `env`: object mapping required env‑vars to values or placeholders.

Runtime endpoints are written to `.vscode/mcp-runtime.json` by `gateway_runner.py`.

---

## FastMCP Server: Basic Test

1. Start a single FastMCP server:
   ```bash
   python mcpServer01.py
   ```
2. Note the printed SSE URL (e.g. `http://127.0.0.1:8000/lookup/sse`).
3. In another shell, test with client:
   ```bash
   python client.py --url http://127.0.0.1:8000/lookup/sse
   ```

---

## Gateway Runner (`gateway_runner.py`)

This script:

1. Loads `.vscode/mcp.json`:
   ```json5
   {
     servers: {
       /* ... */
     },
   }
   ```
2. For each server entry:
   - Assigns a unique port (starting at `8000` by default).
   - Resolves `cwd` if provided.
   - Builds the launch command:
     - **stdio** → wraps `command + args` via `supergateway` on HTTP/SSE.
     - **sse** → launches directly with `--port`.
3. Spawns each subprocess and collects `(name, port)` tuples.
4. Writes `.vscode/mcp-runtime.json`:
   ```json
   {
     "lookup": "http://localhost:8001/sse",
     "brave-search": "http://localhost:8002/sse",
     …
   }
   ```

Run it via:

```bash
python gateway_runner.py
```

---

## Testing with `client.py`

You can manually target any server by editing `client.py`’s `--url` argument:

```bash
python client.py --url http://localhost:8002/sse
```

Use it to list tools or invoke them interactively.

---

## Running an Agent (`agent.py`)

1. Ensure `.vscode/mcp-runtime.json` is up to date.
2. Run:
   ```bash
   python agent.py
   ```
3. The agent will:
   - Read server URLs from the runtime file.
   - Connect to each via `MCPServerSse`.
   - List available tools per server.
   - Execute a series of prompts by invoking tools under the hood.

---

## MCP Transport Modes

- **stdio**: Wrapped by `supergateway` → secure, same‐container only.
- **sse (HTTP)**: Native SSE endpoint → more flexible and scalable.

> Most open‐source MCP implementations default to stdio.

---

## Security

By default, MCP exposes a `list_tools` endpoint which can reveal all available functions. To lock down access:

1. **Disable Listing**: In your server code, override or remove the `list_tools` handler so that tools must be called by name without enumeration.

2. **Authenticate Requests**: Place a reverse proxy (e.g. NGINX or Traefik) in front of SSE endpoints and require an API token or OAuth header. Example NGINX snippet:

   ```nginx
   location /lookup/sse {
     proxy_pass http://localhost:8001/sse;
     proxy_set_header Authorization $http_authorization;
     auth_request /auth;
   }
   ```

3. **Per‑Tool Guards**: Inside each tool implementation, validate a request header or shared secret before proceeding:

   ```python
   from fastmcp import FastMCP, Context

   @mcp.tool("secured_tool")
   def secured_tool(params: dict, context: Context):
       token = context.headers.get("Authorization")
       if token != os.environ.get("MCP_API_TOKEN"):
           raise PermissionError("Invalid API token")
       # … tool logic …
   ```

4. **Network Controls**: Limit access to SSE ports via firewall rules or Docker network policies so only trusted clients can connect.

---

## Sample `.vscode/mcp.json`

```json5
{
  servers: {
    lookup: {
      command: "python",
      args: ["mcpServer01.py"],
      env: { OPENAI_API_KEY: "<YOUR_OPENAI_API_KEY>" },
    },
    "brave-search": {
      type: "stdio",
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-brave-search", "--stdio"],
      env: { BRAVE_API_KEY: "" },
    },
  },
}
```

---

## Extending with FastMCP

To author your own SSE server:

1. Use the `FastMCP` class:
   ```python
   from fastmcp import FastMCP
   mcp = FastMCP(name="myservice", host="0.0.0.0", port=9000)
   ```
2. Decorate your tool functions:
   ```python
   @mcp.tool("my_tool", description="Does something useful")
   def my_tool(params: dict): …
   ```
3. Run:
   ```bash
   mcp.run(transport="sse")
   ```

Your new server can then be added to `.vscode/mcp.json` and managed by `gateway_runner.py`.

---

Happy prototyping! 🎉

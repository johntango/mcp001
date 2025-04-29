# The goal is to run multipl mcp sse servers

Below the setup is split into two standalone processes that both read the same .vscode/mcp.json.
gateway_runner.py. Reads .vscode/mcp.json

Spawns one Supergateway‐wrapped SSE server per entry (on ports base_port+1, +2, …)
Writes out a simple .vscode/mcp-runtime.json mapping { "memory": 8001, "brave-search": 8002, … }
Blocks until you hit Ctrl-C, then cleanly tears down all subprocesses

agent_app.py

Reads .vscode/mcp.json (for env-var names) and .vscode/mcp-runtime.json (for the actual ports)
Instantiates MCPServerSse clients pointing at http://localhost:<port>/<name>/sse
Connects, runs your Agent examples, disconnects, and exits

Now we use FastMCP to generate sse servers for particular goals
vectordb_lookup_server.py given a name retrieves from OpenAI the id of the vectordb

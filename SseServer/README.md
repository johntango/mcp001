# The goal is to run multiple mcp sse servers, each on at its own URL
### each mcp server exposes a list of tools that the LLM can call. 
#### The Gateway_runner stands up all the servers defined in the script mcp.json and records their endpoints in mcp-runner.json. 
## Agents are given lists of [tools] or [mcp-servers] or both. The mechanics of the LLM asking the Agent for the tools to be run is hidden from the user by OpenAI's latest openai-agents sdk. 


Start by testing basic server "python mcpServer01.py"  which stands up a FastMCP server
Notice the ports it is using.  Now run "python client.py" to test out that server

The main capability is gateway_runner.py that reads .vsode/mcp.json for servers to create. It writes a file mcp-runner.json that can be read by Agent apps to see available servers. 
You can test this by using client.py and editing the server port number to hit servers one by one. 

Finally you can run agent.py "python agent.py" that takes a list of prompts and executes them by calling available tools.  Start with tools 

Note: MCP Servers can communication on stdio  or  using sse on http ports. 
Stdio is safer but sse is more flexible and scaleable. 
Most modelcontextprotocol open source servers run stdio. If an Agent wants to use these it must be running in the same container. 
I use "supergateway" to expose the stdio server over an http port. eg http://localhost:8001/sse.  

If you write your own FastMCP server then you can use FastMCP library. This can support either stdio or sse servers. 

The mcp.json file follows an mcp standard for defining server behvior. Notice that type : stdio can be used to flag that it needs to be wrapped by supergateway to serve up sse. If there is no type then we assume it is natively sse. (type : sse) IS NOT ALLOWED 

Here is a sample  .vscode/mcp.json
"servers": {
        "lookup": {
            "command": "python",
            "args": [
                "mcpServer01.py"
            ],
            "env": {
                "OPENAI_API_KEY": "<YOUR_OPENAI_API_KEY>"
            }
        },
        "brave-search": {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-brave-search",
                "--stdio"
            ],
            "env": {
                "BRAVE_API_KEY": ""
            }
        },
}

gateway-runner - spawns one Supergateway‐wrapped SSE server per entry (on ports base_port+1, +2, …)
Writes out a simple .vscode/mcp-runtime.json mapping { "memory": 8001, "brave-search": 8002, … }
I have chosen to run all servers on http://localhost:{port}/sse 
You will see some users running on http://localhost:{port}/{name}/sse  
If you prefer this you can easily edit the code. I write mcp-runner.json to show which endpoints sse is at. Thus your Agent apps can just read this file to instantiate "Clients" for the servers (see client.py for example)
You Agent will use the code below to generate a list of "tools" associated with each server. These are the functions that the LLM can call. 

# Connect the MCP SSE client
            params: MCPServerSseParams = {"url": sse_url}
            srv = MCPServerSse(params=params, name=name)
            await srv.connect()
            tools = await srv.list_tools()

agent_app.py

Reads .vscode/mcp.json (for env-var names) and .vscode/mcp-runtime.json (for the actual ports)
Instantiates MCPServerSse clients pointing at http://localhost:<port>/<name>/sse
Connects, runs your Agent examples, disconnects, and exits

Now we use FastMCP to generate sse servers for particular goals
vectordb_lookup_server.py given a name retrieves from OpenAI the id of the vectordb

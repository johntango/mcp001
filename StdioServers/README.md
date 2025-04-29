#DEMO001 mcp_servers CPServerStdio
To run the code you will need KEYS 
then runn 
uvicorn app:app --reload 
This will bring up a browser web page where you can input a prompt. 
This prompt will be handled by an Agent, which has access to 4 mcp Servers. Each mcp Server has multiple functions that can be run. We end up with around 30 or so. The servers are run as tasks and we need to clean up these at the end. 

This code is built to take data in style of .vscode/mcp.json data and spin up multiple mcpStdio type servers.
in app.py you can add more. Notice the "KEYS" are assumed to be in CodeSpaces. However, you can past them in by hand 

Notice that these servers are spun up as NPX (Node type) The @modelcontextprotocol/names have been registered with Node Package Manager and npx is used to install them. 

The idea is we are running well tested code that will serve up specific functionality via the MCP protocol.
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
            }
 }

These are provided to the Agent in the argument mcp_servers: mcp_servers as well as a tool
The agent can decide to run one or more of these.
When this code ends we shut the servers down (we keep track of the tasks in which the servers are running). 

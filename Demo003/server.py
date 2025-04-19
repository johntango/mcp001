import asyncio
import sys
from dotenv import load_dotenv

from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServer
from agents.model_settings import ModelSettings

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
import os

load_dotenv()
set_default_openai_key(os.getenv("OPENAI_API_KEY"))

async def run_agent_chat(server_script_path: str):
    # Validate script path
    is_python = server_script_path.endswith(".py")
    is_js = server_script_path.endswith(".js")
    if not (is_python or is_js):
        raise ValueError("Server script must be a .py or .js file")

    command = "python" if is_python else "node"
    server_params = StdioServerParameters(
        command=command,
        args=[server_script_path],
        env=None
    )

    # Connect to the server
    print("Connecting to server...")
    stdio = await stdio_client(server_params)
    mcp_server = MCPServer(stdio)
    await mcp_server.initialize()
    print("Connected. Available tools:", [tool.name for tool in await mcp_server.list_tools()])

    # Agent configuration
    model_settings = ModelSettings(
        model="gpt-3.5-turbo", 
        max_tokens=1000,
        temperature=0.7,
    )

    agent = Agent(
        model_settings=model_settings,
        tools=mcp_server.tools,
    )

    runner = Runner(agent)

    print("\nMCP Agent Started. Type your query or 'quit' to exit.")

    while True:
        query = input("\nQuery: ").strip()
        if query.lower() == "quit":
            break

        trace_id = gen_trace_id()
        print(f"\n[Trace ID: {trace_id}] Running query...")

        async for update in runner.run(
            input=query,
            tools=mcp_server,
            trace=trace(name="chat.run", id=trace_id)
        ):
            if update.is_text():
                print(update.text, end="", flush=True)
            elif update.is_error():
                print(f"\n[ERROR] {update.error}")
                break

        print("\n")  # newline after response


async def main():
    if len(sys.argv) < 2:
        print("Usage: python agent_runner.py <path_to_server_script>")
        sys.exit(1)

    try:
        await run_agent_chat(sys.argv[1])
    except Exception as e:
        print(f"\nFatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from agents.mcp import MCPServerSse
from agents import Agent, Runner, set_default_openai_key
from agents.model_settings import ModelSettings
import os

set_default_openai_key(os.getenv("OPENAI_API_KEY"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
async def main():
    # Connect to multiple MCP servers
    print("Type:", type(MCPServerSse))
    mcp1 = MCPServerSse("http://localhost:7070/sse")
    mcp2 = MCPServerSse("http://localhost:7071/sse")

    await asyncio.gather(mcp1.initialize(), mcp2.initialize())

    all_tools = mcp1.tools + mcp2.tools
    model_settings = ModelSettings.from_file("model_settings.yaml")
    print(model_settings)
    agent = Agent(
        model_settings=model_settings,
        tools=all_tools,
    )

    runner = Runner(agent)

    while True:
        user_input = input("\nQuery (type 'quit' to exit): ").strip()
        if user_input.lower() == "quit":
            break

        async for update in runner.run(user_input, tools=[mcp1, mcp2]):
            if update.is_text():
                print(update.text, end="", flush=True)
            elif update.is_error():
                print("\nError:", update.error)

if __name__ == "__main__":
    asyncio.run(main())
from fastmcp import Client
import asyncio

async def main():
    # Connection is established here
    sse_url = "https://ominous-space-chainsaw-7p9qvpvw76jfp9p7-8000.app.github.dev/sse"
    client = Client(sse_url)
    async with client:
        print(f"Client connected: {client.is_connected()}")

        # Make MCP calls within the context
        tools = await client.list_tools()
        print(f"Available tools: {tools}")

        if any(tool.name == "hello" for tool in tools):
            result = await client.call_tool("hello", {
            "params": {
                "name": "John"
            }
            })
            print(f"Greet result: {result}")
        if any(tool.name == "lookup_id" for tool in tools):
            result = await client.call_tool("lookup_id", {
                "name": "MyVectorStore"
            })
            print(f"Greet result: {result}")
        if any(tool.name == "queryvectordb" for tool in tools):
            result = await client.call_tool("queryvectordb", {
                "name": "MyVectorStore",
                "messages": "What does John like?"
            })
            print(f"Greet result: {result}")

    # Connection is closed automatically here
 # Connection is closed automatically here
    print(f"Client connected: {client.is_connected()}")

if __name__ == "__main__":
    asyncio.run(main())

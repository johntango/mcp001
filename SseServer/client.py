from fastmcp import Client
import asyncio

async def main():
    # Connection is established here
    sse_url = "http://localhost:9000/sse"
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
            "params": {
                "name": "MyVectorStore"
            }
            })
            print(f"Greet result: {result}")

    # Connection is closed automatically here
 # Connection is closed automatically here
    print(f"Client connected: {client.is_connected()}")

if __name__ == "__main__":
    asyncio.run(main())

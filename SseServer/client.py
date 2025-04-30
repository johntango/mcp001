from fastmcp import Client
import asyncio

async def main():
    # Establish the client context against your lookup endpoint
    async with Client("http://localhost:8000") as client:
        # 1. List available tools
        tools = await client.list_tools()
        print("Available tools:", tools)

        # 2. Invoke the "hello" tool
        result = await client.call_tool("hello", {"name": "John"})
        print("Tool result:", result)

        # 3. Open a streaming SSE connection
        #    Note that client.run must be awaited, and is only valid
        #    once the client object has been created.
        await client.run(transport="sse")

if __name__ == "__main__":
    asyncio.run(main())

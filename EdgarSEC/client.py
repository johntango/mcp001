from fastmcp import Client
import asyncio

async def main():
    # Connection is established here
    sse_url = "http://localhost:8000/sse"
    client = Client(sse_url)
    async with client:
        print(f"Client connected: {client.is_connected()}")

        # Make MCP calls within the context
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        params = {
        "lookups":  ["MSFT"],                  
        "user_agent": "John Williams (jrwtango@gmail.com)",  # per SEC policy
        "recent":     True                                   # only recent filings
    }
        if any(tool.name == "get_submissions" for tool in tools):
            
            result = await client.call_tool("get_submissions", params)
            # turn rsult into string
            
            print(f"Get Submissions: {result}")
        if any(tool.name == "get_company_facts" for tool in tools):
            result = await client.call_tool("get_company_facts", params)
            print(f"Greet result: {result}")

    # Connection is closed automatically here
 # Connection is closed automatically here
    print(f"Client connected: {client.is_connected()}")

if __name__ == "__main__":
    asyncio.run(main())

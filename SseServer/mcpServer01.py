import os
import argparse

from fastmcp import FastMCP, Context
from openai import OpenAI

# Parse command-line arguments for port (and optionally host)
parser = argparse.ArgumentParser(
    description="Start the lookup SSE server with configurable port and host"
)
parser.add_argument(
    "--port", "-p",
    type=int,
    default=8000,
    help="Port to bind the SSE server to (default: 8000)"
)
parser.add_argument(
    "--host", "-H",
    type=str,
    default="127.0.0.1",
    help="Host/interface to bind to (default: 127.0.0.1)"
)
args = parser.parse_args()

name = "lookup"

# Instantiate FastMCP server with dynamic port/host
mcp = FastMCP(
    name=name,
    port=args.port,
    host=args.host
)

# ─── Tool Definitions ─────────────────────────────────────────────────────────────
@mcp.tool("hello", description="Given a person's name return Hello <name>")
def hello(params: dict):
    name_param = params.get("name")
    if not name_param:
        raise ValueError("Parameter 'name' is required")
    return {"hello": f"Hello {name_param}"}


@mcp.tool("lookup_id", description="Given a VectorDB name, return its ID")
def lookup_id(name: str):
    if not name:
        raise ValueError("Parameter 'name' is required")
    stores = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).vector_stores.list()
    for store in stores:
        if store.name == name:
            return {"id": store.id}
    raise ValueError(f"No vector store named '{db_name}' found")


@mcp.tool("queryvectordb", description="Given a query and a vectordb name return the top 2 results")
def queryvectordb(name: str, messages: str):
    if not name:
        raise ValueError("'name' is required")
    if not messages:
        raise ValueError("'messages' is required")

    try:
        # Correct function call
        vector_store_id = "vs_KY8o9PLZUZnmpYz9ybHiXi3l"
        # Call responses.create with keyword args
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
            model="gpt-4o-mini",
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
            }],
            input=messages
        )
        # Proper f‑string and no stray punctuation
        print(f"Response: {response.output_text}")
        return response.output_text

    except Exception as e:
        raise ValueError(f"Error querying vector store '{name}': {e}")

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/{name}/sse"
    print(f"Starting SSE at {url} …")
    mcp.run(transport="sse", host=args.host, port=args.port)
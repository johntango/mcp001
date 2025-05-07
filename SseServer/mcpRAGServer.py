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

name = "RAGLookup"

# Instantiate FastMCP server with dynamic port/host
mcp = FastMCP(
    name=name,
    port=args.port,
    host=args.host
)
vector_store_id_cache: dict[str,str] = {}
# ─── Tool Definitions ─────────────────────────────────────────────────────────────

@mcp.tool("lookup_id", description="Given a VectorDB name, return its ID")
def lookup_id(name: str):
    if not name:
        raise ValueError("Parameter 'name' is required")
    stores = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).vector_stores.list()
    for store in stores:
        if store.name == name:
            vector_store_id_cache = {"id":store.id}
            return {"result": store.id}
    raise ValueError(f"No vector store named '{name}' found")


@mcp.tool("RAGsearch", description="Given RAG VectorDB name and a query return the best answer by using the RAG tool")
def ragsearch_tool(name: str, query: str):
    if not name:
        raise ValueError("'name' is required")
    if not query:
        raise ValueError("'query' is required")

    try:
        # Correct function call
        vector_store_id_cache = {"id":"vs_ftVzUp6jJR6Yv6QpfdG1zCgZ"}
        if vector_store_id_cache == {}:
            vector_store_id_cache = lookup_id(name)
        #vector_store_id = lookup_id(name).get("id")
        # Call responses.create with keyword args
        print(f"Querying vector store '{name}' with ID '{vector_store_id_cache['id']}'")
        tools = [{
                "type": "file_search",
                "vector_store_ids": [vector_store_id_cache["id"]],
                "max_num_results": 1
            }]
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
            model="gpt-4o-mini",
            tools=tools,
            input=query
        )
        # Proper f‑string and no stray punctuation
        print(f"Response: {response.output_text}")
        return {"result": response.output_text}

    except Exception as e:
        raise ValueError(f"Error querying vector store '{name}': {e}")

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/{name}/sse"
    print(f"Starting SSE at {url} …")
    mcp.run(transport="sse", host=args.host, port=args.port)
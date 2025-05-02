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

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/{name}/sse"
    print(f"Starting SSE at {url} …")
    # Run only the SSE transport; path is auto-prefixed by 'name'
    # HTTP namespace is applied when running without transport="sse"
    # Here, SSE runs on raw /sse, but clients should connect at the generated URL
    mcp.run(transport="sse", host=args.host, port=args.port)
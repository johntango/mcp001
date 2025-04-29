#!/usr/bin/env python3
import os
import argparse

from fastmcp import FastMCP, Context
from openai import OpenAI

# ─── MCP Tool Definition ─────────────────────────────────────────────────────────
def register_tools(server: FastMCP):
    @server.tool("lookup_vector_db_id", description="Given a VectorDB name, return its ID")
    def lookup_vector_db_id(params: dict, context: Context):
        db_name = params.get("name")
        if not db_name:
            raise ValueError("Parameter 'name' is required")
        stores = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).beta.vector_stores.list()  # 
        for store in stores:
            if store.name == db_name:
                return {"id": store.id}
        raise ValueError(f"No vector store named '{db_name}' found")

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FastMCP SSE server: lookup OpenAI VectorDB IDs by name"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8005, help="Port to serve SSE on")
    args = parser.parse_args()

    # Create the FastMCP server _with_ host/port settings
    mcp = FastMCP(
        name="vectordb_lookup",
        host=args.host,
        port=args.port
    )

    # Now register our tool onto that instance
    register_tools(mcp)

    # Finally, run _only_ specifying transport
    print(f"Starting vectordb_lookup on {args.host}:{args.port}/sse …")
    mcp.run("sse")  # :contentReference[oaicite:0]{index=0}

#!/usr/bin/env python3
import os
import argparse

from fastmcp import FastMCP, Context
from openai import OpenAI

name = "lookup"
    # Create the FastMCP server _with_ host/port settings
mcp = FastMCP(name=name, port=8000, host="localhost")


@mcp.tool("hello",description="Given a person's name return Hello <name>" )
def hello(params: dict, context: Context):
    name = params.get("name")
    if not name:
        raise ValueError("Parameter 'name' is required")
    return {"hello": f"Hello {name}"}   

@mcp.tool("lookup_id", description="Given a VectorDB name, return its ID")
def lookup_id(params: dict, context: Context):
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
    
    # Finally, run _only_ specifying transport
    print(f"Starting url  {name} /sse …")
    mcp.run("sse")  # :contentReference[oaicite:0]{index=0}

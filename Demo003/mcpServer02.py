from mcp.server.fastmcp import FastMCP
import random

mcp = FastMCP("Fun Tools")

@mcp.tool()
def get_secret_word() -> str:
    return random.choice(["banana", "apple", "kiwi"])

if __name__ == "__main__":
    mcp.run(transport = "sse")
#!/usr/bin/env python3
import json5, json, os, shlex, signal, subprocess, sys, time
from pathlib import Path
from typing import Dict, List, Tuple 
import aiohttp


MCP_CONFIG = Path("/workspaces/mcp001/SseServer/.vscode/mcp.json")
workspace_root = MCP_CONFIG.parent.parent  # → /workspaces/mcp001/SseServer

MCP_RUNTIME = Path("/workspaces/mcp001/SseServer/.vscode") / "mcp-runtime.json"
DEFAULT_BASE_PORT = 8000

def load_mcp_config(path) -> dict:
    with open(path, "r") as f:
        return json5.load(f)


def start_sse_gateways(
    servers: Dict[str, dict],
    base_port: int,
    workspace_root: Path
) -> List[Tuple[str, int, str, subprocess.Popen]]:
    """
    Launch one process per `servers` entry, all from `workspace_root` (unless
    overridden by cfg['cwd']).

    - stdio→SSE servers (cfg['type']=='stdio') are wrapped via supergateway.
    - direct SSE servers (cfg['type']=='sse') are launched directly.

    After launching, writes out runtime metadata (including the correct
    /sse URL) via write_runtime().
    """
    procs: List[Tuple[str, int, str, subprocess.Popen]] = []
    port = base_port

    for name, cfg in servers.items():
        current_port = port
        port += 1

        # determine working directory
        cwd = workspace_root
        if "cwd" in cfg:
            cwd = (workspace_root / cfg["cwd"]).resolve()
        if not cwd.is_dir():
            raise RuntimeError(f"Configured cwd for '{name}' is not a directory: {cwd}")
        print(f"[+] Launching '{name}' from cwd={cwd}")

        # build environment
        env = os.environ.copy()
        for var in cfg.get("env", []):
            if var not in env:
                raise RuntimeError(f"Required env var '{var}' missing for '{name}'")
            env[var] = os.environ[var]

        svc_type = cfg.get("type", "sse")

        # choose launch strategy
        if svc_type == "stdio":
            child_cmd = "npx -y @modelcontextprotocol/server-brave-search --stdio"
            cmd = [
                "npx", "-y", "supergateway",
                "--port", str(port),
                "--baseUrl",      f"http://localhost:{port}",
                "--ssePath",      f"/{name}/sse",
                "--messagePath",  f"/{name}/message",
                "--outputTransport", "sse",
                "--stdio",        child_cmd,
            ]

            print(f"   command to run:  {cmd} ")
            print(f"    → stdio→SSE on port {current_port}")
        else:
            cmd = [
                cfg["command"],
                *cfg.get("args", []),
                "--port", f"{current_port}"
            ]
            print(f"   command to run:  {cmd} ")
            print(f"    → direct SSE on port {current_port}")

        proc = subprocess.Popen(cmd, env=env, cwd=str(cwd))
        procs.append((name, current_port, svc_type, proc))

    # --- write out runtime metadata including the correct SSE URLs ---
    # Build a mapping name→url
    endpoints = {}
    for name, port, svc_type, _ in procs:
        if svc_type == "stdio":
            endpoints[name] = f"http://localhost:{port}/sse"
        else:
            endpoints[name] = f"http://localhost:{port}/sse"

    # your existing function – it will pick up our `endpoints` dict
    write_runtime(procs, MCP_RUNTIME )

    return procs

def write_runtime(procs, path):
    """
    procs: List of tuples (name, port, svc_type, process)
    path:  Path to write the JSON mapping

    For svc_type == "stdio", produce http://localhost:{port}/sse
    Otherwise,          produce http://localhost:{port}/sse
    """
    endpoints = {}
    for name, port, svc_type, _ in procs:
        if svc_type == "stdio":
            endpoints[name] = f"http://localhost:{port}/sse"
        else:
            endpoints[name] = f"http://localhost:{port}/sse"

    with open(path, "w") as f:
        json.dump(endpoints, f, indent=2)

    print(f"[+] Wrote runtime map with SSE URLs to {path}")

def shutdown(procs):
    for name, _, p in procs:
        print(f"[–] Terminating '{name}' (pid={p.pid})")
        p.terminate()
    for _, _, p in procs:
        p.wait(timeout=5)

def main():
    if not MCP_CONFIG.exists():
        print(f"Config not found: {MCP_CONFIG}", file=sys.stderr)
        sys.exit(1)



    cfg = load_mcp_config(MCP_CONFIG)
   

    servers = cfg.get("servers", {})
    if not servers:
        print("No servers defined.", file=sys.stderr)
        sys.exit(1)

    procs = start_sse_gateways(cfg["servers"], DEFAULT_BASE_PORT, workspace_root)
    write_runtime(procs, MCP_RUNTIME)
    print(f"[+] Launched {len(procs)} SSE gateways:")
    
    print("Gateways running. Ctrl-C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown(procs)

if __name__ == "__main__":
    main()

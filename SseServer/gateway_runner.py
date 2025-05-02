#!/usr/bin/env python3
import json5
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Path to the MCP configuration file
MCP_CONFIG = Path("/workspaces/mcp001/SseServer/.vscode/mcp.json")
workspace_root = MCP_CONFIG.parent.parent  # → /workspaces/mcp001/SseServer

# Path to write runtime server endpoints
MCP_RUNTIME = Path("/workspaces/mcp001/SseServer/.vscode") / "mcp-runtime.json"
DEFAULT_BASE_PORT = 8000
CS_NAME = os.environ["CODESPACE_NAME"]         # e.g. 'monalisa-hot-potato-…'


def load_mcp_config(path: Path) -> dict:
    with open(path, "r") as f:
        return json5.load(f)


def start_sse_gateways(
    servers: Dict[str, dict],
    base_port: int,
    workspace_root: Path
) -> List[Tuple[str, int, str, subprocess.Popen]]:
    """
    Launch one process per `servers` entry from `workspace_root`, assigning each a unique port.

    - stdio→SSE servers (cfg['type']=='stdio') are wrapped via supergateway.
    - direct SSE servers (cfg['type']=='sse') are launched directly.

    Returns a list of tuples: (name, port, svc_type, process)
    """
    procs: List[Tuple[str, int, str, subprocess.Popen]] = []
    port = base_port

    for name, cfg in servers.items():
        # Assign a unique port
        current_port = port
        port += 1

        # Determine working directory
        cwd = workspace_root
        if "cwd" in cfg:
            cwd = (workspace_root / cfg["cwd"]).resolve()
        if not cwd.is_dir():
            raise RuntimeError(f"Configured cwd for '{name}' is not a directory: {cwd}")
        print(f"[+] Launching '{name}' from cwd={cwd}")

        # Build environment
        env = os.environ.copy()
        for var in cfg.get("env", {}):
            if var not in env:
                raise RuntimeError(f"Required env var '{var}' missing for '{name}'")

        svc_type = cfg.get("type", "sse")

        # Build command based on service type
        if svc_type == "stdio":
            # Retrieve base command and args from configuration
            base_cmd = cfg.get("command")
            if not base_cmd or not isinstance(base_cmd, str):
                raise RuntimeError(f"Missing or invalid 'command' for stdio server '{name}'")
            args = cfg.get("args", [])
            if not isinstance(args, list):
                raise RuntimeError(f"'args' for stdio server '{name}' must be a list of strings")

            # Combine command and args into a single child command string
            child_cmd_list = [base_cmd, *args]
            child_cmd = " ".join(child_cmd_list)

            # Wrap via supergateway
            cmd = [
                "npx", "-y", "supergateway",
                "--port", str(current_port),
                "--baseUrl", f"http://localhost:{current_port}",
                "--ssePath", f"/sse",
                "--messagePath", f"/message",
                "--outputTransport", "sse",
                "--stdio", child_cmd,
            ]
            print(f"    → stdio→SSE '{name}' on port {current_port} (cmd='{child_cmd}')")
        else:
            # Direct SSE server binds current_port itself
            base_cmd = cfg.get("command")
            if not base_cmd or not isinstance(base_cmd, str):
                raise RuntimeError(f"Missing or invalid 'command' for direct server '{name}'")
            args = cfg.get("args", [])
            if not isinstance(args, list):
                raise RuntimeError(f"'args' for direct server '{name}' must be a list of strings")

            cmd = [base_cmd, *args, "--port", str(current_port)]
            print(f"    → direct SSE '{name}' on port {current_port}")

        print(f"    → COMMAND cmd: {cmd}")
        proc = subprocess.Popen(cmd, env=env, cwd=str(cwd))
        procs.append((name, current_port, svc_type, proc))

    return procs


def write_runtime(procs: List[Tuple[str, int, str, subprocess.Popen]], path: Path) -> None:
    """
    Write a JSON map of service name to base URL (no /sse suffix), so clients can append /sse.

    For stdio services: http://localhost:{port}
    For direct services: http://localhost:{port}
    """
    
    endpoints: Dict[str, str] = {}
    for name, port, svc_type, _ in procs:
        endpoints[name] =  f"https://{CS_NAME}-{port}.app.github.dev"

    with open(path, "w") as f:
        json.dump(endpoints, f, indent=2)

    print(f"[+] Wrote runtime map to {path}")


def shutdown(procs: List[Tuple[str, int, str, subprocess.Popen]]) -> None:
    for name, _, _, p in procs:
        print(f"[–] Terminating '{name}' (pid={p.pid})")
        p.terminate()
    for _, _, _, p in procs:
        p.wait(timeout=5)


def main() -> None:
    if not MCP_CONFIG.exists():
        print(f"Config not found: {MCP_CONFIG}", file=sys.stderr)
        sys.exit(1)

    cfg = load_mcp_config(MCP_CONFIG)
    servers = cfg.get("servers", {})
    if not servers:
        print("No servers defined.", file=sys.stderr)
        sys.exit(1)

    # Launch processes
    procs = start_sse_gateways(servers, DEFAULT_BASE_PORT, workspace_root)

    # Write runtime file
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

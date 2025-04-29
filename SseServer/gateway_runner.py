#!/usr/bin/env python3
import json5, json, os, shlex, signal, subprocess, sys, time
from pathlib import Path
from typing import List, Tuple
import aiohttp

MCP_CONFIG = Path(".vscode") / "mcp.json"
MCP_RUNTIME = Path(".vscode") / "mcp-runtime.json"
DEFAULT_BASE_PORT = 8000

def load_mcp_config(path) -> dict:
    with open(path, "r") as f:
        return json5.load(f)

def start_sse_gateways(servers: dict, base_port: int) -> List[Tuple[str,int,subprocess.Popen]]:
    procs: List[Tuple[str,int,subprocess.Popen]] = []
    port = base_port
    for name, cfg in servers.items():
        # 1) Build stdio cmd (strip --port)
        parts = [cfg["command"]] + cfg.get("args", [])
        stdio = " ".join(shlex.quote(a) for a in parts if not a.startswith("--port"))

        # 2) Env: inherit + only declared keys
        env = os.environ.copy()
        for var in cfg.get("env", {}):
            if var not in os.environ:
                raise RuntimeError(f"Required env '{var}' missing for server '{name}'")
            env[var] = os.environ[var]

        port += 1
        cmd = [
            "npx", "-y", "supergateway",
            "--stdio", stdio,
            "--port", str(port),
            "--baseUrl", f"http://localhost:{port}",
            "--ssePath", f"/{name}/sse",
            "--messagePath", f"/{name}/message",
        ]
        print(f"[+] Launching '{name}' on port {port}")
        p = subprocess.Popen(cmd, env=env)
        procs.append((name, port, p))
    return procs

def write_runtime(procs, path):
    mapping = { name: port for name, port, _ in procs }
    with open(path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"[+] Wrote runtime map to {path}")

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

    procs = start_sse_gateways(servers, DEFAULT_BASE_PORT)
    write_runtime(procs, MCP_RUNTIME)

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

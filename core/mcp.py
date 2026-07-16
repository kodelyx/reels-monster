"""core/mcp.py — MCP / docker service callers, merged from call_flow_mcp.py +
call_gemini_mcp.py + music_generator's generate_music helper.

One place for the JSON-RPC-over-docker-exec pattern that Flow and Gemini both use,
so stages don't each re-implement the "find the JSON line in noisy stdout" parsing.

Endpoints/containers come from core.config (config.env), never hardcoded.
"""
import json
import subprocess


def _find_json_line(stdout: str):
    """MCP servers print startup logs then a JSON-RPC line. Return the parsed JSON obj."""
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    # fallback: whole stdout might be a single JSON blob
    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError:
        return None


def _content_text(result: dict) -> str:
    """Join text parts out of an MCP tool result's content list."""
    parts = result.get("content", [])
    if isinstance(parts, list):
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return str(result)


def call_docker_mcp(cmd: list, tool_name: str, arguments: dict, timeout: int = 300,
                    env: dict = None) -> dict:
    """Run a JSON-RPC tools/call against an MCP server via `docker exec` (cmd).

    Returns the JSON-RPC `result` dict. Raises RuntimeError on any failure.
    """
    request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    run_env = None
    if env:
        import os
        run_env = {**os.environ, **env}
    proc = subprocess.run(cmd, input=json.dumps(request),
                          capture_output=True, text=True, timeout=timeout, env=run_env)
    if proc.returncode != 0:
        raise RuntimeError(f"MCP docker exec failed ({tool_name}): {proc.stderr[-500:]}")
    response = _find_json_line(proc.stdout)
    if response is None:
        raise RuntimeError(f"No JSON response from MCP ({tool_name}).\nRaw:\n{proc.stdout[-800:]}")
    if "error" in response:
        raise RuntimeError(f"MCP tool error ({tool_name}): {response['error']}")
    return response.get("result", {})


# ─── Gemini (chat + generate_music) ───────────────────────────────────────────

def gemini_cmd(config: dict) -> list:
    from core.config import gemini_container, gemini_mcp_path, gemini_mcp_bin
    import os
    # Prefer the native binary (no Docker) when configured and present. It talks
    # to the Gemini HTTP API over localhost:8002 itself, same as the container did.
    native = gemini_mcp_bin(config)
    if native and os.path.exists(native):
        return [native]
    return ["docker", "exec", "-i", gemini_container(config), gemini_mcp_path(config)]


def _gemini_env(config: dict):
    """When running the native binary, point it at the configured HTTP API so the
    MCP and the server never disagree on the port. No-op for docker mode."""
    from core.config import gemini_mcp_bin, gemini_music_url
    import os
    native = gemini_mcp_bin(config)
    if native and os.path.exists(native):
        return {"GEMINI_API_URL": gemini_music_url(config)}
    return None


def gemini_chat(config: dict, prompt: str, timeout: int = 240) -> str:
    result = call_docker_mcp(gemini_cmd(config), "chat", {"prompt": prompt}, timeout,
                             env=_gemini_env(config))
    text = _content_text(result)
    if not text:
        raise RuntimeError("Gemini chat returned no text")
    return text


def gemini_generate_music(config: dict, prompt: str, timeout: int = 300) -> str:
    """Return the raw text response from generate_music (contains the audio URL/path)."""
    result = call_docker_mcp(gemini_cmd(config), "generate_music", {"prompt": prompt}, timeout,
                             env=_gemini_env(config))
    text = _content_text(result)
    if not text:
        raise RuntimeError("generate_music returned empty content")
    return text


# ─── Flow (video generation MCP) ──────────────────────────────────────────────

def flow_cmd() -> list:
    # Flow MCP server container name is fixed in the reel-factory setup.
    return ["docker", "exec", "-i", "flow-agent-server",
            "python3", "-u", "/app/flow_mcp_server.py"]


def flow_call(tool_name: str, arguments: dict, timeout: int = 300) -> dict:
    """Call a Flow MCP tool; return its result dict."""
    return call_docker_mcp(flow_cmd(), tool_name, arguments, timeout)

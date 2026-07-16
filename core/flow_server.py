"""core/flow_server.py — self-contained, on-demand Flow (video/image) API server.

Flow is a Python/FastAPI app (unlike the Go-based Gemini/ChatGPT bridges), so its
"binary" is the source bundle at vendor/flow/ run through **uv** — an isolated,
reproducible environment resolved from pyproject.toml (no global pip pollution, no
Docker, no PyInstaller bloat). See core.config.flow_server_dir.

We boot it *on demand* — only when stage 05 (avatar) or 08 (b-roll) needs it — with
vendor/flow/ as cwd so its config.env, extension cookies (synced over ws://:9227) and
output/ live there. Talks plain HTTP (OpenAI-compatible /v1/videos, /v1/credits).

Public API:
    ensure_server(config)   -> base_url (starts `uv run` if :8001 is down)
    is_up(config)           -> bool  (GET /health)
    warmup(config)          -> (ok, detail)  (boot once, verify extension connected)
"""
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from core.config import flow_api_url, flow_server_dir

# module-level handle so we don't spawn a second server within one process
_PROC = None


def _port(config) -> int:
    return urlsplit(flow_api_url(config)).port or 8001


def is_up(config, timeout: float = 2.0) -> bool:
    """A reachable server answers on /health — that's 'up'."""
    base = flow_api_url(config)
    try:
        urllib.request.urlopen(base + "/health", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # server responded → alive
    except Exception:
        return False


def _launch_cmd(data_dir: Path, port: int) -> list:
    """Prefer `uv run` (isolated env from pyproject). Fall back to plain python3
    if uv isn't installed (then deps must already be importable)."""
    entry = ["cli/api.py", "--host", "127.0.0.1", "--port", str(port)]
    if shutil.which("uv"):
        # uv resolves deps from pyproject.toml into an ephemeral env, Rust-fast.
        return ["uv", "run", "python", *entry]
    return ["python3", *entry]


def ensure_server(config, wait: float = 40.0):
    """Return the server base URL, launching the bundled Flow app if nothing answers.

    Idempotent: reuse a server that's already up (Docker, manual, prior call).
    Otherwise `uv run` vendor/flow/cli/api.py with a project-local cwd. First boot
    may take longer (uv resolves the env once, then caches it), hence wait=40s."""
    global _PROC
    base = flow_api_url(config)
    if is_up(config):
        return base

    data_dir = Path(flow_server_dir(config))
    entry = data_dir / "cli" / "api.py"
    if not entry.exists():
        raise RuntimeError(
            "Flow server is down and no bundled source was found "
            f"(FLOW_SERVER_DIR / vendor/flow/cli/api.py). Base={base}")

    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    port = _port(config)
    env = dict(os.environ)
    env["OPENAI_API_HOST"] = "127.0.0.1"
    env["OPENAI_API_PORT"] = str(port)

    log_path = data_dir / "server.log"
    logf = open(log_path, "ab")
    _PROC = subprocess.Popen(
        _launch_cmd(data_dir, port),
        cwd=str(data_dir), env=env, stdout=logf, stderr=logf,
        start_new_session=True,  # survive parent, don't take our stdin
    )

    deadline = time.time() + wait
    while time.time() < deadline:
        if is_up(config, timeout=1.0):
            return base
        if _PROC.poll() is not None:  # died early
            tail = _read_tail(log_path)
            raise RuntimeError(f"Flow server exited (code {_PROC.returncode}). Log:\n{tail}")
        time.sleep(0.5)
    raise RuntimeError(f"Flow server did not come up within {wait:.0f}s. Log:\n{_read_tail(log_path)}")


def _read_tail(path, n: int = 1200) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except Exception:
        return "(no log)"


def _health(config, timeout: float = 5.0) -> dict:
    base = flow_api_url(config)
    with urllib.request.urlopen(base + "/health", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def warmup(config) -> tuple:
    """Boot the server once at pipeline start and confirm the Chrome extension is
    connected. Flow is used in two stages — avatar (05) and b-roll (08) — so priming
    once here means both reuse the same live server.

    Returns (ok: bool, detail: str). Never raises — a cold Flow shouldn't crash
    preflight; the stages will surface a clear error if it's still down."""
    try:
        ensure_server(config)
    except Exception as e:
        return False, f"server not started: {str(e)[:120]}"
    try:
        h = _health(config)
    except Exception as e:
        return False, f"up but /health failed: {str(e)[:100]}"
    if h.get("extension_connected"):
        return True, f"ready (status={h.get('status')})"
    return False, ("server up but Chrome extension not connected — open Google Flow "
                   "in Chrome with the Flow extension loaded (ws://localhost:9227)")

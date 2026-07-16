"""core/chatgpt_server.py — self-contained, on-demand ChatGPT bridge server.

The ChatGPT HTTP bridge is bundled as a native binary at
vendor/chatgpt/chatgpt-server (a macOS build of kodelyx/chatgpt-free-api — see
core.config.chatgpt_server_bin). This module boots it *on demand* — only when a
stage actually needs ChatGPT — using a project-local working dir that holds
cookies.json (synced by the Chrome extension over ws://localhost:9225), .env and
output/.

No Docker, no OrbStack. Chat is an OpenAI-compatible POST /v1/chat/completions;
stage 06 also uses POST /api/chat/edit for word-level caption timing.

Public API:
    ensure_server(config)          -> base_url (starts the binary if :9225 is down)
    chat(config, prompt)           -> str   (POST /v1/chat/completions)
    warmup(config)                 -> (ok, detail)  (boot once, verify cookies)
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from core.config import chatgpt_url, chatgpt_server_bin, chatgpt_server_dir

# module-level handle so we don't spawn a second server within one process
_PROC = None


def _port(config) -> int:
    return urlsplit(chatgpt_url(config)).port or 9225


def is_up(config, timeout: float = 2.0) -> bool:
    """A reachable server answers on /health — that's 'up'."""
    base = chatgpt_url(config)
    try:
        urllib.request.urlopen(base + "/health", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # server responded → it's alive
    except Exception:
        return False


def ensure_server(config, wait: float = 20.0):
    """Return the server base URL, launching the bundled binary if nothing answers.

    Idempotent: if a server is already up (Docker, manual, or a prior call), we just
    reuse it. Otherwise we spawn vendor/chatgpt/chatgpt-server with a project-local
    cwd (cookies.json + .env + output/ live there)."""
    global _PROC
    base = chatgpt_url(config)
    if is_up(config):
        return base

    binary = chatgpt_server_bin(config)
    if not binary or not Path(binary).exists():
        raise RuntimeError(
            "ChatGPT server is down and no bundled binary was found "
            f"(CHATGPT_SERVER_BIN / vendor/chatgpt/chatgpt-server). Base={base}")

    data_dir = Path(chatgpt_server_dir(config))
    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    port = _port(config)
    env = dict(os.environ)
    # bind loopback on the port our URL expects (bundle .env may say 0.0.0.0)
    env["LISTEN_ADDR"] = f"127.0.0.1:{port}"

    log_path = data_dir / "server.log"
    logf = open(log_path, "ab")
    _PROC = subprocess.Popen(
        [str(Path(binary).resolve())],
        cwd=str(data_dir), env=env, stdout=logf, stderr=logf,
        start_new_session=True,  # survive parent, don't take our stdin
    )

    deadline = time.time() + wait
    while time.time() < deadline:
        if is_up(config, timeout=1.0):
            return base
        if _PROC.poll() is not None:  # died early
            tail = _read_tail(log_path)
            raise RuntimeError(f"ChatGPT server exited (code {_PROC.returncode}). Log:\n{tail}")
        time.sleep(0.5)
    raise RuntimeError(f"ChatGPT server did not come up within {wait:.0f}s. Log:\n{_read_tail(log_path)}")


def _read_tail(path, n: int = 1200) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except Exception:
        return "(no log)"


def _post(config, route: str, payload: dict, timeout: float = 180.0) -> dict:
    base = chatgpt_url(config)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + route, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    obj = json.loads(body)
    if isinstance(obj, dict) and obj.get("error"):
        raise RuntimeError(f"ChatGPT {route} error: {obj['error']}")
    return obj


def chat(config, prompt: str, timeout: float = 180.0) -> str:
    """POST /v1/chat/completions (OpenAI-compatible). Ensures the server is up first."""
    ensure_server(config)
    obj = _post(config, "/v1/chat/completions",
                {"model": config.get("CHATGPT_MODEL", "auto"),
                 "messages": [{"role": "user", "content": prompt}]},
                timeout=timeout)
    return obj["choices"][0]["message"]["content"]


def warmup(config) -> tuple:
    """Boot the server once at pipeline start and confirm cookies are live.

    ChatGPT is used in two places — caption timing (stage 06) and the AI chat
    fallback (Claude → ChatGPT → Gemini). Cookies don't expire for ~15 min, so we
    start the server and prime one session ONCE here; every later call reuses it.

    Returns (ok: bool, detail: str). Never raises — a cold ChatGPT shouldn't block
    the run (Claude/Gemini still cover chat; captions degrade gracefully)."""
    try:
        ensure_server(config)
    except Exception as e:
        return False, f"server not started: {str(e)[:120]}"
    cookies = Path(chatgpt_server_dir(config)) / "cookies.json"
    if not cookies.exists():
        return False, ("server up but cookies.json missing — connect the ChatGPT "
                       "Chrome extension so it syncs cookies to vendor/chatgpt/")
    try:
        reply = chat(config, "ping", timeout=60.0)
        return bool(reply), (f"ready ({reply[:40]!r})" if reply else "no reply")
    except Exception as e:
        return False, f"cookies present but chat failed: {str(e)[:120]}"

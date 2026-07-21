"""core/gemini_server.py — self-contained, on-demand Gemini music server.

The Gemini HTTP server is bundled as a native binary at vendor/gemini/gemini-server
(see core.config.gemini_server_bin). This module boots it *on demand* — only when
stage 09 actually needs music — using a project-local working dir that holds
cookies.json (synced by the Chrome extension over ws://localhost:9226) and output/.

No Docker, no separate free-gemini-api checkout, no MCP. Music is requested with a
plain HTTP POST /music and the server returns a served /output/ URL we download.

Public API:
    ensure_server(config)            -> base_url (starts the binary if :PORT is down)
    generate_music(config, prompt)   -> dict from POST /music  (raises on HTTP error)
    chat(config, prompt)             -> str   (POST /chat, handy for smoke tests)
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from core.config import gemini_music_url, gemini_server_bin, gemini_server_dir

# module-level handle so we don't spawn a second server within one process
_PROC = None


def _port(config) -> int:
    return urlsplit(gemini_music_url(config)).port or 8002


def is_up(config, timeout: float = 2.0) -> bool:
    """A reachable server answers *something* on / (even a 404) — that's 'up'."""
    base = gemini_music_url(config)
    try:
        urllib.request.urlopen(base + "/", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # server responded (e.g. 404 on /) → it's alive
    except Exception:
        return False


def ensure_server(config, wait: float = 20.0):
    """Return the server base URL, launching the bundled binary if nothing answers.

    Idempotent: if a server is already up (started manually, or by a prior call), we
    just reuse it. Otherwise we spawn vendor/gemini/gemini-server with PORT/WS_PORT
    from config and a project-local cwd (cookies.json + output/ live there).
    """
    global _PROC
    base = gemini_music_url(config)
    if is_up(config):
        return base

    binary = gemini_server_bin(config)
    if not binary or not Path(binary).exists():
        raise RuntimeError(
            "Gemini server is down and no bundled binary was found "
            f"(GEMINI_SERVER_BIN / vendor/gemini/gemini-server). Base={base}")

    data_dir = Path(gemini_server_dir(config))
    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    port = _port(config)
    env = dict(os.environ)
    env["PORT"] = str(port)
    env.setdefault("WS_PORT", "9226")  # cookie bridge the Chrome extension pushes to

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
            raise RuntimeError(f"Gemini server exited (code {_PROC.returncode}). Log:\n{tail}")
        time.sleep(0.5)
    raise RuntimeError(f"Gemini server did not come up within {wait:.0f}s. Log:\n{_read_tail(log_path)}")


def _read_tail(path, n: int = 1200) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except Exception:
        return "(no log)"


def _post(config, route: str, payload: dict, timeout: float = 180.0) -> dict:
    base = gemini_music_url(config)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + route, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    obj = json.loads(body)
    if isinstance(obj, dict) and obj.get("error"):
        raise RuntimeError(f"Gemini {route} error: {obj['error']}")
    return obj


def reset_session(config, timeout: float = 15.0) -> bool:
    """POST /reset — start a FRESH Gemini conversation (new c_… id).

    Kept for callers that want an explicit reset. For music we instead pass
    new_chat:true on the /music request itself (one round-trip, same effect).
    Best-effort: returns True on success, False otherwise.
    """
    ensure_server(config)
    try:
        obj = _post(config, "/reset", {}, timeout=timeout)
        return isinstance(obj, dict) and obj.get("status") == "success"
    except Exception:
        return False


def generate_music(config, prompt: str, timeout: float = 180.0) -> dict:
    """POST /music. Ensures the server is up first. Returns the parsed JSON dict,
    which includes music[].local_path (a http://<host>/output/... URL we can fetch).

    Sends new_chat:true so Gemini starts a FRESH conversation for every request.
    Gemini's music_gen tool only fires on the first relevant turn of a chat — reuse
    an old conversation and it replies with chat text ("## Music Prompt Validated …")
    instead of generating audio. Verified: new_chat:true → music_gen fires and a
    track is returned in the same round-trip (no separate /reset needed).
    """
    ensure_server(config)
    return _post(config, "/music", {"prompt": prompt, "new_chat": True}, timeout=timeout)


def chat(config, prompt: str, timeout: float = 90.0) -> str:
    """POST /chat — mainly a smoke test that Gemini + cookies are alive."""
    ensure_server(config)
    obj = _post(config, "/chat", {"prompt": prompt}, timeout=timeout)
    return obj.get("text", "")


def warmup(config) -> tuple:
    """Boot the server once at pipeline start and confirm cookies are live.

    Gemini is used in two places — music (stage 09) and the AI chat fallback
    (Claude → ChatGPT → Gemini). Cookies don't expire for ~15 min, so we start the
    server and prime one session ONCE here; every later call reuses it.

    Returns (ok: bool, detail: str). Never raises — a cold Gemini shouldn't block the
    run (Claude/ChatGPT still cover chat; music falls back to a silent bed).
    """
    try:
        ensure_server(config)
    except Exception as e:
        return False, f"server not started: {str(e)[:120]}"
    cookies = Path(gemini_server_dir(config)) / "cookies.json"
    if not cookies.exists():
        return False, ("server up but cookies.json missing — connect the Gemini "
                       "Chrome extension so it syncs cookies to vendor/gemini/")
    try:
        reply = chat(config, "ping", timeout=45.0)
        return bool(reply), (f"ready ({reply[:40]!r})" if reply else "no reply")
    except Exception as e:
        return False, f"cookies present but chat failed: {str(e)[:120]}"


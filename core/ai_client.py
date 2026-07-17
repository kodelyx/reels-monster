#!/usr/bin/env python3
"""
Shared AI client for reel-factory LLM steps.

Provides ONE entry point, call_ai(), that runs a text/JSON prompt through a
failover chain of backends:

    1. Proxy Claude  (Anthropic SDK, AI_API_KEY — supports 1+ comma-separated keys)
    2. Local ChatGPT (OpenAI-compatible bridge on CHATGPT_SERVER_URL, port 9225)
    3. Local Gemini  (JSON-RPC `chat` tool inside the GEMINI_DOCKER_CONTAINER)

Each backend is tried in order; on any failure (rate-limit, auth, server down)
it moves to the next. Also handles config.env loading, CLI-style proxy headers,
and robust JSON extraction from replies.

Used by: topic_finder.py (Step 0) and pipeline.py (Steps 1-4).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from anthropic import Anthropic

try:
    import requests
except ImportError:
    requests = None


def log(msg):
    print(msg, file=sys.stderr)


def load_env_config(project_dir: Path) -> dict:
    """Read config.env key=value pairs; environment variables override."""
    config = {}
    env_file = Path(project_dir) / ".env"
    if not env_file.exists():
        env_file = Path(project_dir) / "config.env"   # legacy name — back-compat
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    for key in ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL"):
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config


def get_api_keys(config: dict) -> list:
    """AI_API_KEY may hold multiple comma-separated keys (primary, backup, ...)."""
    raw = config.get("AI_API_KEY", "")
    keys = [k.strip() for k in raw.split(",")
            if k.strip() and not k.strip().startswith("<")]
    if not keys:
        raise SystemExit(
            "❌ AI_API_KEY not set. Add it to config.env:\n"
            "   AI_API_KEY=your-key[,backup-key,...]\n"
            "   AI_BASE_URL=https://your-proxy-url  (optional)"
        )
    return keys


def build_client(api_key: str, config: dict) -> Anthropic:
    kwargs = {"api_key": api_key}
    if config.get("AI_BASE_URL"):
        kwargs["base_url"] = config["AI_BASE_URL"]
        # Proxy requires CLI-style headers, see claude-setup.md
        kwargs["default_headers"] = {
            "User-Agent": "claude-cli/1.0.0 (external, cli)",
            "X-App": "cli",
            "Anthropic-Beta": "claude-code-20250219",
        }
    return Anthropic(**kwargs)


def looks_like_rate_limit(err: Exception) -> bool:
    """Detect rate-limit / quota / auth failures worth retrying on the next key."""
    status = getattr(err, "status_code", None)
    if status in (401, 403, 429):
        return True
    text = str(err).lower()
    keywords = ("rate limit", "rate_limit", "quota", "insufficient", "limit reached",
                "too many requests", "credit", "balance", "unauthorized", "expired")
    return any(k in text for k in keywords)


def _insert_missing_commas(raw: str) -> str:
    """Local models sometimes drop the comma between two JSON values
    (e.g. `"a" "b"` or `} {`). Insert a comma wherever a value that has
    already closed is directly followed by the start of the next value,
    ignoring anything inside strings."""
    out, in_str, esc = [], False, False

    def prev_nonspace():
        return next((c for c in reversed(out) if not c.isspace()), "")

    for ch in raw:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch in '"{[':
            # a closed value (string/array/object) followed by a new value → comma
            p = prev_nonspace()
            if p and p in '"]}':
                out.append(",")
            if ch == '"':
                in_str = True
        out.append(ch)
    return "".join(out)


def _repair_json(raw: str):
    """Best-effort repair of a malformed JSON string from a local backend:
    insert missing commas between values, then close any open brackets."""
    s = raw.rstrip()
    s = re.sub(r",\s*$", "", s)
    try:
        return json.loads(_insert_missing_commas(s))
    except json.JSONDecodeError:
        pass
    s = _insert_missing_commas(s)
    # Walk the string, tracking open brackets outside of strings
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    if in_str:
        s += '"'
    for opener in reversed(stack):
        s += "}" if opener == "{" else "]"
    return json.loads(s)


def extract_json(text: str):
    """Pull the first JSON object/array out of a model reply (handles ```json fences
    and best-effort repair of truncated replies from local backends)."""
    match = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL)
    if match:
        raw = match.group(1)
    else:
        start = min(
            (i for i in (text.find("{"), text.find("[")) if i != -1),
            default=-1,
        )
        end = max(text.rfind("}"), text.rfind("]"))
        if start == -1:
            raise ValueError(f"No JSON found in reply:\n{text[:300]}")
        raw = text[start:end + 1] if end > start else text[start:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _repair_json(raw)  # truncated reply — close open brackets and retry


def _extract_text(msg) -> str:
    """Join all text blocks, skipping thinking/other blocks (extended thinking)."""
    parts = [getattr(b, "text", None) for b in msg.content]
    text = "".join(p for p in parts if p)
    if not text:
        raise ValueError(f"No text blocks in reply (blocks: {[b.type for b in msg.content]})")
    return text


# ─── Backend 1: Proxy Claude (Anthropic SDK) ─────────────────────────────────

def _call_claude(keys, config, model, prompt, max_tokens, label, web_search):
    """Try each proxy key in turn; switch on rate-limit/auth errors."""
    kwargs = {}
    if web_search > 0:
        kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": web_search,
        }]

    last_err = None
    for idx, key in enumerate(keys):
        client = build_client(key, config)
        key_label = f"key #{idx + 1}/{len(keys)} (…{key[-4:]})"
        try:
            log(f"   🔑 {label} — Claude {key_label}")
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return _extract_text(msg)
        except Exception as e:
            last_err = e
            log(f"   ⚠️  Claude {key_label} failed: {str(e)[:120]}")
            continue
    raise RuntimeError(f"All {len(keys)} Claude keys failed. Last: {last_err}")


# ─── Backend 2: Local ChatGPT bridge (OpenAI-compatible) ──────────────────────

def _call_chatgpt(config, prompt, label):
    """Call the bundled ChatGPT bridge's OpenAI-compatible endpoint.

    Self-contained native binary (vendor/chatgpt/chatgpt-server) — no Docker, no
    OrbStack. It boots itself if down and reads cookies.json synced by the ChatGPT
    Chrome extension. Falls back to a plain HTTP call if the bundle isn't present."""
    from core import chatgpt_server
    base = config.get("CHATGPT_SERVER_URL", "http://localhost:9225")
    log(f"   💬 {label} — local ChatGPT ({base})")
    text = chatgpt_server.chat(config, prompt)
    if not text:
        raise RuntimeError("chatgpt returned no text")
    return text


# ─── Backend 3: Local Gemini (bundled HTTP server, shared with stage 09) ──────

def _call_gemini(config, prompt, label):
    """Call the bundled Gemini server's /chat endpoint (native binary, on-demand).

    Same self-contained server stage 09 uses for music — no Docker, no MCP. It boots
    itself if down and reads cookies.json synced by the Gemini Chrome extension."""
    from core import gemini_server
    log(f"   ✨ {label} — local Gemini (bundled server)")
    text = gemini_server.chat(config, prompt)
    if not text:
        raise RuntimeError("gemini returned no text")
    return text


# ─── Orchestrator: try Claude → ChatGPT → Gemini ──────────────────────────────

def call_ai(keys: list, config: dict, model: str, prompt: str,
            max_tokens: int = 4096, expect_json: bool = True,
            label: str = "AI call", web_search: int = 0):
    """Run prompt through the backend failover chain.

    Order: proxy Claude (all keys) → local ChatGPT (9225) → local Gemini.
    Returns parsed JSON (expect_json=True) or raw text (expect_json=False).
    web_search only applies to the Claude backend; local backends already have
    their own browsing/tools via the logged-in session.
    """
    backends = [
        ("Claude", lambda: _call_claude(keys, config, model, prompt,
                                        max_tokens, label, web_search)),
        ("ChatGPT", lambda: _call_chatgpt(config, prompt, label)),
        ("Gemini", lambda: _call_gemini(config, prompt, label)),
    ]

    last_err = None
    for name, fn in backends:
        for attempt in (1, 2):  # each backend gets 2 tries before moving on
            try:
                text = fn()
                return extract_json(text) if expect_json else text.strip()
            except Exception as e:
                last_err = e
                where = f"'{name}' try {attempt}/2"
                if attempt == 1:
                    log(f"⚠️  Backend {where} failed ({str(e)[:100]}). Retrying...")
                else:
                    log(f"⚠️  Backend {where} failed ({str(e)[:100]}). Falling back...")
    raise SystemExit(f"❌ All backends (Claude → ChatGPT → Gemini) failed. Last: {last_err}")

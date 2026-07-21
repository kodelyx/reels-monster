#!/usr/bin/env python3
"""Pre-flight — verify every external service the media stages need is up.

Run before stages 05-10 so a run never dies halfway with 0 Flow credits or a
dead ChatGPT/Gemini service. Importable (`run(config, paths)`) and CLI.

  python3 core/preflight.py -p /path/to/reels-monster
Migrated from reel-factory scripts/preflight.py — checks unchanged, paths/getters
now come from core.config.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parent))
from core.config import (PATHS, load_config, flow_api_url, chatgpt_url,
                         gemini_container, gemini_music_url)

try:
    import requests
except ImportError:
    requests = None

OK, BAD = "✅", "❌"


def check_avatar_image(paths: PATHS):
    return paths.AVATAR_IMAGE.exists(), str(paths.AVATAR_IMAGE)


def check_flow_credits(config):
    # Bundled self-contained server (Python/FastAPI in vendor/flow/, run via uv). We
    # boot it on-demand — one warm-up primes both avatar (05) and b-roll (08). If the
    # bundle isn't present we just probe an external server on :8001.
    from core import flow_server
    from core.config import flow_server_dir
    if flow_server_dir(config):
        ok, detail = flow_server.warmup(config)
        if not ok:
            return False, f"bundled → {detail}"
        # server + extension up → now the credits probe below is meaningful
    base = flow_api_url(config)
    if requests is None:
        return False, "requests not installed"
    try:
        # Aggregating credits across many connected clients (17+) can take
        # >6s, so give the probe generous headroom — a slow-but-alive server
        # must not be misread as "unreachable" and block the whole pipeline.
        r = requests.get(f"{base}/v1/credits", timeout=30)
        data = r.json()
    except Exception as e:
        return False, f"Flow API unreachable at {base} ({str(e)[:60]})"
    if "total_credits" in data:
        n = data["total_credits"]
        return (n > 0), f"{n} credits"
    if "credits" in data:
        n = data["credits"]
        return (n > 0), f"{n} credits"
    if data.get("detail") == "NO_FLOW_KEY":
        return False, "NO_FLOW_KEY — Flow session/key not loaded (sync your Flow login)"
    return False, f"unexpected: {str(data)[:80]}"


def check_chatgpt(config):
    # Bundled self-contained server (native binary in vendor/chatgpt/). We boot it
    # on-demand and verify cookies are live — one warm-up primes both caption timing
    # (06) and the AI chat fallback. No Docker, no OrbStack.
    from core import chatgpt_server
    from core.config import chatgpt_server_bin
    binary = chatgpt_server_bin(config)
    if binary and os.path.exists(binary):
        ok, detail = chatgpt_server.warmup(config)
        base = chatgpt_url(config)
        return ok, (f"bundled → {base} · {detail}")
    # Legacy fallback: external / Docker server already listening on :9225.
    base = chatgpt_url(config)
    if requests is None:
        return False, "requests not installed"
    try:
        r = requests.get(f"{base}/health", timeout=5)
        d = r.json()
        if d.get("ok") and d.get("extensionConnected"):
            return True, "connected"
        return False, f"reachable but not connected: {str(d)[:60]}"
    except Exception as e:
        return False, f"unreachable at {base} ({str(e)[:50]})"


def check_gemini(config):
    # Bundled self-contained server (native binary in vendor/gemini/). We boot it
    # on-demand and verify cookies are live — one warm-up primes both music (09)
    # and the AI chat fallback. No Docker, no MCP.
    from core import gemini_server
    from core.config import gemini_server_bin
    binary = gemini_server_bin(config)
    if binary and os.path.exists(binary):
        ok, detail = gemini_server.warmup(config)
        base = gemini_music_url(config)
        return ok, (f"bundled → {base} · {detail}")
    # Legacy fallback: external native binary or docker container.
    native = config.get("GEMINI_MCP_BIN", "")
    if native and os.path.exists(native):
        base = gemini_music_url(config)
        if requests is None:
            return (True, f"native binary (HTTP check skipped: requests missing)")
        try:
            requests.get(f"{base}/", timeout=5)  # 404 is fine — server answered
            return True, f"native → {base}"
        except Exception as e:
            return False, f"native binary set but API down at {base} ({str(e)[:40]})"
    container = gemini_container(config)
    try:
        r = subprocess.run(["docker", "ps", "--filter", f"name={container}",
                            "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
        return (container in r.stdout), (r.stdout.strip() or "not running")
    except Exception as e:
        return False, str(e)[:50]


def run(config, paths: PATHS):
    """Returns (all_ok, blocking_list). Prints a report."""
    from core.config import elevenlabs_api_key
    print("🔍 Pre-flight check for media stages\n")
    checks = [
        ("Avatar image", check_avatar_image(paths)),
        ("Flow API + credits (avatar/broll)", check_flow_credits(config)),
        ("Gemini API (music/trim)", check_gemini(config)),
    ]
    # ChatGPT check: only blocking if ElevenLabs key is missing (ChatGPT is fallback)
    elevenlabs_key = elevenlabs_api_key(config)
    chatgpt_ok, chatgpt_msg = check_chatgpt(config)
    if elevenlabs_key:
        # ElevenLabs primary, ChatGPT optional fallback
        status = f"{chatgpt_msg} (fallback only, ElevenLabs primary)"
        print(f"  {OK if chatgpt_ok else '⚠️ '} ChatGPT server (captions fallback): {status}")
    else:
        # No ElevenLabs — ChatGPT is required
        checks.append(("ChatGPT server (captions)", (chatgpt_ok, chatgpt_msg)))

    blocking = []
    for name, (ok, msg) in checks:
        print(f"  {OK if ok else BAD} {name}: {msg}")
        if not ok:
            blocking.append(name)
    print()
    return (len(blocking) == 0), blocking


def main():
    parser = argparse.ArgumentParser(description="Media pipeline pre-flight check")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parent))
    args = parser.parse_args()
    paths = PATHS(args.project)
    config = load_config(paths.ROOT)
    all_ok, blocking = run(config, paths)
    if all_ok:
        print("🎉 All systems go.")
        return 0
    print(f"⚠️  Not ready — blocked by: {', '.join(blocking)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

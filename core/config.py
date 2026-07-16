"""core/config.py — single source of truth for paths and service endpoints.

⭐ P1 FIX (see docs/PRD.md): the old reel-factory hardcoded absolute paths like
`/Users/akash/Reels-Agent/...` in THREE different places that disagreed with each
other. Here EVERY path is derived from PROJECT_ROOT, so the whole project can be
moved/renamed and still work. `config.env` holds ONLY service endpoints + tunables
+ API keys — never paths.

Usage:
    from core.config import load_config, PATHS
    cfg = load_config(project_root)      # dict of endpoints/keys from config.env
    p = PATHS(project_root)              # all derived paths (project-relative)
"""
import os
from pathlib import Path

# reels-monster package root (this file lives at <root>/core/config.py). Used to
# locate bundled binaries (vendor/gemini/...) regardless of the current cwd.
_PKG_ROOT = Path(__file__).resolve().parents[1]

# ─── Path resolution (everything relative to the project root) ────────────────

class PATHS:
    """All project paths, derived from the project root. No absolute paths baked in."""

    def __init__(self, project_root):
        self.ROOT = Path(project_root).resolve()

        # top-level dirs
        self.PROFILE = self.ROOT / "profile"
        self.SFX = self.ROOT / "sfx"
        self.REMOTION = self.ROOT / "remotion"
        self.OUTPUT = self.ROOT / "output"

        # runtime workspace (git-ignored, cleared per project)
        self.PROJECT = self.ROOT / "project"
        self.SCRIPTING = self.PROJECT / "scripting"
        self.AVATAR = self.PROJECT / "avatar"
        self.BROLL = self.PROJECT / "broll"
        self.MUSIC = self.PROJECT / "music"
        self.INTERVALS = self.PROJECT / "intervals"

        # profile inputs
        self.PROFILE_JSON = self.PROFILE / "profile.json"
        # Accept either avatar.jpg or avatar.png (whichever the user provided).
        self.AVATAR_IMAGE = next(
            (self.PROFILE / f"avatar.{ext}" for ext in ("jpg", "png", "jpeg", "webp")
             if (self.PROFILE / f"avatar.{ext}").exists()),
            self.PROFILE / "avatar.jpg")
        self.TOPIC_HISTORY = self.PROFILE / "topic_history.json"

        # state + stage outputs (these ARE the handover contract — see contracts.py)
        self.STATE = self.PROJECT / "state.json"
        self.TOPIC = self.PROJECT / "topic.json"
        self.PRE_PRODUCTION = self.SCRIPTING / "pre_production.json"
        self.SCRIPT = self.SCRIPTING / "script.json"
        self.SCENES = self.SCRIPTING / "scenes.json"
        self.MUSIC_PROMPT = self.SCRIPTING / "music_prompt.txt"
        self.CAPTION = self.SCRIPTING / "caption.json"
        self.BG_MUSIC = self.MUSIC / "bg_music.mp3"

        # final render outputs
        self.FINAL = self.OUTPUT / "final.mp4"
        self.FINAL_TRIMMED = self.OUTPUT / "final_trimmed.mp4"

    def ensure_dirs(self):
        """Create the runtime workspace dirs if missing (safe to call anytime)."""
        for d in (self.PROJECT, self.SCRIPTING, self.AVATAR, self.BROLL,
                  self.MUSIC, self.INTERVALS, self.OUTPUT):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def rel(self, path):
        """Return `path` relative to ROOT (for logs/state.json). Absolute → project-relative."""
        try:
            return str(Path(path).resolve().relative_to(self.ROOT))
        except ValueError:
            return str(path)


# ─── config.env loader (endpoints, model names, API keys — NO paths) ──────────

# Keys that must never appear in config.env (they are paths — derive from PATHS).
_FORBIDDEN_PATH_KEYS = {
    "RAPID_EDIT_SCRIPT_PATH", "REMOTION_BROLL_DIR", "REMOTION_AVATAR_DIR",
    "REMOTION_CAPTION_JSON_PATH", "TALKING_AVATAR_SCRIPT_PATH",
    "AVATAR_IMAGE_PATH", "SCRIPT_JSON_PATH", "SCENES_JSON_PATH", "SFX_DIR",
}


def load_config(project_root) -> dict:
    """Read config.env (key=value). Environment variables override file values.

    Only service endpoints / model names / API keys are expected here. If a legacy
    path key is found it is ignored with a warning (paths now come from PATHS).
    """
    config = {}
    env_file = Path(project_root).resolve() / "config.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in _FORBIDDEN_PATH_KEYS:
                continue  # legacy path key — ignored, PATHS is the source of truth
            config[key] = val

    # env overrides (for AI creds especially)
    for key in ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL", "CHATGPT_SERVER_URL",
                "FLOW_API_URL", "GEMINI_DOCKER_CONTAINER", "GEMINI_MCP_PATH",
                "GEMINI_MUSIC_URL", "GEMINI_MCP_BIN",
                "GEMINI_SERVER_BIN", "GEMINI_SERVER_DIR",
                "CHATGPT_SERVER_BIN", "CHATGPT_SERVER_DIR",
                "FLOW_SERVER_DIR"):
        if os.environ.get(key):
            config[key] = os.environ[key]

    return config


# ─── convenience getters (with sane defaults) ─────────────────────────────────

def flow_api_url(config: dict) -> str:
    return config.get("FLOW_API_URL", "http://localhost:8001")


def flow_server_dir(config: dict) -> str:
    """Working dir for the bundled Flow server (Python/FastAPI, run via `uv run`).

    Default: reels-monster/vendor/flow. Holds cli/ omniflash/ flow_cli/ (source),
    pyproject.toml (uv resolves deps from it), config.env, and output/. The server
    runs with this as its cwd. Empty ⇒ assume an external server at FLOW_API_URL."""
    val = config.get("FLOW_SERVER_DIR", "")
    if val:
        return val
    default = _PKG_ROOT / "vendor" / "flow"
    return str(default) if (default / "cli" / "api.py").exists() else ""


def chatgpt_url(config: dict) -> str:
    return config.get("CHATGPT_SERVER_URL", "http://localhost:9225")


def chatgpt_server_bin(config: dict) -> str:
    """Path to the bundled, self-contained ChatGPT HTTP bridge binary.

    Default: reels-monster/vendor/chatgpt/chatgpt-server (native macOS build of
    kodelyx/chatgpt-free-api). When present, stages launch it on-demand (project-
    local data dir) and talk to it over plain HTTP — no Docker, no OrbStack. Empty /
    missing ⇒ assume an already-running server at CHATGPT_SERVER_URL."""
    val = config.get("CHATGPT_SERVER_BIN", "")
    if val:
        return val
    default = _PKG_ROOT / "vendor" / "chatgpt" / "chatgpt-server"
    return str(default) if default.exists() else ""


def chatgpt_server_dir(config: dict) -> str:
    """Working dir for the bundled ChatGPT server. Holds cookies.json (synced by the
    Chrome extension over ws://localhost:9225), .env and output/. The server runs
    with this as its cwd."""
    val = config.get("CHATGPT_SERVER_DIR", "")
    if val:
        return val
    return str(_PKG_ROOT / "vendor" / "chatgpt")


def gemini_container(config: dict) -> str:
    return config.get("GEMINI_DOCKER_CONTAINER", "free-gemini-api")


def gemini_mcp_path(config: dict) -> str:
    return config.get("GEMINI_MCP_PATH", "/app/gemini-mcp")


def gemini_mcp_bin(config: dict) -> str:
    """Path to the NATIVE gemini-mcp binary (no Docker). If set + present, stages
    invoke it directly instead of `docker exec`. Empty ⇒ fall back to docker."""
    return config.get("GEMINI_MCP_BIN", "")


def gemini_music_url(config: dict) -> str:
    """Host-side base URL for the Gemini music server's /output/ files.

    The MCP tool replies with a *container-internal* URL (localhost:8001), but the
    container maps that port to 8002 on the host (docker-compose 8002:8001). We keep
    only the path from the MCP URL and re-root it here so downloads hit the host port.
    """
    return config.get("GEMINI_MUSIC_URL", "http://localhost:8002")


def gemini_server_bin(config: dict) -> str:
    """Path to the bundled, self-contained Gemini HTTP server binary.

    Default: reels-monster/vendor/gemini/gemini-server. When present, stage 09
    launches it on-demand (project-local data dir) and talks to it over plain
    HTTP POST /music — no Docker, no separate free-gemini-api checkout, no MCP.
    Empty / missing ⇒ stage 09 assumes an already-running server at GEMINI_MUSIC_URL.
    """
    val = config.get("GEMINI_SERVER_BIN", "")
    if val:
        return val
    default = _PKG_ROOT / "vendor" / "gemini" / "gemini-server"
    return str(default) if default.exists() else ""


def gemini_server_dir(config: dict) -> str:
    """Working dir for the bundled server. Holds cookies.json (synced by the Chrome
    extension) and output/ (generated tracks). The server runs with this as its cwd."""
    val = config.get("GEMINI_SERVER_DIR", "")
    if val:
        return val
    return str(_PKG_ROOT / "vendor" / "gemini")


def ai_model(config: dict) -> str:
    return config.get("AI_MODEL", "claude-opus-4-8")

"""core/media_utils.py — deterministic media checks (extracted from auto_media.py).

Pure, side-effect-free helpers the orchestrator and stages use to VERIFY that a
media file is real before handing off to the next stage (Layer A, docs/Architecture.md §4).
"""
import json
import subprocess
from pathlib import Path

MIN_MP4_BYTES = 10_000       # smaller than this = almost certainly a broken/empty file
MIN_MP4_SECONDS = 0.3        # shorter than this = not a usable clip


def probe_duration(path) -> float:
    """Return media duration in seconds via ffprobe, or 0.0 if unreadable."""
    path = Path(path)
    if not path.exists():
        return 0.0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip() or 0)
    except (ValueError, subprocess.SubprocessError, OSError):
        return 0.0


def mp4_ok(path):
    """(ok, duration_seconds) — True only if `path` is a real, playable, non-trivial mp4."""
    path = Path(path)
    if not path.exists() or path.stat().st_size < MIN_MP4_BYTES:
        return False, 0.0
    dur = probe_duration(path)
    return dur > MIN_MP4_SECONDS, dur


def audio_ok(path):
    """(ok, duration_seconds) — True if `path` is a non-trivial audio file (e.g. bg_music.mp3)."""
    path = Path(path)
    if not path.exists() or path.stat().st_size < 1_000:
        return False, 0.0
    dur = probe_duration(path)
    return dur > MIN_MP4_SECONDS, dur


def n_scenes(paths) -> int:
    """Number of scenes = number of segments in script.json. 0 if not written yet.

    `paths` is a core.config.PATHS instance.
    """
    if not paths.SCRIPT.exists():
        return 0
    try:
        data = json.loads(paths.SCRIPT.read_text(encoding="utf-8"))
        return len(data.get("segments", []))
    except (json.JSONDecodeError, OSError):
        return 0

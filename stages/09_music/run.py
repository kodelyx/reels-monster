#!/usr/bin/env python3
"""Stage 09 — Background music.

Reads music_prompt.txt, generates a track via the bundled, self-contained Gemini
server (native binary at vendor/gemini/gemini-server, booted on-demand), downloads
the rendered file over plain HTTP, transcodes to a real mp3, and copies it into
remotion/public/ so Remotion always picks up the fresh track.

  requires:  project/scripting/music_prompt.txt
  produces:  project/music/bg_music.mp3  (+ remotion/public/bg_music.mp3 copy)

No Docker, no MCP, no separate free-gemini-api checkout — the server binary lives in
this repo and starts itself when needed, reading cookies.json synced by the Gemini
Chrome extension (ws://localhost:9226).

Run:  python3 stages/09_music/run.py -p /path/to/reels-monster
"""
import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, gemini_music_url
from core.ai_client import log
from core import gemini_server


def pick_track_url(config, resp: dict) -> str:
    """Pull the served /output/ URL out of the /music JSON response.

    The server returns music[].local_path = http://<host>/output/....mp3 (served by
    its own /output/ route). We prefer that over download_url (Google's raw provider
    link, which our host can't re-serve). Re-root the host at our configured base URL
    so the port always matches even if the server reports a different one.
    """
    tracks = resp.get("music") or []
    if not tracks:
        raise RuntimeError(f"No music track in Gemini response: {str(resp)[:200]}")
    local = tracks[0].get("local_path")
    if not local:
        raise RuntimeError(f"Track had no local_path: {str(tracks[0])[:200]}")
    base = urlsplit(gemini_music_url(config))
    target = urlsplit(local)
    return urlunsplit((base.scheme, base.netloc, target.path, target.query, ""))


def _link_public(paths):
    # Remotion's dev server serves symlinked *directories* (avatar/broll) but NOT
    # symlinked *files* in public/ — a `bg_music.mp3` symlink 404s at render time.
    # Copy the real bytes in so the static handler always finds it.
    public_file = paths.REMOTION / "public" / "bg_music.mp3"
    public_file.parent.mkdir(parents=True, exist_ok=True)
    if public_file.exists() or public_file.is_symlink():
        public_file.unlink()
    shutil.copyfile(paths.BG_MUSIC, public_file)


def make_silent(paths, seconds: int = 60):
    """Write a silent bg_music.mp3 so a music outage never blocks the render.
    The video still gets narration + SFX; only the background bed is silent."""
    paths.MUSIC.mkdir(parents=True, exist_ok=True)
    final_file = paths.BG_MUSIC
    ff = subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                         "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                         "-t", str(seconds), "-codec:a", "libmp3lame", "-q:a", "4",
                         str(final_file)], capture_output=True, text=True)
    if ff.returncode != 0 or not final_file.exists():
        raise SystemExit(f"❌ Could not create silent fallback: {ff.stderr[-300:]}")
    (paths.MUSIC / "_PLACEHOLDER.txt").write_text(
        "Silent placeholder — Gemini music was unavailable (Chrome extension cookies "
        "not synced). Re-run stage 09 once cookies are live to get the real track.\n")
    _link_public(paths)


# Hard negative guard ALWAYS appended to every music prompt before it reaches
# Lyria — the model has ignored an in-prose "instrumental" hint and produced sung
# vocals/lyrics (an English voice bleeding under the Hindi narration). Enforcing it
# here (not just in the stage-04 AI prompt) guarantees the guard is present even if
# the AI forgets to write it. Keep it blunt and explicit — Lyria responds to plain
# negatives.
INSTRUMENTAL_GUARD = (
    " STRICTLY INSTRUMENTAL ONLY. Absolutely NO vocals, NO lyrics, NO singing, "
    "NO humming, NO chanting, NO choir, NO spoken word, NO human voice of any kind. "
    "Pure instrumental background score with zero voices."
)


def _with_instrumental_guard(prompt: str) -> str:
    """Append the no-vocals guard unless the prompt already ends with it."""
    if "STRICTLY INSTRUMENTAL ONLY" in prompt:
        return prompt
    return prompt.rstrip() + INSTRUMENTAL_GUARD


def try_generate_music(config, paths) -> bool:
    """Attempt the real Gemini track. Return True on success, False on any failure."""
    prompt = _with_instrumental_guard(paths.MUSIC_PROMPT.read_text(encoding="utf-8").strip())
    log("🎵 Generating music via bundled Gemini server (Lyria 3) ...")
    log("   🔇 instrumental guard enforced (no vocals/lyrics/singing).")
    try:
        resp = gemini_server.generate_music(config, prompt)
        url = pick_track_url(config, resp)
    except Exception as e:
        log(f"⚠️ Music generation failed: {str(e)[:200]}")
        return False

    paths.MUSIC.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlsplit(url).path).suffix or ".mp3"
    raw_file = paths.MUSIC / f"_raw{suffix}"
    final_file = paths.BG_MUSIC

    title = (resp.get("music") or [{}])[0].get("title", "")
    log(f"   ▶ downloading track{f' “{title}”' if title else ''} from {url}")
    try:
        urllib.request.urlretrieve(url, str(raw_file))
    except Exception as e:
        log(f"⚠️ Music download failed: {str(e)[:160]}")
        return False

    if not raw_file.exists() or raw_file.stat().st_size < 10_000:
        size = raw_file.stat().st_size if raw_file.exists() else 0
        log(f"⚠️ Downloaded music file too small ({size} bytes).")
        raw_file.unlink(missing_ok=True)
        return False

    # Always transcode to a real .mp3 (Lyria may return mp3/wav) so the file's
    # extension always matches its actual content.
    ff = subprocess.run(["ffmpeg", "-y", "-i", str(raw_file), "-codec:a", "libmp3lame",
                         "-qscale:a", "2", str(final_file)], capture_output=True, text=True)
    raw_file.unlink(missing_ok=True)
    if ff.returncode != 0 or not final_file.exists():
        log(f"⚠️ ffmpeg transcode failed: {ff.stderr[-200:]}")
        return False

    # Clear any stale placeholder marker from a prior silent fallback.
    (paths.MUSIC / "_PLACEHOLDER.txt").unlink(missing_ok=True)
    _link_public(paths)
    log(f"✅ Music ready: {paths.rel(final_file)} (copied into remotion/public/bg_music.mp3)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Stage 09 — Background music")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    parser.add_argument("--require-music", action="store_true",
                        help="fail (exit 1) if the real track can't be generated, "
                             "instead of falling back to a silent bed")
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)

    if not paths.MUSIC_PROMPT.exists():
        raise SystemExit(f"❌ music_prompt.txt not found at {paths.MUSIC_PROMPT} — run stage 04 first.")
    if not paths.MUSIC_PROMPT.read_text(encoding="utf-8").strip():
        raise SystemExit("❌ music_prompt.txt is empty.")

    if try_generate_music(config, paths):
        return

    # Real music unavailable — usually the Gemini Chrome-extension cookies aren't
    # synced. Don't hold the whole video hostage to the background bed.
    if args.require_music:
        raise SystemExit("❌ Music generation failed and --require-music was set. "
                         "Connect the Gemini Chrome extension (cookies) and retry.")
    log("⚠️  ─────────────────────────────────────────────────────────────")
    log("⚠️  Falling back to a SILENT background track so the render can run.")
    log("⚠️  To get real music: connect the Gemini Chrome extension, then")
    log("⚠️  re-run:  python3 stages/09_music/run.py -p .   (overwrites the bed)")
    log("⚠️  ─────────────────────────────────────────────────────────────")
    make_silent(paths)
    log(f"✅ Silent placeholder ready: {paths.rel(paths.BG_MUSIC)}")


if __name__ == "__main__":
    main()

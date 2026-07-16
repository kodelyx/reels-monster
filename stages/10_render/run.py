#!/usr/bin/env python3
"""Stage 10 — Remotion render.

Ensures remotion/public symlinks point at the current project media, then renders
the split-screen composite (B-roll + avatar + karaoke captions + popups + music)
with Bun, driven by caption.json.

  requires:  project/scripting/caption.json, project/music/bg_music.mp3,
             project/avatar/*, project/broll/*
  produces:  output/final.mp4

Run:  python3 stages/10_render/run.py -p /path/to/reels-monster
New thin wrapper around the `bunx remotion render` command from reel-factory's README
(the old flow ran it by hand). Logic = same command, paths via core.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS
from core.ai_client import log

# public/ symlink → project source (so Remotion always sees fresh media).
# NOTE: only *directories* are symlinked — Remotion's dev server serves those.
# A symlinked *file* (bg_music.mp3) 404s, so that one is copied in below.
LINKS = {
    "avatar": Path("..") / ".." / "project" / "avatar",
    "broll": Path("..") / ".." / "project" / "broll",
    "sfx": Path("..") / ".." / "sfx",
}


def ensure_symlinks(paths: PATHS):
    public = paths.REMOTION / "public"
    public.mkdir(parents=True, exist_ok=True)
    for name, target in LINKS.items():
        link = public / name
        if link.exists() or link.is_symlink():
            if link.is_symlink() or link.is_file():
                link.unlink()
            else:  # a real directory (shouldn't happen) — leave it
                continue
        link.symlink_to(target)
    # bg_music.mp3 must be a real file, not a symlink (Remotion won't serve a
    # symlinked file — it 404s). Copy the current track in.
    music_dst = public / "bg_music.mp3"
    if paths.BG_MUSIC.exists():
        if music_dst.exists() or music_dst.is_symlink():
            music_dst.unlink()
        shutil.copyfile(paths.BG_MUSIC, music_dst)
    # caption.json → props (Remotion reads it via --props too, but keep the link fresh)
    props = paths.REMOTION / "props" / "caption.json"
    props.parent.mkdir(parents=True, exist_ok=True)
    if props.exists() or props.is_symlink():
        props.unlink()
    props.symlink_to(Path("..") / ".." / "project" / "scripting" / "caption.json")


def main():
    parser = argparse.ArgumentParser(description="Stage 10 — Remotion render")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    if not paths.CAPTION.exists():
        raise SystemExit(f"❌ caption.json not found: {paths.CAPTION} — run stage 06/07 first.")

    ensure_symlinks(paths)
    paths.OUTPUT.mkdir(parents=True, exist_ok=True)

    cmd = ["bunx", "remotion", "render", "src/index.ts", "Documentary",
           str(paths.FINAL), f"--props={paths.CAPTION}"]
    # Reuse an already-installed Chrome if one is pointed to via REMOTION_CHROME
    # (or a common playwright cache) so Remotion never needs to download its own
    # headless shell — critical on machines that can't reach googleapis.com.
    chrome = os.environ.get("REMOTION_CHROME", "")
    if chrome and os.path.exists(chrome):
        cmd.append(f"--browser-executable={chrome}")
        log(f"   using Chrome: {chrome}")
    log(f"🎬 Rendering with Remotion (Bun) → {paths.rel(paths.FINAL)}")
    log(f"   {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(paths.REMOTION))
    if proc.returncode != 0 or not paths.FINAL.exists():
        raise SystemExit(f"❌ Remotion render failed (exit {proc.returncode}).")
    log(f"✅ Rendered: {paths.rel(paths.FINAL)}")


if __name__ == "__main__":
    main()

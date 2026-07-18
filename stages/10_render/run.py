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
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config
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


def popups_enabled(config: dict) -> bool:
    """ENABLE_POPUPS toggle from config.env / env. Default ON (back-compat).

    Set ENABLE_POPUPS=false (or 0/no/off) to render WITHOUT the icon popups —
    without re-running stage 07. The popup data stays untouched in caption.json;
    we just render from a popup-stripped copy, so flipping it back to true and
    re-rendering brings the icons straight back (no AI cost).
    """
    val = str(config.get("ENABLE_POPUPS", "true")).strip().lower()
    return val not in ("false", "0", "no", "off")


def build_render_caption(paths: PATHS, keep_popups: bool) -> Path:
    """Return the caption path to render from.

    Popups ON  → the real caption.json (unchanged).
    Popups OFF → a sibling caption.no_popups.json with every scene's `popup`
    field removed. The original is never modified. SFX ride on popups, so
    dropping popup drops their sfx too (BG-music ducking reads the same field,
    so it stays consistent automatically).
    """
    if keep_popups:
        return paths.CAPTION
    data = json.loads(paths.CAPTION.read_text(encoding="utf-8"))
    stripped = 0
    for scene in data.get("scenes", []):
        if scene.pop("popup", None) is not None:
            stripped += 1
    out = paths.CAPTION.parent / "caption.no_popups.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"   🚫 Popups OFF (ENABLE_POPUPS=false) — stripped {stripped} scene(s); "
        f"rendering from {paths.rel(out)} (caption.json untouched).")
    return out


def main():
    parser = argparse.ArgumentParser(description="Stage 10 — Remotion render")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    if not paths.CAPTION.exists():
        raise SystemExit(f"❌ caption.json not found: {paths.CAPTION} — run stage 06/07 first.")

    config = load_config(args.project)
    ensure_symlinks(paths)
    paths.OUTPUT.mkdir(parents=True, exist_ok=True)

    render_caption = build_render_caption(paths, popups_enabled(config))

    cmd = ["bunx", "remotion", "render", "src/index.ts", "Documentary",
           str(paths.FINAL), f"--props={render_caption}"]
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

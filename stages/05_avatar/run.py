#!/usr/bin/env python3
"""Stage 05 — Talking Avatar generation.

For each narration segment, generates a talking-avatar clip via the local Flow API
(using profile/avatar.jpg as the identity reference), in parallel with retries.

  requires:  project/scripting/script.json (segments), profile/avatar.jpg
  produces:  project/avatar/scene_N.mp4  (one per segment)

Run:  python3 stages/05_avatar/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/avatar_generator.py (logic unchanged; paths via core).
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS
from core.ai_client import log

GENERATOR = STAGE_DIR / "generate_talking_avatar.py"


def avatar_duration(narration: str) -> int:
    # Match clip length to narration so the full line is spoken WITHOUT dead air.
    # Flow supports only 6/8/10s. Pick the SMALLEST bucket that still fits the
    # spoken line (~2.3 Hindi words/sec). No +1 headroom — that used to over-size
    # the clip (e.g. an 8s line got a 10s clip), leaving 1-2s of silence the model
    # tried to fill by stretching/repeating words, which broke the lip-sync.
    speech = len(narration.split()) / 2.3
    for bucket in (6, 8, 10):
        if speech <= bucket:
            return bucket
    return 10


def generate_batch(todo, paths: PATHS):
    """Launch a batch of scenes in parallel; return the set that succeeded."""
    processes = []
    for seg in todo:
        scene_num = seg["scene"]
        narration = seg["narration"]
        temp_dir = paths.PROJECT / f"temp_avatar_scene_{scene_num}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dur = avatar_duration(narration)
        print(f"🎬 Scene {scene_num}: {len(narration.split())} words → {dur}s clip.")
        cmd = ["python3", str(GENERATOR),
               "--dialogue", narration,
               "--aspect", "landscape",
               "--duration", str(dur),
               "--avatar", str(paths.AVATAR_IMAGE),
               "--output", str(temp_dir)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append((scene_num, p, temp_dir))

    print("\n⏳ Generations running in parallel. Monitoring...\n")
    done = set()
    for scene_num, p, temp_dir in processes:
        _, stderr = p.communicate()
        files = list(temp_dir.glob("talking_avatar_*.mp4")) if p.returncode == 0 else []
        if files:
            shutil.move(str(files[0]), str(paths.AVATAR / f"scene_{scene_num}.mp4"))
            print(f"✅ Scene {scene_num} done.")
            done.add(scene_num)
        else:
            print(f"❌ Scene {scene_num} failed (will retry): {(stderr or '')[-120:]}")
        shutil.rmtree(temp_dir, ignore_errors=True)
    return done


def main():
    parser = argparse.ArgumentParser(description="Stage 05 — Talking Avatar generation")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    if not paths.SCRIPT.exists():
        print(f"❌ script.json not found: {paths.SCRIPT}")
        sys.exit(1)

    segments = json.loads(paths.SCRIPT.read_text(encoding="utf-8")).get("segments", [])
    if not segments:
        print("❌ No segments found in script.json.")
        sys.exit(1)

    paths.AVATAR.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Generating {len(segments)} avatar videos...")
    print(f"📁 Project directory: {paths.ROOT}")

    # Resume-friendly: skip scenes whose clip already exists (a prior run made it),
    # so a mid-stage failure only re-generates the missing scenes on --resume
    # instead of burning Flow credits redoing good clips.
    def existing(seg):
        f = paths.AVATAR / f"scene_{seg['scene']}.mp4"
        return f.exists() and f.stat().st_size > 10_000
    already = [s["scene"] for s in segments if existing(s)]
    if already:
        print(f"↩️  Reusing {len(already)} existing clip(s): scene(s) {', '.join(map(str, already))}")

    # up to 3 attempts — transient Flow failures are common; retry only misses.
    # Back off before each retry so Flow can recover from a 500 (hammering it
    # back-to-back just gets the same server-side error again).
    remaining = [s for s in segments if not existing(s)]
    for attempt in range(1, 4):
        if not remaining:
            break
        if attempt > 1:
            backoff = 15 * (attempt - 1)
            print(f"\n🔁 Retry attempt {attempt} for {len(remaining)} failed scene(s) "
                  f"(waiting {backoff}s for Flow to recover)...")
            time.sleep(backoff)
        done = generate_batch(remaining, paths)
        remaining = [s for s in remaining if s["scene"] not in done]

    if remaining:
        failed = ", ".join(str(s["scene"]) for s in remaining)
        print(f"\n❌ Scenes still failed after retries: {failed}")
        sys.exit(1)

    print("\n🎉 Batch avatar generation completed!")


if __name__ == "__main__":
    main()

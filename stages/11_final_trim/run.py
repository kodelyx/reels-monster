#!/usr/bin/env python3
"""Stage 11 — Final silence trim (optional).

Applies whole-video keep-interval cuts to the rendered composite so transitions
sync tightly. Intervals come from a hand/auto-authored config; if it's absent this
stage is a no-op (final.mp4 is already the finished video).

  requires:  output/final.mp4
  optional:  project/intervals/final.json  (list of [start,end] keep windows)
  produces:  output/final.mp4  (trimmed in place — no second file)

Run:  python3 stages/11_final_trim/run.py -p /path/to/reels-monster
Same engine as stage 06's silence trim (core/rapid_edit.py) — README Step 9.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS
from core.ai_client import log

RAPID_EDIT = STAGE_DIR.parents[1] / "core" / "rapid_edit.py"


def main():
    parser = argparse.ArgumentParser(description="Stage 11 — Final silence trim")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    parser.add_argument("--config", "-c", default=None,
                        help="Intervals JSON (default: project/intervals/final.json)")
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    if not paths.FINAL.exists():
        raise SystemExit(f"❌ final.mp4 not found: {paths.FINAL} — run stage 10 first.")

    config = Path(args.config) if args.config else (paths.INTERVALS / "final.json")
    if not config.exists():
        # No trim to apply — final.mp4 is already the finished, ready-to-upload
        # video. Do NOT produce a second file: the output folder must hold only
        # final.mp4 + thumbnail.png, nothing else.
        log(f"ℹ️  No trim config ({paths.rel(config)}); final.mp4 is already the final video (no extra file).")
        return

    # Trim into a private scratch dir (rapid_edit also drops temp_parts/ + a
    # concat_list.txt in its cwd), then replace final.mp4 in place so the output
    # folder stays clean — just the one finished video.
    with tempfile.TemporaryDirectory(prefix="reels_trim_") as tmp:
        tmpd = Path(tmp)
        trimmed = tmpd / "final_trimmed.mp4"
        cmd = ["python3", str(RAPID_EDIT),
               "-path", str(paths.FINAL),
               "-out", str(trimmed),
               "-config", str(config)]
        log(f"✂️  Final trim via rapid_edit → {paths.rel(paths.FINAL)}")
        proc = subprocess.run(cmd, cwd=str(tmpd))
        if proc.returncode != 0 or not trimmed.exists():
            raise SystemExit(f"❌ Final trim failed (exit {proc.returncode}).")
        shutil.copyfile(trimmed, paths.FINAL)
    log(f"✅ {paths.rel(paths.FINAL)}")


if __name__ == "__main__":
    main()

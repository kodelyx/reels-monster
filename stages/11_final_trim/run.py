#!/usr/bin/env python3
"""Stage 11 — Final silence trim (optional).

Applies whole-video keep-interval cuts to the rendered composite so transitions
sync tightly. Intervals come from a hand/auto-authored config; if it's absent this
stage is a no-op that just aliases final.mp4 → final_trimmed.mp4.

  requires:  output/final.mp4
  optional:  project/intervals/final.json  (list of [start,end] keep windows)
  produces:  output/final_trimmed.mp4

Run:  python3 stages/11_final_trim/run.py -p /path/to/reels-monster
Same engine as stage 06's silence trim (core/rapid_edit.py) — README Step 9.
"""
import argparse
import subprocess
import sys
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
        # No trim to apply — final_trimmed.mp4 would be a byte-for-byte copy of
        # final.mp4 (a wasted ~24 MB duplicate). Point it at final.mp4 with a
        # relative symlink instead: anything expecting output/final_trimmed.mp4
        # still resolves to the exact same video, with no second render/copy.
        log(f"ℹ️  No trim config ({paths.rel(config)}); linking final_trimmed.mp4 → final.mp4 (no duplicate).")
        if paths.FINAL_TRIMMED.exists() or paths.FINAL_TRIMMED.is_symlink():
            paths.FINAL_TRIMMED.unlink()
        paths.FINAL_TRIMMED.symlink_to(paths.FINAL.name)  # relative: same output/ dir
        log(f"✅ {paths.rel(paths.FINAL_TRIMMED)} → {paths.FINAL.name}")
        return

    cmd = ["python3", str(RAPID_EDIT),
           "-path", str(paths.FINAL),
           "-out", str(paths.FINAL_TRIMMED),
           "-config", str(config)]
    log(f"✂️  Final trim via rapid_edit → {paths.rel(paths.FINAL_TRIMMED)}")
    # rapid_edit writes temp_parts/ + concat_list.txt in cwd — keep them under output/.
    proc = subprocess.run(cmd, cwd=str(paths.OUTPUT))
    if proc.returncode != 0 or not paths.FINAL_TRIMMED.exists():
        raise SystemExit(f"❌ Final trim failed (exit {proc.returncode}).")
    log(f"✅ {paths.rel(paths.FINAL_TRIMMED)}")


if __name__ == "__main__":
    main()

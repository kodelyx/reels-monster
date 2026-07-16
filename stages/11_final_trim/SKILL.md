---
name: stage-11-final-trim
description: Stage 11 — optional whole-video silence trim of final.mp4 → final_trimmed.mp4 to tighten transitions.
---

# ✂️ Stage 11 — Final Silence Trim

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `output/final.mp4` | from Stage 10 |
| **optional** | `project/intervals/final.json` (keep windows) | hand/auto-authored |
| **produces** | `output/final_trimmed.mp4` | the deliverable |

## What it does
If a trim config exists, applies its keep-intervals to `final.mp4`. If it doesn't, this
stage is a safe no-op — it just copies `final.mp4` → `final_trimmed.mp4` so downstream
always has the same output name.

## Run
```bash
python3 stages/11_final_trim/run.py -p /path/to/reels-monster
# custom config:
python3 stages/11_final_trim/run.py -p /path/to/reels-monster -c path/to/intervals.json
```

## Engine
`core/rapid_edit.py` — the same GPU-accelerated ffmpeg cutter used for per-scene silence
trimming in Stage 06 (videotoolbox on macOS, NVENC on CUDA, else libx264). Temp files are
written under `output/` and cleaned up.

## Common issues
- **`final.mp4 not found`** → run Stage 10 first.
- **Output identical to input** → no trim config found (expected no-op); add
  `project/intervals/final.json` to actually cut.

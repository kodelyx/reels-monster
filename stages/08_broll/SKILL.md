---
name: stage-08-broll
description: Stage 08 — generate cinematic B-roll clips (2 per scene) via the Flow API, timed to caption durations.
---

# 🎬 Stage 08 — B-roll Generator

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/scenes.json` (`scenes`) | from Stage 03 |
| **produces** | `project/broll/scene_N_a.mp4`, `scene_N_b.mp4` | two clips per scene |

Durations are read from `caption.json` when present (to match trimmed avatar length),
else fall back to the scene default. B-roll fills the top half of the 9:16 split-screen.

## Run
```bash
python3 stages/08_broll/run.py -p /path/to/reels-monster
```

## Engine
Local **Flow API** (`FLOW_API_URL`, default `http://localhost:8001`). Scenes generate
concurrently — `threading.Semaphore(4)` caps in-flight requests. Two prompts per scene
(`_a` / `_b`) give the renderer a cut mid-scene.

## Common issues
- **All clips fail** → Flow API down or 0 credits. Run preflight / check `FLOW_API_URL`.
- **`scenes.json not found`** → run Stage 03 first.
- **Clips too short/long** → regenerate `caption.json` (Stage 06) so durations match.

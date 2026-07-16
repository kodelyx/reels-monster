---
name: stage-05-avatar
description: Stage 05 — generate a talking-avatar clip per scene via the Flow API, using the creator's avatar image.
---

# 🗣️ Stage 05 — Talking Avatar

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/script.json` (`segments`), `profile/avatar.jpg` | |
| **produces** | `project/avatar/scene_N.mp4` | one clip per segment |

Clip length auto-matched to narration (6/8/10s). Runs scenes in parallel, up to 3 retry passes.

## Run
```bash
python3 stages/05_avatar/run.py -p /path/to/reels-monster
```

## Engine
Local **Flow API** (`FLOW_API_URL`, default `http://localhost:8001`). The heavy lifting
is in `generate_talking_avatar.py` (co-located) — `run.py` just batches + retries.

## Files in this folder
- `run.py` — parallel batch driver
- `generate_talking_avatar.py` — single-clip Flow API call (identity-locked prompt)

## Common issues
- **All scenes fail** → Flow API down or 0 credits. Run preflight / check `FLOW_API_URL`.
- **`avatar.jpg` missing** → contract fails; put the image in `profile/`.

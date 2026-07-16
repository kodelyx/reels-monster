---
name: stage-06-process
description: Stage 06 — trim silence from avatar clips and align word-level karaoke captions into caption.json.
---

# ✂️ Stage 06 — Process (Trim + Caption Align)

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/avatar/scene_N.mp4`, `project/scripting/script.json` | |
| **produces** | `project/scripting/caption.json` | `{ fps, width, height, scenes, pages, style }` |

Also trims each avatar clip **in place** (raw → clean → replaces raw).

## What it does (per scene)
1. Extract audio (ffmpeg) → local **ChatGPT server** for per-word Devanagari+Hinglish timings.
2. Derive speech window → trim silence via `core/rapid_edit.py`.
3. Convert word timings to ms, apply scene offsets → global karaoke `pages`.
4. Compile `caption.json` (the file Remotion renders).

## Run
```bash
python3 stages/06_process/run.py -p /path/to/reels-monster
```

## Engine
`CHATGPT_SERVER_URL` (default `http://localhost:9225`) + ffmpeg + `core/rapid_edit.py`.

## caption.json = the critical handover file
Written here, edited by Stage 07 (popups), read by Stage 10 (render). Schema: `remotion/src/types.ts`.

## Common issues
- **`Raw video not found`** → run Stage 05 first.
- **Alignment fails 3x** → ChatGPT server down; scene is skipped (check server at `:9225`).

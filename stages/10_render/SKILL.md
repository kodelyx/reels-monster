---
name: stage-10-render
description: Stage 10 — render the final 9:16 composite (B-roll + avatar + karaoke captions + popups + music) with Remotion via Bun.
---

# 🎥 Stage 10 — Remotion Render

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/caption.json` (`scenes`), `project/music/bg_music.mp3` | |
| **also uses** | `project/avatar/*`, `project/broll/*`, `sfx/*` | via `public/` symlinks |
| **produces** | `output/final.mp4` | high-quality composite |

## What it does
Refreshes the `remotion/public/` symlinks (avatar, broll, sfx, bg_music) so the renderer
always sees current media, then runs the `Documentary` composition driven by `caption.json`.

## Run
```bash
python3 stages/10_render/run.py -p /path/to/reels-monster
```
Equivalent to: `cd remotion && bunx remotion render src/index.ts Documentary ../output/final.mp4 --props=<caption.json>`

## Engine
**Remotion** (React + TypeScript) run with **Bun** (`bunx remotion render`). Remotion mixes
voice, SFX and `bg_music.mp3` into the composite — no separate audio-mix step needed.

## Common issues
- **`caption.json not found`** → run Stages 06/07 first.
- **Black top half / missing media** → symlinks stale; this stage rebuilds them, so re-run it.
- **`bunx: command not found`** → install Bun and the `remotion/` deps.

---
name: stage-03-scenes
description: Stage 03 — turn narration segments into a shot plan with a video_prompt per scene.
---

# 🎥 Stage 03 — Scene Planning

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `pre_production.json`, `script.json` (`segments`) | |
| **produces** | `project/scripting/scenes.json` | `{ scenes[{ shot_type, subject, camera, video_prompt }] }` |

`video_prompt` per scene is what Stage 08 (B-roll) sends to the Flow API.

## Run
```bash
python3 stages/03_scenes/run.py -p /path/to/reels-monster
```

## Engine
AI. Prompt placeholders: `{style_bible}`, `{segments}`, `{prev_context}`.

## Rules
- Visuals: dark/low-key, t2v-friendly, no human-actor scenes, no on-frame text. See `docs/Design.md §6`.

## Common issues
- **`missing/empty key 'scenes'`** → re-run.

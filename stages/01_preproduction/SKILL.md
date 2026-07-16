---
name: stage-01-preproduction
description: Stage 01 — turn the chosen topic into a creative brief, research notes, and a style bible.
---

# 🎬 Stage 01 — Pre-Production

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/topic.json` | from Stage 00 |
| **produces** | `project/scripting/pre_production.json` | `{ brief, research, style_bible }` |

`brief` drives later stages: `num_scenes`, `scene_seconds`, `format`, `tone`.

## Run
```bash
python3 stages/01_preproduction/run.py -p /path/to/reels-monster
```

## Engine
AI (`core/ai_client.py`). Prompt: `prompt.md` — placeholders `{topic}`, `{duration}`.

## Common issues
- **`topic.json not found`** → run Stage 00 first.
- **Empty `brief`** → contract check fails; re-run (AI returned bad shape).

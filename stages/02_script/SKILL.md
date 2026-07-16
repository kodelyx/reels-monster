---
name: stage-02-script
description: Stage 02 — write the full Hindi (Devanagari) narration split into scene segments.
---

# ✍️ Stage 02 — Scriptwriting

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/pre_production.json` | needs `brief` |
| **produces** | `project/scripting/script.json` | `{ logline, segments[] }` |

`segments` count = number of scenes for the whole pipeline (avatar/broll/captions all key off it).

## Run
```bash
python3 stages/02_script/run.py -p /path/to/reels-monster
```

## Engine
AI. Prompt placeholders: `{num_scenes}`, `{scene_seconds}`, `{words_per_scene}` (= scene_seconds × 2.5), `{brief}`, `{research}`, `{style_bible}`, `{format}`.

## Rules
- Narration = **Hindi Devanagari** (English loanwords in Devanagari spelling). See `docs/Rules.md` R14.

## Common issues
- **`missing/empty key 'segments'`** → AI output malformed; re-run.

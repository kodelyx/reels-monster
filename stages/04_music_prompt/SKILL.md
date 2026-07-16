---
name: stage-04-music-prompt
description: Stage 04 — write a 60-80 word background-music prompt for Lyria/MusicFX.
---

# 🎵 Stage 04 — Music Prompt

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `pre_production.json`, `script.json` | |
| **produces** | `project/scripting/music_prompt.txt` | plain text, 60-80 words |

Consumed later by Stage 09 (Music) → `bg_music.mp3`.

## Run
```bash
python3 stages/04_music_prompt/run.py -p /path/to/reels-monster
```

## Engine
AI (text, not JSON). Prompt placeholders: `{{topic}}`, `{{tone}}`, `{{audience}}`, `{{visual_style}}`, `{{segments}}`.

## Common issues
- **empty file** → contract `text` check fails; re-run.

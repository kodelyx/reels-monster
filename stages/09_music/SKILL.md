---
name: stage-09-music
description: Stage 09 — generate a background-music track from the music prompt via Gemini (Lyria 3), transcoded to bg_music.mp3.
---

# 🎵 Stage 09 — Background Music

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/music_prompt.txt` | from Stage 04 |
| **produces** | `project/music/bg_music.mp3` | mixed into the render by Remotion |

Also symlinks the track into `remotion/public/bg_music.mp3` so `staticFile()` finds it.

## Run
```bash
python3 stages/09_music/run.py -p /path/to/reels-monster
```

## Engine
**Gemini MCP** (Lyria 3) via `core/mcp.py` → `gemini_generate_music()`, run inside the
`free-gemini-api` docker container. The generated file path is parsed from MCP output,
`docker cp`'d out, then ffmpeg-transcoded to a clean MP3.

## Common issues
- **`music_prompt.txt not found`** → run Stage 04 first.
- **MCP path parse fails** → container returned no `Path: …mp3/.wav` line; check
  `GEMINI_DOCKER_CONTAINER` is running (`docker ps`).
- **No audio in final render** → symlink missing; re-run this stage before Stage 10.

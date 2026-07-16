---
name: stage-00-topic
description: Stage 00 — discover ONE fresh, viral AI/tech topic for the reel, matched to the creator profile and never repeated.
---

# 🎯 Stage 00 — Topic Discovery

## What this does
Web-searches live AI/tech news, picks the single highest-virality topic for the
creator's audience (`profile/profile.json`), and records it so it's never repeated
(`profile/topic_history.json`).

## Contract (handover)
| | File | Notes |
|:--|:--|:--|
| **requires** | `profile/profile.json` | creator niche, audience, virality rules |
| **produces** | `project/topic.json` | `{ topic, hook, why_trending, visuals_suggested, source }` |

Side-effect: appends the chosen topic to `profile/topic_history.json` (survives `project/` wipe).

## Run
```bash
python3 stages/00_topic/run.py -p /path/to/reels-monster
```

## Engine
AI (`core/ai_client.py`) with **web_search** (up to 5 searches). Needs `AI_API_KEY`
in `config.env`; the proxy/endpoint must support the `web_search` tool.

## Prompt
`prompt.md` (this folder) is the manual-fallback reference. The live prompt is built
in `run.py::build_topic_prompt` (fills profile + past topics + today's date).

## Common issues
- **`profile.json not found`** → you're pointing `-p` at the wrong root.
- **Repeats a topic** → check `profile/topic_history.json` is being written.
- **`web_search` errors** → the AI endpoint doesn't support the tool; switch `AI_BASE_URL`.

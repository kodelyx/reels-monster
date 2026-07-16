---
name: stage-07-popups
description: Stage 07 — design story-matched glass icon popups per scene, synced to spoken words, into caption.json.
---

# 🎨 Stage 07 — Popup Designer

## Contract
| | File | Notes |
|:--|:--|:--|
| **requires** | `project/scripting/caption.json` (scenes + pages/tokens) | from Stage 06 |
| **produces** | `project/scripting/caption.json` | each scene gains a `popup` field |

## What it does
Per scene, asks the AI to design 2-4 glass "popup" cards (icon + label) that pop in
exactly when their concept is spoken (`atMs` = token `startMs`). Validates/coerces the
AI output into a safe `PopupConfig` (icons, slots, colors, SFX). Falls back to a generic
popup if a scene has no tokens or the AI call fails — never crashes the pipeline.

## Run
```bash
python3 stages/07_popups/run.py -p /path/to/reels-monster
```

## Engine
AI (`core/ai_client.py`). Prompt + icon/SFX vocab are inline in `run.py` because the
renderer (`PopupAsset.tsx`) only understands specific `CURATED_SVG` / `SFX_KEYS` values.

## Rendered by
`remotion/src/PopupAsset.tsx` (`PopupConfig` in `types.ts`).

## Common issues
- **`caption.json not found`** → run Stage 06 first.
- **Generic popups everywhere** → scenes had no tokens (Stage 06 alignment failed).

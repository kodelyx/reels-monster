# 🐲 Reels-Monster

AI-driven vertical (9:16) reel production pipeline. Ek topic se leke final rendered
video tak — 12 self-contained stages, har ek apne folder me, ek se dusre ko validated
handover ke saath.

> **Split-screen output:** upar cinematic B-roll, neeche talking avatar, beech me
> karaoke-style Hinglish captions + glass-icon popups, background music mixed in.
> Narration Hindi (Devanagari), captions Hinglish (Roman).

---

## 🚀 Quick start

```bash
# 0. Pehli baar? Local AI servers setup karo (binaries build + Chrome extensions):
#    → vendor/README.md padho (ChatGPT :9225 + Gemini :8002, dono self-contained)

# 1. Services live hain? — preflight sab khud boot + verify karta hai:
python3 core/preflight.py

# 2. Poora pipeline chalao:
python3 orchestrator.py

# 3. Beech me ruk gaya? Wahin se resume:
python3 orchestrator.py --resume
```

Final video: `output/final_trimmed.mp4`

> **AI services:** ChatGPT (caption timing) aur Gemini (music) dono bundled native
> binaries hain jo **on-demand khud boot** hote hain — koi Docker nahi. Setup +
> troubleshooting: [`vendor/README.md`](vendor/README.md).

---

## 🧩 Kaise chalta hai (2-layer handover)

Har stage ek subprocess hai (`stages/<name>/run.py`). Orchestrator har stage ke liye:

1. **requires** check (Layer A — `core/contracts.py`): input files present + valid?
2. stage run karo
3. **produces** check: output files present + valid? (warna FAILED, aage nahi badhta)
4. **state** update (Layer B — `core/state.py` → `project/state.json`): resume ke liye

Isliye koi stage kabhi galat input pe nahi chalta, aur toota output kabhi "done"
mark nahi hota.

---

## 🎬 Stages

| # | Stage | Kya banata hai | Engine |
|:--|:--|:--|:--|
| 00 | `topic` | `project/topic.json` | AI |
| 01 | `preproduction` | `pre_production.json` | AI |
| 02 | `script` | `script.json` (segments) | AI |
| 03 | `scenes` | `scenes.json` | AI |
| 04 | `music_prompt` | `music_prompt.txt` | AI |
| 05 | `avatar` | `avatar/scene_N.mp4` | Flow API |
| 06 | `process` | trim + `caption.json` (Hinglish) | Gemini + ChatGPT |
| 07 | `popups` | `caption.json` me popups | AI |
| 08 | `broll` | `broll/scene_N_a/b.mp4` | Flow API |
| 09 | `music` | `music/bg_music.mp3` | Gemini (Lyria 3) |
| 10 | `render` | `output/final.mp4` | Remotion (Bun) |
| 11 | `final_trim` | `output/final_trimmed.mp4` | ffmpeg |

Har stage ka apna `SKILL.md` (contract + run + common issues) us folder me hai.
Stages 00-04 me `prompt.md` bhi (LLM prompt template).

---

## 🕹️ Orchestrator flags

```bash
python3 orchestrator.py                  # saare incomplete stages
python3 orchestrator.py --resume         # jo DONE hain unhe skip
python3 orchestrator.py --from 06_process# yahan se shuru (name ya number: 6 / process)
python3 orchestrator.py --to 04          # yahan tak (sirf text pipeline)
python3 orchestrator.py --only 09_music  # sirf ek stage
python3 orchestrator.py --dry-run        # plan dikhao, chalao mat
python3 orchestrator.py --no-ai          # sirf deterministic checks (AI QC skip)
```

---

## 📁 Layout

```
reels-monster/
├── orchestrator.py      # master runner (yahan se sab chalta hai)
├── cleanup.py           # naya reel shuru karne se pehle state reset
├── config.env           # endpoints + keys (paths NAHI — wo derived hote hain)
├── core/                # shared: config, state, contracts, ai_client, mcp, preflight…
├── stages/00..11/       # har stage: run.py + SKILL.md (+ prompt.md)
├── docs/                # PRD, Architecture, Rules, Phases, Design, Memory
├── project/             # generated state (topic→captions→music, state.json) [gitignore]
├── output/              # rendered videos [gitignore]
├── profile/             # avatar.jpg + creator profile
├── remotion/            # React/TS renderer (public/ me media symlinks)
├── sfx/                 # sound effects
└── _archive/            # purane dead scripts (reference only)
```

## 📚 Docs (yahan se samjho)

- **`docs/Memory.md`** — live progress log. **Naya kaam shuru karne se pehle ye padho.**
- `docs/PRD.md` — kya bana rahe hain, kiske liye
- `docs/Architecture.md` — flow, folder structure, §5 me exact stage contracts
- `docs/Rules.md` — AI boundaries, libraries, error handling
- `docs/Phases.md` — build steps
- `docs/Design.md` — colors/fonts/typography (Remotion visuals)

## ⚙️ Config

`config.env` sirf endpoints + keys rakhta hai (koi filesystem path nahi — sab
`core/config.py` PATHS project-root se derive karta hai, isliye repo kahin bhi move ho
to bina change ke chalti hai):

```
AI_API_KEY=...            AI_BASE_URL=https://cc.freemodel.dev   AI_MODEL=...
FLOW_API_URL=http://localhost:8001
CHATGPT_SERVER_URL=http://localhost:9225
GEMINI_DOCKER_CONTAINER=free-gemini-api
```

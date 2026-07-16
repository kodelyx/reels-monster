# 🏗️ Architecture.md — reels-monster

> App ka flow, folder/file structure, tech stack, aur **har stage ka exact input→output contract**. Ye "kaise bana hai" batata hai. "Kya/kyun" ke liye [PRD.md](./PRD.md).

---

## 1. High-level flow

```
                 ┌──────────────── TEXT PHASE (LLM only) ────────────────┐
  profile.json → 00 topic → 01 preprod → 02 script → 03 scenes → 04 music_prompt
                                                                          │
                 ┌──────────────── MEDIA PHASE (services + render) ───────┘
                 ▼
  05 avatar → 06 process(trim+captions) → 07 popups → 08 broll → 09 music → 10 render → 11 final_trim
                                                                                              │
                                                                                              ▼
                                                                          output/final_trimmed.mp4
```

Har arrow ek **handover** hai: pichla stage ek file likhta hai, agla usko padhta hai. Orchestrator har handover pe **verify** karta hai (file exist + valid?) — tabhi aage badhta hai.

---

## 2. Folder / file structure

```
reels-monster/
├── docs/                      # ye 6 documents (PRD, Architecture, Rules, Phases, Design, Memory)
├── README.md                  # quickstart + pipeline map
├── config.env                 # ⭐ SINGLE source of truth — sab PROJECT_ROOT-relative
├── orchestrator.py            # ⭐ MASTER runner — state.json + contracts se poora pipeline
│
├── core/                      # shared library (har stage yahan se import kare)
│   ├── __init__.py
│   ├── ai_client.py           # LLM calls + multi-key failover      (reel-factory se moved)
│   ├── config.py              # config.env loader (FIXED: relative paths)
│   ├── state.py               # NEW — project/state.json read/write
│   ├── contracts.py           # NEW — har stage ka requires/produces + validate()
│   ├── media_utils.py         # NEW — mp4_ok/ffprobe/n_scenes (auto_media se nikala)
│   └── mcp.py                 # NEW — Flow + Gemini MCP callers (call_*_mcp merged)
│
├── stages/                    # ⭐ har stage = ek self-contained agent
│   ├── 00_topic/          { SKILL.md, run.py, prompt.md }
│   ├── 01_preproduction/  { SKILL.md, run.py, prompt.md }
│   ├── 02_script/         { SKILL.md, run.py, prompt.md }
│   ├── 03_scenes/         { SKILL.md, run.py, prompt.md }
│   ├── 04_music_prompt/   { SKILL.md, run.py, prompt.md }
│   ├── 05_avatar/         { SKILL.md, run.py, generate_talking_avatar.py }
│   ├── 06_process/        { SKILL.md, run.py }        # trim + caption align
│   ├── 07_popups/         { SKILL.md, run.py, prompt.md }
│   ├── 08_broll/          { SKILL.md, run.py }
│   ├── 09_music/          { SKILL.md, run.py }
│   ├── 10_render/         { SKILL.md, run.py }         # remotion invoke
│   └── 11_final_trim/     { SKILL.md, run.py, rapid_edit.py }
│
├── remotion/                  # React video compositor — UNCHANGED (Design.md dekho)
├── profile/                   # creator profile + avatar.jpg + topic_history.json
├── sfx/                       # sound effects library
├── project/                   # ⭐ RUNTIME workspace (git-ignored) — sab outputs + state.json
│   ├── state.json
│   ├── topic.json
│   ├── scripting/  { pre_production.json, script.json, scenes.json, music_prompt.txt, caption.json }
│   ├── avatar/     { scene_N.mp4 }
│   ├── broll/      { scene_N_a.mp4, scene_N_b.mp4 }
│   ├── music/      { bg_music.mp3 }
│   └── intervals/  { scene_N_intervals.json }
│
├── _archive/                  # dead scripts (reference ke liye, DELETE nahi)
└── cleanup.py                 # project/ reset karne ke liye
```

### Consistent stage pattern (yehi "samajhna easy" banata hai)
Har `stages/NN_name/` folder me:
- **`SKILL.md`** — ye agent kya karta hai, input/output contract, kaise chalao, common issues.
- **`run.py`** — sirf isi stage ka code. `-p/--project` arg leta hai, `core.*` import karta hai, exit code se PASS(0)/FAIL(≠0).
- **`prompt.md`** — LLM prompt (agar AI-based stage hai).

Koi bhi stage improve karna = us folder ko kholo, SKILL.md padho, `run.py` badlo. Baaki kuch chhune ki zarurat nahi.

---

## 3. Tech stack
| Layer | Tech |
|:--|:--|
| Orchestration / stages | **Python 3** (stdlib + `httpx`/`requests`, `anthropic`) |
| LLM | Claude proxy via `AI_BASE_URL` (`ai_client.py`, multi-key failover) |
| Avatar + B-roll video | **Flow API** (local `http://localhost:8001`) |
| Music | **Gemini MCP** (Lyria) via `docker exec free-gemini-api` |
| Caption alignment | Local **ChatGPT server** (`http://localhost:9225`) |
| Video compositing | **Remotion** (React + TypeScript) run via **Bun** |
| Media processing | **ffmpeg / ffprobe** |

---

## 4. Handover model (dono layer — jaisa PRD me tay hua)

### Layer A — Per-stage JSON contract (`core/contracts.py`)
Har stage ka ek entry:
```python
"03_scenes": Contract(
    requires=[File("project/scripting/pre_production.json", kind="json"),
              File("project/scripting/script.json", kind="json", must_have=["segments"])],
    produces=[File("project/scripting/scenes.json", kind="json", must_have=["scenes"])],
)
```
- Stage chalne se **pehle**: saare `requires` maujood + valid? nahi → FAIL (agla stage kabhi galat input pe nahi chalega).
- Stage chalne ke **baad**: saare `produces` bane + valid? nahi → FAIL.

### Layer B — Master state (`core/state.py` → `project/state.json`)
```json
{
  "project": "openai-gpt6-leak",
  "updated": "2026-07-15T12:30:00",
  "stages": {
    "00_topic":       { "status": "done",    "output": "project/topic.json", "at": "..." },
    "01_preproduction":{ "status": "done",   "output": "...", "at": "..." },
    "02_script":      { "status": "failed",  "error": "AI returned no segments", "at": "..." },
    "03_scenes":      { "status": "pending" }
  }
}
```
- Orchestrator isse janta hai kaun done hai, kahan se resume karna hai.
- `--resume` = pehle non-done stage se; `--from N` / `--only N` = manual.

---

## 5. ⭐ Per-stage contracts (exact input → output)

> Saare paths `PROJECT_ROOT`-relative. Ye tables hi asli handover spec hain.

| Stage | Requires (input) | Produces (output) | Engine |
|:--|:--|:--|:--|
| **00 topic** | `profile/profile.json`, `profile/topic_history.json` | `project/topic.json` `{topic,hook,why_trending,visuals_suggested,source}` + history append | AI + web_search |
| **01 preproduction** | `project/topic.json` | `project/scripting/pre_production.json` `{brief,research,style_bible}` | AI |
| **02 script** | `pre_production.json` (`brief`) | `project/scripting/script.json` `{logline,segments[]}` | AI |
| **03 scenes** | `pre_production.json`, `script.json` (`segments`) | `project/scripting/scenes.json` `{scenes[{video_prompt,...}]}` | AI |
| **04 music_prompt** | `pre_production.json`, `script.json` | `project/scripting/music_prompt.txt` (60-80 words) | AI |
| **05 avatar** | `script.json` (`segments`), `profile/avatar.jpg` | `project/avatar/scene_N.mp4` (N = #segments) | Flow API |
| **06 process** | `project/avatar/scene_N.mp4`, `script.json` | trimmed `scene_N.mp4` + `project/scripting/caption.json` (`scenes`,`pages`) + `project/intervals/*` | ChatGPT + ffmpeg |
| **07 popups** | `caption.json` (narration+tokens) | `caption.json` me har scene ka `popup` field | AI |
| **08 broll** | `scenes.json` (`video_prompt`) | `project/broll/scene_N_a.mp4`, `scene_N_b.mp4` | Flow API |
| **09 music** | `music_prompt.txt` | `project/music/bg_music.mp3` | Gemini MCP |
| **10 render** | `caption.json`, `avatar/*`, `broll/*`, `music/bg_music.mp3` | `output/final.mp4` | Remotion/Bun |
| **11 final_trim** | `output/final.mp4`, `project/*_intervals_config_final.json` | `output/final_trimmed.mp4` | ffmpeg (rapid_edit) |

### Critical shared file: `caption.json`
- **Path**: `project/scripting/caption.json` (config `REMOTION_CAPTION_JSON_PATH`).
- Likhta hai: **06 process** (base: scenes + pages), 07 popups (adds `popup`).
- Padhta hai: **10 render** (Remotion `--props`). Symlink `remotion/props/caption.json` → yahi.
- Schema: `remotion/src/types.ts` (`DocumentaryProps`, `CaptionPage`, `SceneClip`, `PopupConfig`).

### Symlink contract (Remotion `public/` fresh media uthaye)
- `remotion/public/avatar` → `project/avatar`
- `remotion/public/broll` → `project/broll`
- `remotion/public/bg_music.mp3` → `project/music/bg_music.mp3`
- `remotion/public/sfx` → `sfx`

---

## 6. Config resolution (P1 fix)
`core/config.py` `PROJECT_ROOT = config.env ka parent`. Saare paths us se derive honge:
```python
AVATAR_DIR   = PROJECT_ROOT / "project" / "avatar"
SCRIPT_JSON  = PROJECT_ROOT / "project" / "scripting" / "script.json"
# koi bhi "/Users/akash/..." absolute path nahi
```
`config.env` me sirf **service endpoints + tunables** (URLs, model names, API keys) — paths nahi.

---

## 7. Data flow ki ek line me summary
`profile.json` → *(AI text phase)* → `scripting/*.json` → *(media phase Flow/Gemini/ChatGPT)* → `avatar/ broll/ music/ caption.json` → *(Remotion)* → `output/final.mp4` → *(ffmpeg)* → `output/final_trimmed.mp4`. **State** har step pe `project/state.json` me, **verify** har step pe `contracts.py` se.

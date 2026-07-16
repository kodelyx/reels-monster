# 📄 PRD.md — reels-monster

> **Project Requirements Document.** Kya bana rahe hain, kiske liye, aur kaunse features chahiye. Ye "kyun/kya" batata hai — "kaise" ke liye [Architecture.md](./Architecture.md) dekho.

---

## 1. One-liner
`reels-monster` ek **automated AI video production pipeline** hai jo ek trending AI/tech topic se lekar **final edited Hindi reel** (9:16, split-screen: upar B-roll, neeche talking avatar, karaoke captions, background music, icon popups) tak sab kuch khud banata hai.

Ye maujooda `reel-factory` codebase ka **reorganized (stage/agent-based) version** hai — same features, par aisa structure jisme:
- har kaam ka **apna folder + skill + code** ho,
- ek stage agle stage ko **validated handover** kare,
- codebase samajhna aur improve karna **easy** ho.

---

## 2. Problem statement (kyun reorganize kar rahe hain)
Maujooda `reel-factory` kaam karta hai par maintain karna mushkil hai:

| # | Problem | Asar |
|:--|:--|:--|
| P1 | **Hardcoded absolute paths 3 jagah 3 alag** (`config.env` me `/Reels-Agent/`, `SKILL.md` me `/My-work/`, actual `/Reels-hub/`) | Kuch bhi move karo to pipeline toot-ta hai |
| P2 | **Do alag orchestrators** (`pipeline.py` = text steps, `auto_media.py` = media steps), koi single master nahi | Handover manual, resume/verify aadha-aadha |
| P3 | **~11 dead scripts** (`fix_captions`, `compile_captions`, `polish_captions`, `trim_avatar_only`, `analyze_silence`, `sound_manager`, `trim_and_align_avatar`, `normalize_avatar_audio`, `fix_caption_merges`, `call_flow_mcp`, `call_gemini_mcp`) | Confusion — kaunsa asli hai pata nahi chalta |
| P4 | Stage boundaries dhundhle — ek script kai kaam karta hai (jaise `process_avatar` = trim + caption) | Ek cheez badlo to doosri toot-ne ka dar |

---

## 3. Target users
| User | Kaun | Zarurat |
|:--|:--|:--|
| **Creator (Akash)** | Content banane wala, non-deep-tech | Ek command chalao → final reel mile. Har baar 100% chale. |
| **Maintainer (Akash + AI agent)** | Codebase improve karne wala | Kisi ek stage ko kholo, uska contract dekho, sirf wahi badlo — baaki na toote |
| **AI agent (Claude)** | Naye chat me kaam continue karne wala | Docs + Memory.md se turant context mile, pura codebase dobara padhna na pade |

---

## 4. Goals & non-goals

### ✅ Goals
- G1 — **Feature parity**: jo `reel-factory` aaj karta hai, sab kuch same chale (koi regression nahi).
- G2 — **Stage/agent structure**: har stage self-contained (folder + SKILL.md + run.py + prompt).
- G3 — **Validated handover**: har stage input verify kare, output verify kare — galat data aage na jaaye (→ "100% accuracy").
- G4 — **Single source of truth**: ek `config.env`, project-relative paths, koi hardcoded absolute path nahi.
- G5 — **Ek master orchestrator**: poora pipeline ek command se, resume/only/from support, state-driven.
- G6 — **Easy to understand & improve**: consistent folder pattern + docs + Memory.md.

### ❌ Non-goals (abhi ke liye nahi)
- Remotion React compositor ko rewrite karna (jaisa hai waisa rahega).
- Naye creative features (naye video styles, naye platforms) add karna.
- External services (Flow API, Gemini MCP, ChatGPT server) ki auth/setup badalna.
- Purana `reel-factory/` delete karna (verify hone tak side-by-side rahega).

---

## 5. Features (functional requirements)

Pipeline = **12 stages**, do phase me:

### 🅰️ Text phase (LLM-driven — sirf `AI_API_KEY` chahiye)
| Stage | Feature | Output |
|:--|:--|:--|
| 00 topic | Trending AI/tech topic khud dhoondhe (web search, profile-matched, repeat nahi) | `project/topic.json` |
| 01 preproduction | Topic → brief + research + style bible | `project/scripting/pre_production.json` |
| 02 script | Hindi narration script (segments) | `project/scripting/script.json` |
| 03 scenes | Shot plan + per-scene `video_prompt` | `project/scripting/scenes.json` |
| 04 music_prompt | 60-80 word music prompt | `project/scripting/music_prompt.txt` |

### 🅱️ Media phase (external services + render)
| Stage | Feature | Output |
|:--|:--|:--|
| 05 avatar | Talking avatar clips (Flow API) | `project/avatar/scene_N.mp4` |
| 06 process | Silence trim + word-level caption align | `scene_N` trimmed + `project/scripting/caption.json` |
| 07 popups | Story-matched glass icon popups per scene | `caption.json` me `popup` field |
| 08 broll | Top-screen B-roll clips (Flow API) | `project/broll/scene_N_a.mp4`, `_b.mp4` |
| 09 music | Background track (Gemini MCP / Lyria) | `project/music/bg_music.mp3` |
| 10 render | Remotion split-screen composite | `output/final.mp4` |
| 11 final_trim | Final silence trim | `output/final_trimmed.mp4` |

> Har stage ka **exact input→output contract** [Architecture.md §5](./Architecture.md) me hai.

### Cross-cutting features
- **F1 Preflight**: media phase se pehle saari services + Flow credits check.
- **F2 State tracking**: `project/state.json` — har stage ka status/output/timestamp.
- **F3 Handover verification**: har stage ke baad deterministic + (optional) AI check.
- **F4 Resume**: `--from`, `--only`, `--resume` state.json se.
- **F5 Cleanup/reset**: `project/*` khaali karke naya video shuru.

---

## 6. Success criteria (kaise pata chale ho gaya)
- ✅ `python3 orchestrator.py --project . --dry-run` — poora wiring bina error verify ho.
- ✅ Ek topic se end-to-end run → `output/final_trimmed.mp4` bane, `reel-factory` ke barabar quality.
- ✅ Koi hardcoded absolute path na ho — folder rename karke bhi chale.
- ✅ Koi bhi stage ka folder kholke, uski SKILL.md padhke, akele us stage ko `--only` se chala/test kar sako.
- ✅ Naye chat me `Memory.md` padhke agent turant continue kar sake.

---

## 7. Related docs
- [Architecture.md](./Architecture.md) — flow, folder structure, tech stack, per-stage contracts
- [Rules.md](./Rules.md) — AI/dev ke liye boundaries (kya karein, kya nahi)
- [Phases.md](./Phases.md) — build steps (kis order me banega)
- [Design.md](./Design.md) — visual system (colors, fonts, layout)
- [Memory.md](./Memory.md) — live progress log (build ke saath update hota hai)

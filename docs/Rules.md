# 📏 Rules.md — reels-monster

> AI agent aur developer dono ke liye boundaries. Code likhne/badalne se pehle ye padho. Ye rules [Architecture.md](./Architecture.md) ko enforce karte hain.

---

## 1. Golden rules (kabhi na todo)
- **R1 — Feature parity sacred hai.** Migration ka matlab hai *move + rewire*, *rewrite nahi*. Kisi stage ka logic bina wajah na badlo. Behavior wahi rahe jo `reel-factory` me tha.
- **R2 — Koi hardcoded absolute path nahi.** Har path `PROJECT_ROOT` se derive ho (`core/config.py`). `/Users/akash/...` code me kahin na aaye.
- **R3 — Handover verify kiye bina aage nahi.** Har stage input `requires` check kare, output `produces` check kare. Fail → rukho, saaf error do, next stage mat chalao.
- **R4 — Purana `reel-factory/` mat chhedo** jab tak `reels-monster` end-to-end verify na ho. Side-by-side rahega.
- **R5 — Dead code migrate karo ya delete karo.** Useful logic proper stage me port karo, baaki delete. Archive folder mat rakho — reference ki zarurat nahi jab sab migrated ho.

---

## 2. Code structure rules
- **R6** — Shared logic sirf `core/` me. Stage ka `run.py` `core.*` import kare, kisi doosre stage se import na kare (stages ek-doosre pe depend na karein — sirf files ke through handover).
- **R7** — Har `run.py` ka ek hi standard shape: `-p/--project` arg leta hai, kaam karta hai, success pe exit 0, fail pe non-zero + stderr pe `❌` reason.
- **R8** — Har stage ke output sirf `project/` ke andar likho. Root directory hamesha saaf rahe. (Isse `cleanup.py` se reset easy.)
- **R9** — Naya stage add karna = naya `stages/NN_name/` folder (SKILL.md + run.py) + `core/contracts.py` me ek entry + orchestrator ki order list me naam. Bas.

---

## 3. Libraries — use / avoid
| Use ✅ | Avoid ❌ |
|:--|:--|
| Python **stdlib** (json, pathlib, subprocess, argparse) | Bade frameworks (Django/Flask) — ye CLI pipeline hai |
| `httpx` / `requests` (jo already use ho raha) | Naye HTTP libs mat mix karo |
| `anthropic` via `core/ai_client.py` | LLM ko direct kahin aur se call mat karo — hamesha `ai_client` |
| `ffmpeg`/`ffprobe` subprocess | Python video libs (moviepy etc.) — pipeline ffmpeg pe khadi hai |
| Remotion + Bun (jaise hai) | Remotion ko kisi aur renderer se replace mat karo |

---

## 4. Error handling
- **R10** — External call (Flow/Gemini/ChatGPT/LLM) fail ho sakta hai → retry with failover jahan pehle se hai (jaise `ai_client` multi-key, avatar 3-attempt). Naya code bhi yahi pattern rakhe.
- **R11** — Fail hone pe **state.json me `status:"failed"` + `error`** likho, phir non-zero exit. Silent fail bilkul nahi (P4/G3 ke against).
- **R12** — Har verify failure ka message **actionable** ho: kaunsi file missing/invalid, kaunsa stage pehle chalana hai.
- **R13** — Destructive kaam (`cleanup.py`, `_archive` move) hamesha explicit flag (`--clean`) ya confirm ke peeche.

---

## 5. AI-stage rules (LLM prompts)
- **R14** — Narration hamesha **Hindi Devanagari** (English loanwords Devanagari spelling me). Baaki JSON fields English.
- **R15** — Prompt files `stages/NN/prompt.md` me rahein, code me hardcode nahi. Placeholders `{key}`/`{{key}}` `ai_client`/orchestrator bhare.
- **R16** — LLM se JSON expect karte waqt `expect_json=True` + validate; kabhi bharosa mat karo ki AI ne sahi shape diya — `contracts.py` se check.
- **R17** — Visual/creative hard-rules (dark/low-key lighting, no text/logo in frames, t2v default, max 4 parallel gen) [Design.md](./Design.md) me — un se deviate mat karo.
- **R18** — Stage 06 me avatar audio **-14 LUFS normalize** hota hai (consistent loudness) aur **phonetic merge rules** apply hote hain (ए+आई→AI, चैट+जीपीटी→ChatGPT). Naye merge patterns zarurat ke hisaab se `MERGE_RULES` list me add karo.
- **R19** — Stage 07 me SFX selection **AI-driven** hai — `sfx/` folder runtime pe scan hota hai, har file ka mood detect hota hai, AI narration/popup ke context se pick karta hai. Naye sounds chahiye to `stages/07_popups/sound_manager.py` chalao.

---

## 6. Do / Don't (quick)
| Do ✅ | Don't ❌ |
|:--|:--|
| Ek stage `--only NN` se akele test karo | Poora pipeline chala ke ek stage debug mat karo |
| Naye chat me pehle `Memory.md` padho | Bina context padhe code likhna shuru mat karo |
| Path change → sirf `config.env` / `core/config.py` | Path stage ke andar hardcode mat karo |
| Contract pehle likho, phir stage | Stage bana ke contract baad me "kabhi" — nahi |

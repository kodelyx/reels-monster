# 🪜 Phases.md — reels-monster

> Project ko chhote manageable steps me toda gaya hai (AI sab ek saath nahi bana sakta). Har phase ke **baad verify**, tabhi agla. Progress [Memory.md](./Memory.md) me update hoti hai.

> **Rule:** ek phase khatam = uska "✅ Done when" satisfy + Memory.md update + Akash ka OK → tabhi next.

---

## Phase 0 — Documentation ✅
Spec-driven docs likhna taaki baaki sab isi ke against bane.
- [x] `PRD.md` — kya/kyun/kaun/features
- [x] `Architecture.md` — flow + folder + per-stage contracts
- [x] `Rules.md` — boundaries
- [x] `Phases.md` — ye file
- [x] `Design.md` — visual system
- [x] `Memory.md` — live update

---

## Phase 1 — Scaffold + `core/` ✅
Foundation. Koi stage logic nahi — sirf shared library + fixed config.
- [x] `reels-monster/` skeleton (folders per Architecture §2)
- [x] `core/config.py` — `config.env` loader, **PROJECT_ROOT-relative** (P1 fix, R2)
- [x] `core/ai_client.py` — reel-factory se move (as-is)
- [x] `core/state.py` — state.json read/write, `mark(stage, status, **info)`
- [x] `core/contracts.py` — `Contract`/`File` + har stage ka requires/produces + `validate()`
- [x] `core/media_utils.py` — `mp4_ok`, `n_scenes` (auto_media se nikala)
- [x] `core/mcp.py` — Flow + Gemini callers merge
- [x] `config.env` — sirf endpoints/keys, no paths

---

## Phase 2 — Stages migrate (12 stages) ✅
Har existing script → uska stage folder. **Logic same, sirf move + rewire imports + SKILL.md.**
- [x] Batch A (text): 00 topic, 01 preproduction, 02 script, 03 scenes, 04 music_prompt
- [x] Batch B (media): 05 avatar (+generate_talking_avatar), 06 process, 07 popups
- [x] Batch C (finish): 08 broll, 09 music, 10 render, 11 final_trim
- [x] Har stage ka `SKILL.md` (contract + how-to-run + issues)

---

## Phase 3 — Orchestrator ✅
`pipeline.py` + `auto_media.py` ki functionality ek master me.
- [x] `orchestrator.py` — stages order list, state.json load
- [x] Har stage: `contracts.validate(requires)` → `run.py` → `contracts.validate(produces)` → `state.mark`
- [x] Flags: `--from N`, `--only N`, `--resume`, `--dry-run`, `--no-ai`
- [x] Preflight integrate (media phase se pehle services/credits check)

---

## Phase 4 — Dead code cleanup ✅
- [x] Useful logic stages me port kiya (normalize_audio → 06, merge_rules → 06, sound_manager → 07)
- [x] `_archive/` folder pura delete — sab migrated
- [x] Confirm koi live stage old scripts pe depend nahi karta

---

## Phase 5 — Docs finalize + smoke test ✅
- [x] Root `README.md` — quickstart + pipeline map
- [x] `cleanup.py` port
- [x] End-to-end media run (stages 00→08 real output verified)
- [x] Stages 09/10/11 code-verified (user terminal pe run)

---

## Phase 6 — Post-migration enhancements ✅
- [x] Self-contained native services (Gemini/ChatGPT Go binaries, Flow uv-based)
- [x] Stage 06: audio loudness normalize (-14 LUFS) + phonetic merge rules (ए+आई→AI)
- [x] Stage 07: dynamic SFX scanning from `sfx/` + AI-driven context-aware sound selection
- [x] `stages/07_popups/sound_manager.py` — MyInstants SFX downloader utility
- [x] Repo push-prep (secrets gitignored, config.env.example, binaries excluded)

---

## Phase order rationale
Docs → foundation → stages → orchestrator → cleanup → verify → enhance. Har phase pichle pe khadi hai; koi phase skip nahi. Risky cheezein (real generation) sabse aakhir me, jab wiring already verified ho.


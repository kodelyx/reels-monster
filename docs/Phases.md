# 🪜 Phases.md — reels-monster

> Project ko chhote manageable steps me toda gaya hai (AI sab ek saath nahi bana sakta). Har phase ke **baad verify**, tabhi agla. Progress [Memory.md](./Memory.md) me update hoti hai.

> **Rule:** ek phase khatam = uska "✅ Done when" satisfy + Memory.md update + Akash ka OK → tabhi next.

---

## Phase 0 — Documentation ✅ (abhi)
Spec-driven docs likhna taaki baaki sab isi ke against bane.
- [x] `PRD.md` — kya/kyun/kaun/features
- [x] `Architecture.md` — flow + folder + per-stage contracts
- [x] `Rules.md` — boundaries
- [x] `Phases.md` — ye file
- [x] `Design.md` — visual system
- [ ] `Memory.md` — Phase 1 se live update shuru

**✅ Done when:** Akash docs review karke OK de.

---

## Phase 1 — Scaffold + `core/`
Foundation. Koi stage logic nahi — sirf shared library + fixed config.
- [ ] `reels-monster/` skeleton (folders per Architecture §2)
- [ ] `core/config.py` — `config.env` loader, **PROJECT_ROOT-relative** (P1 fix, R2)
- [ ] `core/ai_client.py` — reel-factory se move (as-is)
- [ ] `core/state.py` — NEW: state.json read/write, `mark(stage, status, **info)`
- [ ] `core/contracts.py` — NEW: `Contract`/`File` + har stage ka requires/produces + `validate()`
- [ ] `core/media_utils.py` — NEW: `mp4_ok`, `n_scenes` (auto_media se nikala)
- [ ] `core/mcp.py` — NEW: Flow + Gemini callers merge
- [ ] `config.env` — sirf endpoints/keys, no paths

**✅ Done when:** `python3 -c "from core import config, state, contracts"` bina error import ho; `core/config.py` koi absolute path na de.

---

## Phase 2 — Stages migrate (12 stages)
Har existing script → uska stage folder. **Logic same, sirf move + rewire imports + SKILL.md.**
Order (batch me, verify karte hue):
- [ ] Batch A (text): 00 topic, 01 preproduction, 02 script, 03 scenes, 04 music_prompt
- [ ] Batch B (media): 05 avatar (+generate_talking_avatar), 06 process, 07 popups
- [ ] Batch C (finish): 08 broll, 09 music, 10 render, 11 final_trim
- [ ] Har stage ka `SKILL.md` (contract + how-to-run + issues)

**✅ Done when:** har stage `python3 stages/NN/run.py -p . --help` chale; imports `core.*` resolve ho; koi cross-stage import nahi.

---

## Phase 3 — Orchestrator
`pipeline.py` + `auto_media.py` ki functionality ek master me.
- [ ] `orchestrator.py` — stages order list, state.json load
- [ ] Har stage: `contracts.validate(requires)` → `run.py` → `contracts.validate(produces)` → `state.mark`
- [ ] Flags: `--from N`, `--only N`, `--resume`, `--dry-run`, `--no-ai`
- [ ] Preflight integrate (media phase se pehle services/credits check)

**✅ Done when:** `--dry-run` poora graph verify kare bina kuch generate kiye; ek fail stage pe rukke saaf error de.

---

## Phase 4 — Dead code archive
- [ ] 11 unused scripts `_archive/` me move
- [ ] `_archive/README.md` — kaunsa kya tha, kyun archive
- [ ] Confirm koi live stage inpe depend nahi karta

**✅ Done when:** `grep -r` se koi live reference na mile; pipeline phir bhi chale.

---

## Phase 5 — Docs finalize + smoke test
- [ ] Root `README.md` — quickstart + pipeline map
- [ ] `.agents/skills/reel-factory/SKILL.md` — naye structure ke hisaab se update (ya naya `reels-monster` skill)
- [ ] `cleanup.py` port
- [ ] **Smoke test**: `--dry-run` green; ho sake to ek chhota real run

**✅ Done when:** naye chat me sirf docs se agent pura flow chala paaye; end-to-end ek reel bane.

---

## Phase order rationale
Docs → foundation → stages → orchestrator → cleanup → verify. Har phase pichle pe khadi hai; koi phase skip nahi. Risky cheezein (real generation) sabse aakhir me, jab wiring already verified ho.

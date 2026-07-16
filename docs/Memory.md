# 🧠 Memory.md — reels-monster (live progress log)

> **Ye file har chat/tool switch pe pehle padho.** Isse pata chalta hai ab tak kya hua, kahan ho, aage kya. Bina isko padhe code mat likho (poora codebase dobara padhne me token waste hote hain).
>
> **Update kab karo:** har phase/stage khatam hone pe. Naya entry sabse upar "Current state" me, aur "Log" me ek line.

---

## 📍 Current state
- **Active phase:** Structure ✅ complete. **END-TO-END MEDIA TEST (2026-07-15) — stages 00→08 REAL output ban gaya, 09/10/11 code-verified.** Topic "China AI-companion ban", 5 scenes.
- **✅ Stages jo maine ACTUALLY chalaye (real output verified):**
  - `00-04` (text): topic/pre_production/script/scenes/music_prompt sab bane. QC ab plausibility-aware.
  - `05_avatar`: **5/5 real Flow clips** (1280x720, 8s). Retry logic verified (scene 1 do baar Flow HTTP-500 se fail → teesri baar success).
  - `06_process`: **5/5 trimmed + caption.json complete** (5 scenes, 5 pages, plausible 5-6.4s durations, tokens+broll refs).
  - `07_popups`: **5/5 scenes × 3 cards + 3 sfx**. **Failover verified** — Claude proxy unreachable (mera sandbox) → auto-fallback local ChatGPT → real popups bane.
  - `08_broll`: **10/10 real Flow clips** (5 scenes × a/b, 1280x720, 4s), Semaphore(4) parallel.
- **🐛 3 REAL BUGS mile aur FIX hue (ye future me bhi aate):**
  1. **`core/rapid_edit.py` videotoolbox no-fallback** — hardware encoder fail hote hi ffmpeg exit 187, poora 06/11 toot jaata tha. **Fix:** encoder chain (videotoolbox/nvenc → libx264 software fallback) + empty-output detection (exit 0 par 0-byte file bhi failure). Verified: fallback trigger hua, clip clean bana.
  2. **`06_process` partial caption.json** — koi scene fail ho to bhi adhura caption.json likh deta tha (missing scenes), render silently gap se toot-ta. **Fix:** `failed_scenes` track + fail-fast `sys.exit(1)` before compile — adhura output kabhi nahi likhta.
  3. **`06_process` ChatGPT bad alignment** — kabhi galat word-timing deta (16 words → 1.4s), rapid_edit clip ko wahi galat span pe kaat deta (narration cut). **Fix:** plausibility guard (`span >= 0.20s/word` + `len(words) >= 0.6×expected`), warna retry. Verified: retry ke baad sab 5-6.4s sane.
  4. (pehle fix hua) **`orchestrator.py` QC dummy-facts + scene-count bias** — `collect_facts()` ab real file facts collect karta, `expected_scenes` sirf per-scene stages (avatar/broll) me; music_prompt/script/scenes single-file, QC ab per-scene structure nahi maangta.
- **⏳ Stages jo MERE SANDBOX se blocked (code verified, USER ke terminal pe run pending):**
  - `09_music`: Gemini Lyria docker (`docker exec` — socket permission denied mere shell me). Config getters + paths sab resolve ✅.
  - `10_render`: Remotion/Bun. **`bun install` mere yahan fail — npm registry 403 (sandbox network whitelist)**. Par: caption.json **DocumentaryProps type se 100% match** ✅, ensure_symlinks sab links sahi resolve ✅, saari avatar/broll media refs disk pe exist ✅.
  - `11_final_trim`: default no-op copy (final→final_trimmed), warna fixed rapid_edit.
- **▶️ USER ko ab ye chalana hai:** `python3 orchestrator.py --from 09_music` (ya `--resume`) — 09 music → 10 render → 11 trim. Sab upstream media (avatar/broll/caption) ready hai. Output: `output/final_trimmed.mp4`.
- **Note:** `sfx/` empty (placeholder). Mere sandbox me `ps`/`pkill`/`pgrep` "sysmond service not found" se blocked — background jobs manage nahi kar sakta, isliye media stages FOREGROUND single-run se test kiye (overlapping bg runs state corrupt karte the). Docker socket + npm registry + Claude proxy sab mere shell se blocked; Flow API + local ChatGPT reachable.


## 🗂️ Where things are
- New project root: `/Users/akash/Reels-hub/reels-monster/`
- Docs: `reels-monster/docs/{PRD,Architecture,Rules,Phases,Design,Memory}.md`
- Old project (DO NOT TOUCH yet): `/Users/akash/Reels-hub/reel-factory/`
- Existing skills: `/Users/akash/Reels-hub/.agents/skills/`

## 🎯 Key decisions (locked)
1. Full refactor → **stage/agent** structure (12 stages, har ek self-contained folder).
2. Handover = **dono**: per-stage JSON contract (`core/contracts.py`) + master `project/state.json` (`core/state.py`).
3. New folder **`reels-monster/`**, side-by-side (old `reel-factory` verify hone tak safe).
4. **Feature parity** — migration = move + rewire, NO logic rewrite.
5. Docs = spec-driven 6-file set (PRD/Architecture/Rules/Phases/Design/Memory).

## ⚠️ Gotchas found (during exploration)
- Hardcoded paths **3 jagah 3 alag** (`/Reels-Agent/`, `/My-work/`, actual `/Reels-hub/`) → Phase 1 me `core/config.py` PROJECT_ROOT-relative se fix.
- Do orchestrators: `pipeline.py` (text 1-4) + `auto_media.py` (media, has verify logic) → Phase 3 me merge.
- `caption.json` = sabse critical shared file (`project/scripting/caption.json`), 06 process likhta, 07 popups edit, 10 render padhta.
- Dead scripts (~11) confirmed 0 references: `fix_captions, fix_caption_merges, compile_captions, polish_captions, trim_avatar_only, trim_and_align_avatar, normalize_avatar_audio, analyze_silence, sound_manager, call_flow_mcp, call_gemini_mcp` → Phase 4 archive.
- Remotion (`remotion/src/*`) UNCHANGED — Design.md isko document karta hai.

## 📝 Log
- **2026-07-15** — Gemini FULLY self-contained + VIDEO COMPLETE. (a) Gemini server binary bundle kiya `reels-monster/vendor/gemini/gemini-server` — ab alag `free-gemini-api` checkout pe dependency khatam. (b) `core/gemini_server.py` naya: `ensure_server()` on-demand binary boot (cwd `vendor/gemini/`, reads `cookies.json`, writes `output/`), `generate_music()`/`chat()` direct HTTP (MCP + docker DROP), `warmup()` start me ek baar boot+cookie verify. (c) Gemini 2 jagah use hota — music (09) + AI chat fallback (`ai_client._call_gemini`); DONO ab bundled server pe (dono ke liye ek session, cookies ~15min valid to ek warmup kaafi). (d) `check_gemini` preflight ab warmup karta hai (orchestrator start pe cookies aa jaati). (e) Folder saaf: sirf `gemini-server` + `cookies.json` + `output/` — data/ wrapper aur assets/ (cosmetic png) kachra hataya. config.env se legacy `GEMINI_MCP_BIN/DOCKER/MCP_PATH` hataye, sirf `GEMINI_MUSIC_URL` + auto-derived `GEMINI_SERVER_BIN/DIR`. (f) Cookie expiry: extension `sessionKeepAlive` 15→**12 min** (3-min safety buffer, expiry se pehle rotate) + server ka reactive auto-heal (`executeWithRetry`: fail→trigger_sync→5s→reload→retry) baraqaraar. VERIFIED live: external server kill → `09_music` pe bundled binary **khud boot** (PID→vendor/gemini/gemini-server), extension cookies push, real track "khamosh safar" bana, re-render → `output/final.mp4` (24MB, 30.6s, 1080×1920, aac -21.9dB real music). Manual server-start ki need NAHI — on-demand.
- **2026-07-15** — BUG 9 (09 galat music URL) FIXED. Track ke 2 URL aate: `local_path` (=`/output/` served, SAHI) aur `download_url` (Google raw, host re-serve nahi kar sakta → 404). `09` galat wala utha raha tha → 404. Fix: `pick_track_url()` ab `music[].local_path` prefer karta hai, host ko `GEMINI_MUSIC_URL` pe re-root. (BUG 8/7 ke saath ye teesra render-blocker tha.)
- **2026-07-15** — BUG 8 (10_render sfx 404) found & FIXED. bg_music fix ke baad render 22/917 frames tk gaya phir `public/sfx/popular-riser.mp3 → 404`. Root cause: `sfx/` folder khaali tha (sirf README) — original popup sound-effects reels-monster me kabhi copy nahi hue, aur poore Reels-hub tree me kahin nahi (reel-factory me bhi 0). `remotion/src/PopupAsset.tsx` 13 sfx mp3s reference karta hai; caption.json 6 use karta (alert/boom/ding/rise/shineAnime/swoosh). Fix (silent-fallback philosophy, jaisa music bed): saare 13 ke silent 1s placeholder mp3 `ffmpeg anullsrc` se `sfx/` me bana diye + `sfx/_PLACEHOLDER.txt`. Popups visually render honge, sirf sfx silent. `public/sfx` dir-symlink hai (Remotion follow karta hai — avatar/broll proved). Real sfx chahiye to same filenames se `sfx/` me daal do.
- **2026-07-15** — BUG 7 (10_render bg_music 404) found & FIXED. User run pe render bundling+frames tk pahunch gaya par encoding pe `http://localhost:3000/public/bg_music.mp3 → 404` + `MediaError`. Root cause: Remotion dev server symlinked **directories** (avatar/broll/sfx) to serve karta hai par symlinked **file** ko nahi — `public/bg_music.mp3` symlink tha → 404. Fix: bg_music ab **real copy** (`shutil.copyfile`) hoti hai symlink ke bajaye — dono jagah: `09_music/_link_public()` (writer) aur `10_render/ensure_symlinks()` (render se pehle re-copy). Baaki (avatar/broll/sfx) dir-symlink hi rahenge (wo chalte hain), caption `--props` se real path pe jaata hai. Verified: current `public/bg_music.mp3` = 239KB real ID3 mp3 (symlink nahi); mere sandbox se render bundling 91% tak pahuncha (sirf Chrome launch OS-block `mach_port 1100` se ruka — code bug nahi, user machine pe Chrome chalta hai).
- **2026-07-15** — DOCKER HATAYA (Gemini) → NATIVE Go binary. User: "docker ka khel kachra khatam ho". `free-gemini-api` ko `go build` kiya (GOCACHE project-local, sandbox `~/Library/Caches` blocked) → `main` (HTTP server) + `gemini-mcp-bin` (MCP), dono Mach-O arm64. Native server boot verified (Fiber up, WS bridge up), native MCP→server JSON-RPC round-trip verified (`generate_music` execute hua; sirf cookies-missing kyunki fresh test instance). reels-monster rewired: `config.env` me `GEMINI_MCP_BIN` (native binary path); `core/config.gemini_mcp_bin()`; `core/mcp.gemini_cmd()` native-first (docker fallback) + `_gemini_env()` `GEMINI_API_URL` set karta; `core/preflight.check_gemini()` native mode me sirf HTTP `:8002/` check karta (docker ps nahi). Start script: `free-gemini-api/start-native.sh` (PORT 8002 + WS 9226). Preflight verified: down→fail, live→pass.
- **2026-07-15** — 09_music REAL RUN (user terminal) crashed → BUG 4 found & FIXED + verified. Gemini MCP ab `docker cp` (`Path:`) ke bajaye HTTP `URL:` deta hai, aur wo URL **container-internal** hai (`localhost:8001`) jabki host pe wo port **8002** (docker-compose `8002:8001`) — host se 8001 = Flow API → 404. Fix: (a) `extract_audio_ref()` URL+Path dono handle karta; (b) URL-mode me path rakh ke host `GEMINI_MUSIC_URL` (config.env, default `localhost:8002`) pe re-root; (c) new getter `core/config.gemini_music_url`. **Verified end-to-end mere sandbox se:** `/music` POST → `local_path http://localhost:8002/output/music_r_...mp3` → download = 744KB valid `ID3` mp3.
- **2026-07-15** — BUG 5 (05_avatar): resume pe Flow HTTP-500 par scene retry back-to-back the (recover time nahi) + already-bane clips dobara ban rahe the (credit waste). Fix: retry se pehle backoff (15s/30s); already-exist clips (>10KB) skip → resume sirf missing scene banata hai.
- **2026-07-15** — END-TO-END MEDIA RUN: 00→08 real output (5 avatar clips, 10 broll clips, complete caption.json+popups). 3 real bugs fix: rapid_edit encoder fallback, 06 fail-fast on partial caption, 06 ChatGPT-timing plausibility guard. 09/10/11 code-verified (docker+bun mere sandbox se blocked; caption↔Remotion type match ✅, symlinks ✅, media refs ✅). User ko `--from 09_music` chalana hai.
- **2026-07-15** — Explored `reel-factory` (24 scripts, 7 prompts, remotion). Mapped call-graph, per-stage I/O contracts, found 3 problems (paths, dual orchestrator, dead code).
- **2026-07-15** — Phase 0: Wrote 6 docs (PRD, Architecture, Rules, Phases, Design, Memory) in `reels-monster/docs/`.
- **2026-07-15** — Phase 1: Scaffolded `reels-monster/` (core/, stages/00-11, project/, _archive/). Built core: `config.py` (PROJECT_ROOT-relative, P1 fixed), `ai_client.py` (copied), `state.py`, `contracts.py` (all 12 stages), `media_utils.py`, `mcp.py`. Copied profile/remotion, made empty sfx/. `config.env` = endpoints/keys only. Smoke test: all core imports + checks PASS.
- **2026-07-15** — Phase 2: Sabhi 12 stages migrate. Batch A (00-04 text, prompt.md sameet), Batch B (05 avatar+generate_talking_avatar.py, 06 process, 07 popups), Batch C (08 broll Semaphore(4), 09 music via core.mcp Lyria3, 10 render Remotion/Bun, 11 final_trim rapid_edit). Har run.py: `STAGE_DIR.parents[1]` sys.path, `PATHS(project)`, argparse `--project/-p`. Logic reel-factory se as-is; sirf paths core pe rewire. Sabka `--help` ✅.
- **2026-07-15** — Phase 3: `orchestrator.py` bana (pipeline.py + auto_media.py merge). ORDER pe chalta: requires-check → run.py subprocess → produces-check → AI QC (optional) → state.mark. Flags `--from/--to/--only/--resume/--dry-run/--no-ai`; `resolve()` number/short/full naam handle karta (`6`/`process`/`06_process`). Media stage (05+) se pehle preflight. `core/preflight.py` bhi migrate (importable `run()` + CLI). Dry-run + resolve tests ✅.
- **2026-07-15** — Phase 4: 11 dead scripts `_archive/` me copy (reel-factory se), `_archive/README.md` me har ek ka "kyun dead / kisne replace kiya" table.
- **2026-07-15** — Phase 5: Root `README.md` (Hinglish, quick-start + stage table + flags + layout), `cleanup.py` port (new protected dirs), `.gitignore` verify (project/output/caches ignored). Final smoke test: core modules import, ORDER⇔CONTRACTS aligned (12), sabhi 12 stage `--help` ✅, orchestrator resolve edge cases ✅.

## 2026-07-16 — Flow self-contained (uv-based, video/image gen)
Teesra service bundle. Flow = **Python/FastAPI** (Gemini/ChatGPT Go binaries the),
isliye "binary" ki jagah **uv** (Rust, isolated env) use kiya — source-bundle +
reproducible, PyInstaller bloat ke bina. Pehle Docker (`flow-agent-server` container).
- **Source:** `Reels-hub/flow-mcp/` (FastAPI, `cli/api.py` → uvicorn :8001, WS :9227).
- **Bundle:** `vendor/flow/` (352K) = `cli/ omniflash/ flow_cli/` + `flow_mcp_server.py`
  + `pyproject.toml` (uv deps: fastapi/uvicorn/websockets/multipart/cryptography) +
  `config.env` (DEFAULT_PROJECT + ports, SERVER_API_KEY empty → **committed, no secret**)
  + `extension/` (Flow Chrome ext) + `output/`.
- **New file** `core/flow_server.py` — gemini/chatgpt mirror: `is_up` (/health),
  `ensure_server` (on-demand, `uv run python cli/api.py`; python3 fallback if no uv;
  wait=40s bcz first uv resolve slow), `warmup` (boot + verify `extension_connected`).
- **config.py:** `flow_server_dir()` (default `vendor/flow`, guard on cli/api.py),
  env key `FLOW_SERVER_DIR`.
- **preflight.py** `check_flow_credits` → `flow_server.warmup()` first, then credits probe.
- **stages/05_avatar + 08_broll** → boot bundled Flow on-demand before HTTP `/v1/videos`.
- **Runtime model:** first boot `uv sync`/`uv run` needs internet (deps resolve once →
  `.venv` cached), phir offline+instant. README me `uv sync` prewarm step (1b).
- **.gitignore:** root `config.env` anchored (`/config.env`) so `vendor/flow/config.env`
  (safe) commits; `vendor/flow/.venv/` + `uv.lock` ignored.
- **Note:** `omniflash/config.py` me hardcoded `AIzaSy...` — ye Google **public**
  aisandbox web-client key (extension JS + orig repo me bhi), secret NAHI → rakha.
- **VERIFIED:** all core imports clean, wiring resolves, uv launched venv + started dep
  resolve (PyPI mere sandbox me blocked = expected; user terminal pe chalega).
- vendor/README.md updated: Flow section (uv setup, extension table +Flow, smoke test,
  troubleshooting rows). Dead `core/mcp.py::flow_cmd` docker code chhoda (unused, no stage
  imports it; sirf core/__init__ import karta hai).

## 2026-07-16 — Repo push-prep (junk clean + secret guard)
GitHub push ke liye cleanup. Deleted: `_ff.log`, `server.log`, `__pycache__`, `.DS_Store`,
`.claude/.cc-writes`. **Secrets gitignored:** `/config.env` (AI_API_KEY), `vendor/*/cookies.json`
(live tokens), `vendor/*/.env`. Created `config.env.example` (key redacted). **Ignored heavy:**
Go binaries (`vendor/*-server`, ~30M, rebuild from source), `profile/avatar.jpg` (personal),
`remotion/node_modules`, `project/`, `output/`. Push manifest ~96 files, zero real keys
(verified grep `fe_oa_`/`sk-ant`). NOTE: `git init` mere sandbox me blocked — user apne
terminal se `git init && add && commit && push` karega.

## ➡️ Handoff for next session
Agar tum naya agent ho: (1) ye Memory.md padho, (2) `docs/Phases.md` me current phase dekho, (3) `docs/Architecture.md §5` se stage contracts, (4) tabhi kaam shuru.

## 2026-07-16 — ChatGPT self-contained (Gemini-parity)
Same migration jo Gemini pe ki thi, ab ChatGPT pe. Pehle ChatGPT OrbStack/Docker
container (`chatgpt-free-api`, port 9225) pe chalta tha. Ab bundled native binary.
- **Source:** `kodelyx/chatgpt-free-api` (GitHub, public, module `chatgpt-agent`, go 1.26).
  User ne apne terminal se clone kiya → `chatgpt-src/` → `go build -o chatgpt-server .`
  → native **Mach-O arm64** binary (9.6M). (Docker container me sirf Linux binary tha,
  koi `.go` source nahi — isliye GitHub clone zaroori tha.)
- **Bundle:** `vendor/chatgpt/` = `chatgpt-server` (native binary) + `.env`
  (`LISTEN_ADDR`, `DEFAULT_MODEL=gpt-5-5`) + `output/`. Cookies pending (extension
  sync ya `docker cp chatgpt-free-api:/app/cookies.json vendor/chatgpt/`).
- **New file** `core/chatgpt_server.py` — exact mirror of `core/gemini_server.py`:
  `is_up` (/health), `ensure_server` (on-demand boot, cwd=vendor/chatgpt, LISTEN_ADDR
  forced to 127.0.0.1:port), `chat` (POST /v1/chat/completions), `warmup`.
- **config.py:** added `chatgpt_server_bin()` / `chatgpt_server_dir()` (default
  `vendor/chatgpt/…`), env keys `CHATGPT_SERVER_BIN`/`CHATGPT_SERVER_DIR`.
- **ai_client.py** `_call_chatgpt` → now `chatgpt_server.chat()` (on-demand, no requests.post).
- **preflight.py** `check_chatgpt` → `chatgpt_server.warmup()` when bundle present,
  legacy /health fallback below.
- **stages/06_process/run.py** → boots bundled server on-demand before `/api/chat/edit`.
- **VERIFIED:** bundled binary self-booted on alt port 9231, `/health` = `ok:true`,
  `mode:chatgpt-api-bridge`, endpoints incl `/api/chat/edit`. Only cookies.json + a
  live extension connection remain (same as Gemini's requirement).

# `vendor/` — Bundled self-contained AI servers

Pipeline teen local AI services use karta hai. Sab **on-demand khud boot** hote hain
(koi Docker nahi, koi manual `run` nahi). Har ek apni cookies ek Chrome extension se
live sync karta hai.

- **ChatGPT** + **Gemini** — Go native binaries (`go build`)
- **Flow** — Python/FastAPI, **`uv`** se isolated env me chalta hai (Rust-fast)

```
vendor/
├── chatgpt/
│   ├── chatgpt-server   ← native macOS-arm64 binary   (git-ignored — build karo)
│   ├── .env             ← LISTEN_ADDR + DEFAULT_MODEL
│   ├── cookies.json     ← extension sync karti hai      (git-ignored — secret)
│   └── output/
├── gemini/
│   ├── gemini-server    ← native macOS-arm64 binary    (git-ignored — build karo)
│   ├── cookies.json     ← extension sync karti hai      (git-ignored — secret)
│   └── output/
└── flow/                ← Python source (committed) — uv run se chalta hai
    ├── cli/ omniflash/ flow_cli/   ← FastAPI app + Google-Flow bridge
    ├── flow_mcp_server.py
    ├── pyproject.toml   ← uv isi se deps resolve karta hai
    ├── config.env       ← DEFAULT_PROJECT + ports (no secrets — committed)
    ├── extension/       ← Chrome extension (Flow login → cookies)
    ├── .venv/           ← uv banata hai                 (git-ignored)
    └── output/
```

> **Kyun kuch git-ignored?** Go binaries platform-specific (macOS-arm64) + bade (~30M)
> hain; `cookies.json` me **live session tokens**; `.venv/` regenerate ho jaata hai.
> Flow ka Python **source commit hota hai** (chhota, cross-platform) — sirf uska env
> `uv` locally banata hai.

---

## Kahan use hote hain

| Service | Port | Stage / jagah | Kaam | Runtime |
|:--|:--|:--|:--|:--|
| **ChatGPT** | `9225` | Stage 06 (`/api/chat/edit`) + AI-fallback | caption timing | Go binary |
| **Gemini**  | `8002` (WS `9226`) | Stage 09 (music) + AI-fallback | Lyria 3 music, chat | Go binary |
| **Flow**    | `8001` (WS `9227`) | Stage 05 (avatar) + 08 (b-roll) | video/image gen | Python + uv |

AI-chat failover chain: **Claude (proxy) → ChatGPT → Gemini** (`core/ai_client.py`).
Pipeline start pe `core/preflight.py` teeno ko `warmup()` karta hai — ek baar boot +
verify, phir har call reuse.

---

## Setup (ek baar)

### 1a. Go binaries build karo (ChatGPT + Gemini)

**ChatGPT** — source: [`kodelyx/chatgpt-free-api`](https://github.com/kodelyx/chatgpt-free-api) (public, Go 1.26)

```bash
git clone https://github.com/kodelyx/chatgpt-free-api.git /tmp/chatgpt-src
cd /tmp/chatgpt-src
CGO_ENABLED=0 go build -o chatgpt-server .
cp chatgpt-server  <repo>/vendor/chatgpt/chatgpt-server
cp .env            <repo>/vendor/chatgpt/.env   # LISTEN_ADDR, DEFAULT_MODEL
```

**Gemini** — source: `free-gemini-api` (Go, Fiber + Lyria 3 bridge)

```bash
cd /path/to/free-gemini-api
go build -o gemini-server .
cp gemini-server <repo>/vendor/gemini/gemini-server
```

Verify (native arm64 hona chahiye, Linux nahi):
```bash
file vendor/chatgpt/chatgpt-server   # → Mach-O 64-bit executable arm64
file vendor/gemini/gemini-server     # → Mach-O 64-bit executable arm64
```

### 1b. Flow env prewarm karo (Python — uv)

Flow ka source repo me hi hai. `uv` iske deps ko pyproject.toml se ek isolated
`.venv` me resolve karta hai. Ek baar prewarm kar lo (internet chahiye, ek hi baar):

```bash
cd vendor/flow
uv sync            # .venv banata hai + deps install (fastapi, uvicorn, ...)
```

Iske baad server boot **offline + instant** hota hai (`uv run` cached env use karta
hai). `uv` na ho to: `pip install -r vendor/flow/requirements.txt` — phir `flow_server`
`python3` fallback pe khud chala lega.

### 2. Chrome extensions load karo (cookies/login sync ke liye)

Servers khud login nahi karte — ek Chrome extension logged-in browser se
cookies/session leke server ko `ws://` pe push karti hai.

`chrome://extensions` → **Developer mode ON** → **Load unpacked**:

| Extension | Folder | Sync port | Login site |
|:--|:--|:--|:--|
| ChatGPT Bridge | `gpt-extension/` (source repo me) | `ws://127.0.0.1:9225` | chatgpt.com |
| Gemini Bridge  | `gemini-extension/` (free-gemini-api me) | `ws://127.0.0.1:9226` | gemini.google.com |
| Flow Bridge    | `vendor/flow/extension/` | `ws://127.0.0.1:9227` | labs.google (Flow) |

Load karne se pehle us site pe **logged in** hona zaroori. Extension server-connect
hote hi session push kar deti hai.

> ChatGPT/Gemini cookies ~15 min me expire hoti hain. Extension proactively (12-min
> timer) refresh karti hai, aur server 403 pe reactively re-sync maangta hai — normal
> run me manual kuch nahi karna padta.

---

## Kaise chalta hai (khud, on-demand)

Kuch manually start karne ki zaroorat **nahi**. Jab stage ko service chahiye:

1. `core/{chatgpt,gemini,flow}_server.py::ensure_server()` port check karta hai
2. Down hai → bundle launch karta hai (cwd = us folder, taaki cookies/config/output
   wahin se mile). Go: `vendor/<svc>/<binary>`. Flow: `uv run python cli/api.py`.
3. `/health` up hone tak wait, phir HTTP call
4. Already up (pichla boot / Docker) → reuse (idempotent)

Manual smoke test:
```bash
python3 -c "from core import chatgpt_server as S; print(S.chat({}, 'hello'))"
python3 -c "from core import gemini_server  as S; print(S.chat({}, 'hello'))"
python3 -c "from core import flow_server    as S; print(S.warmup({}))"
```

---

## Troubleshooting

| Symptom | Wajah / fix |
|:--|:--|
| `no bundled binary found` | Step 1a nahi kiya — `vendor/<svc>/<binary>` missing. Build karo. |
| `no bundled source found` (Flow) | `vendor/flow/cli/api.py` missing — bundle adhoora. |
| Flow boot: `Failed to fetch pypi` | uv env prewarm nahi (Step 1b) ya internet down. `cd vendor/flow && uv sync`. |
| `cookies.json missing` | Extension load/connect nahi hui. Step 2. Browser me logged-in? |
| `extension not connected` | Extension band/reload chahiye. `chrome://extensions` → reload. Flow: Google Flow tab khula ho. |
| `403 Forbidden` log me | Cookies expire — extension re-sync kar degi; ek retry me theek. |
| `NO_FLOW_KEY` | Flow login sync nahi — labs.google pe logged-in + Flow extension connected? |
| Port pehle se busy | Purana server chal raha (Docker/manual). Band karo ya `*_SERVER_URL` alag port pe point karo. |

Override paths (agar bundle kahin aur rakhna ho) — `config.env`:
```
CHATGPT_SERVER_BIN=/abs/path/chatgpt-server
CHATGPT_SERVER_DIR=/abs/path/workdir
GEMINI_SERVER_BIN=/abs/path/gemini-server
GEMINI_SERVER_DIR=/abs/path/workdir
FLOW_SERVER_DIR=/abs/path/flow-source-dir
```


# 🗄️ _archive/ — Dead scripts (reference only)

Ye scripts `reel-factory` me the par **naye pipeline me use nahi hote** — exploration ke
time inka 0 references / superseded hona confirm hua. Yahan sirf **reference ke liye**
rakhe hain (agar kabhi koi logic wapas chahiye ho). **Inhe orchestrator ya kisi stage se
import mat karo.** Kuch bhi zaroori laga to proper stage me migrate karke phir yahan se hatao.

Source: `reel-factory/scripts/<name>.py` (unchanged copies).

| Script | Kyun dead / kisne replace kiya |
|:--|:--|
| `fix_captions.py` | One-off caption patcher. Alignment ab Stage 06 (`process`) me clean handle hota hai. |
| `fix_caption_merges.py` | Manual caption-merge fixer. Same — Stage 06 output already correct. |
| `compile_captions.py` | Purana caption compiler. Stage 06 seedha `caption.json` likhta hai. |
| `polish_captions.py` | Extra caption polish pass — pipeline me kabhi wire nahi hua. |
| `trim_avatar_only.py` | Standalone avatar trim. Stage 06 trim + align dono karta hai. |
| `trim_and_align_avatar.py` | Purana trim+align (dusra variant). Stage 06 ne replace kiya. |
| `normalize_avatar_audio.py` | Audio normalize helper — kahin call nahi hota. |
| `analyze_silence.py` | Silence detector (per-scene). Logic ab Stage 06 ke andar. |
| `sound_manager.py` | Bada SFX manager — popups ke SFX ab Stage 07 (inline `SFX_KEYS`) handle karta. |
| `call_flow_mcp.py` | Ad-hoc Flow MCP caller. Replace: `core/mcp.py` (`flow_call`). |
| `call_gemini_mcp.py` | Ad-hoc Gemini MCP caller. Replace: `core/mcp.py` (`gemini_chat` / `gemini_generate_music`). |

> Verify hone ke baad (jab naya pipeline end-to-end chal jaye) — purana `reel-factory/`
> alag hai, yahan sirf snapshot hai. Ye folder delete karna safe hoga.

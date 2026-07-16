#!/usr/bin/env python3
"""Stage 07 — Popup Designer.

Reads caption.json and, per scene, asks the AI to design 2-4 glass-card icon popups
synced to the spoken words, writing them into each scene's `popup` field.
Rendered by remotion/src/PopupAsset.tsx. Runs AFTER stage 06, BEFORE render.

SFX selection is AI-driven: the sfx/ directory is scanned at runtime, each file is
categorized by name into mood/purpose labels, and the full catalog is passed to the
AI prompt so it picks the most fitting sound per popup based on narration + context.

  requires:  project/scripting/caption.json  (scenes + pages with tokens)
  produces:  project/scripting/caption.json  (each scene gains a `popup` field)

Run:  python3 stages/07_popups/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/popup_designer.py (logic unchanged; paths via core).
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log

# Icons the Remotion renderer understands natively (curated SVG set).
CURATED_SVG = {"chatgpt", "robot", "check", "code", "brain", "human",
               "gear", "shield", "question", "google", "microsoft", "amazon"}
SLOTS = ("left", "center", "right")

# ─── Dynamic SFX catalog ──────────────────────────────────────────────────────

# Mood/purpose keywords found in filenames → human-readable category for the AI.
_SFX_MOOD_MAP = [
    (r"boom|explosion|blast",       "dramatic impact / explosion"),
    (r"impact|hit|punch|slam",      "hard impact / hit"),
    (r"whoosh|swoosh|swipe|woosh",  "motion swoosh / whoosh"),
    (r"pop|bubble|plop",            "pop / bubble"),
    (r"riser|rise|build",           "tension build-up / riser"),
    (r"shine|sparkle|glitter|glow", "shine / sparkle / glow"),
    (r"ding|bell|chime|notification", "notification / ding"),
    (r"success|win|victory|achieve", "success / victory"),
    (r"alert|alarm|warning|siren",  "alert / warning"),
    (r"transition|swipe|slide",     "transition / slide"),
    (r"click|tap|button",           "click / tap"),
    (r"magic|spell|enchant",        "magic / spell"),
    (r"horror|scary|creep",         "horror / suspense"),
    (r"laugh|funny|comedy",         "comedy / laugh"),
    (r"anime|manga|cartoon",        "anime-style"),
    (r"metal|gear|solid|mgs",       "cinematic alert"),
    (r"cinematic|epic|trailer",     "cinematic / epic"),
    (r"drum|beat|kick",             "drum hit / beat"),
    (r"error|fail|wrong",           "error / fail"),
    (r"cash|money|coin|ka-ching",   "money / cash register"),
    (r"water|splash|drip",          "water / splash"),
    (r"glass|break|shatter",        "glass break / shatter"),
]


def _categorize_sfx(filename: str) -> str:
    """Infer a mood/purpose label from the SFX filename."""
    name = filename.lower().replace("-", " ").replace("_", " ")
    for pattern, label in _SFX_MOOD_MAP:
        if re.search(pattern, name):
            return label
    return "general / misc"


def scan_sfx_library(sfx_dir: Path) -> dict:
    """Scan sfx/ folder and build {key: {file, mood}} catalog.

    Each .mp3 file becomes a selectable SFX key (stem of the filename). The AI
    gets both the key name and a mood description so it can make a contextual pick.
    Returns dict like: {"cinematic-boom": {"file": "cinematic-boom.mp3", "mood": "dramatic impact"}}.
    """
    catalog = {}
    if not sfx_dir.exists():
        return catalog
    for f in sorted(sfx_dir.glob("*.mp3")):
        if f.stat().st_size < 500:   # skip broken / near-empty files
            continue
        key = f.stem                 # filename without .mp3
        catalog[key] = {
            "file": f.name,
            "mood": _categorize_sfx(f.name),
        }
    return catalog


def format_sfx_catalog_for_prompt(catalog: dict) -> str:
    """Build a human-readable SFX menu for the AI prompt."""
    if not catalog:
        return "(no SFX files available — skip sfx array)"
    lines = []
    for key, info in catalog.items():
        lines.append(f'  "{key}" → {info["mood"]}')
    return "\n".join(lines)

PROMPT = """You are a motion-graphics director for a vertical (9:16) Hindi explainer reel.
For ONE scene you design floating glass "popup" cards that pop up over the B-roll to
visually reinforce the narration. Each card pops in EXACTLY when its concept is spoken.

SCENE NARRATION (Hindi):
{narration}

SPOKEN WORDS WITH TIMING (scene-local milliseconds; this is your timing spine):
{tokens}

VIDEO COLOR GRADING / THEME (cards must match this look):
{palette}

AVAILABLE SOUND EFFECTS (pick the best match for each popup's feeling):
{sfx_catalog}

DESIGN RULES:
1. COUNT IS STORY-DRIVEN — never pad. Choose the number of cards from what the narration
   actually needs:
   - ONE card when the scene has a single powerful focus/reveal (most impactful — use this often).
   - TWO cards for a contrast or cause->effect (this vs that, before->after).
   - THREE cards only for a genuine sequence/list of 3 distinct concrete things.
   Do NOT force 3. A single strong, well-timed card beats three weak ones. Max 3.
2. SYNC (critical): every card's "atMs" MUST equal the "startMs" of the token whose word
   introduces that concept. Find the token whose text matches the idea; copy its startMs.
   Never invent a time. Stagger cards so they enter in spoken order.
3. STORY: the cards together must tell a mini visual story that mirrors THIS narration
   (before -> after, problem -> solution, cause -> effect, single hero reveal), not random
   icons. Mark the single most important payoff card with "accent": true.
   For ONE card, center it (slot "center") for maximum focus.
4. ICON CHOICE (pick the highest-quality option for each concept):
   - "simpleicon": a real brand/product/technology logo. Use the exact simple-icons slug
     (lowercase, no spaces): e.g. Google->"google", GitHub->"github", Python->"python",
     Bitcoin->"bitcoin", Android->"android", Anthropic->"anthropic". Prefer this for any
     named company/product/language/framework. If unsure a slug exists, use an emoji instead.
   - "svg": one of these curated icons for generic concepts: {curated}.
   - "emoji": for everything else — pick the single most fitting emoji (money 💰, growth 📈,
     warning ⚠️, idea 💡, rocket 🚀, lock 🔒, hacker 🕵️, brain 🧠, danger ☠️, network 🌐).
5. COLOR (match the grading): every card color MUST come from the video's COLOR
   GRADING / THEME above, so the popups feel painted into the same world. Read the
   theme's dominant colors and pick hexes that belong to it (e.g. a green/jade theme
   -> emerald #10B981 / jade #34D399; cyan accents -> #22D3EE; alerts -> the theme's
   alert red #EF4444; neutral -> #94A3B8). Do NOT use off-theme colors (e.g. purple
   on a green/cyan theme). EXCEPTION: a real brand logo (simpleicon) keeps its own
   brand color. Pick 2-3 distinct graded tones across the cards so they read apart.
6. SLOTS: assign "left","center","right". Do not reuse a slot (2 cards -> left+right;
   3 cards -> left+center+right).
7. LABEL: 1-2 SHORT words (English or Hinglish), UPPERCASE feel. Optional "sub" = 1 short line.
8. SFX (CRITICAL — context-aware selection):
   Add one "sfx" entry per card at the same atMs. READ the AVAILABLE SOUND EFFECTS list
   above carefully. Pick the SFX whose MOOD best matches what the popup MEANS:
   - Card about danger/threat/attack → pick an "alert / warning" or "dramatic impact" sound
   - Card about success/achievement/win → pick a "success / victory" or "shine" sound
   - Card about speed/motion/launch → pick a "motion swoosh" sound
   - Card about reveal/highlight/hero → pick a "shine / sparkle" or "cinematic" sound
   - Card about money/business → pick a "money / cash register" sound if available
   - Card about error/fail → pick an "error / fail" sound if available
   - Generic entrance → pick a "pop" or "transition" sound
   - Build-up/stat reveal → pick a "tension build-up / riser" sound
   Use the EXACT key name from the list (the text before "→"). Do NOT invent keys.

Return ONLY this JSON (no markdown, no commentary):
{{
  "cards": [
    {{"icon": {{"type": "svg", "value": "shield"}}, "label": "SECURITY", "sub": "AT RISK",
      "color": "#EF4444", "atMs": 420, "slot": "left", "accent": false}},
    {{"icon": {{"type": "emoji", "value": "🤖"}}, "label": "AI ATTACK",
      "color": "#9333EA", "atMs": 1850, "slot": "right", "accent": true}}
  ],
  "sfx": [
    {{"atMs": 420, "key": "swoosh-simple-66449", "volume": 0.75}},
    {{"atMs": 1850, "key": "anime-shine-sound-effect_QP4mAaX", "volume": 0.8}}
  ]
}}"""


def build_prompt(narration: str, local_tokens: list, sfx_catalog_text: str) -> str:
    return (PROMPT
            .replace("{narration}", narration or "(no narration)")
            .replace("{tokens}", json.dumps(local_tokens, ensure_ascii=False))
            .replace("{curated}", ", ".join(sorted(CURATED_SVG)))
            .replace("{sfx_catalog}", sfx_catalog_text))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def validate_popup(raw: dict, scene_ms: int, valid_sfx_keys: set) -> dict:
    """Coerce the AI output into a safe popup config."""
    hi = max(0, scene_ms - 400)  # a card must enter with time left to animate + read
    cards_in = raw.get("cards", []) if isinstance(raw, dict) else []
    cards = []
    for i, c in enumerate(cards_in[:4]):
        if not isinstance(c, dict):
            continue
        icon = c.get("icon") or {}
        itype = icon.get("type")
        ival = str(icon.get("value", "")).strip()
        if itype not in ("emoji", "simpleicon", "svg") or not ival:
            icon = {"type": "emoji", "value": "✨"}
        elif itype == "svg" and ival not in CURATED_SVG:
            icon = {"type": "emoji", "value": "✨"}   # unknown curated key -> emoji
        else:
            icon = {"type": itype, "value": ival}

        slot = c.get("slot")
        if slot not in SLOTS:
            slot = SLOTS[i % 3]

        try:
            at = int(_clamp(int(c.get("atMs", 0)), 0, hi))
        except (TypeError, ValueError):
            at = int(_clamp(int(scene_ms * (0.2 + 0.25 * i)), 0, hi))

        color = str(c.get("color", "#60A5FA")).strip() or "#60A5FA"
        if not color.startswith("#"):
            color = "#" + color

        cards.append({
            "icon": icon,
            "label": str(c.get("label", "")).strip()[:24],
            **({"sub": str(c["sub"]).strip()[:24]} if c.get("sub") else {}),
            "color": color,
            "atMs": at,
            "slot": slot,
            "accent": bool(c.get("accent", False)),
        })

    # Respect the AI's story-driven count (1-3). Only synthesize a generic card
    # if the AI returned NOTHING — never pad a strong single card with a filler
    # "SMART/AI" card (the prompt itself says one well-timed card beats three weak
    # ones). Padding was injecting off-topic cards and stacking them in one slot.
    if not cards:
        cards.append({
            "icon": {"type": "svg", "value": "brain"},
            "label": "KEY FACT",
            "color": "#60A5FA",
            "atMs": int(_clamp(int(scene_ms * 0.3), 0, hi)),
            "slot": "center",
            "accent": True,
        })

    # De-duplicate slots so two cards never share one (would overlap-stack).
    used = set()
    free = [s for s in SLOTS]
    for c in cards:
        if c["slot"] in used:
            c["slot"] = next((s for s in free if s not in used), c["slot"])
        used.add(c["slot"])

    # Pick a default SFX key for fallback (first swoosh-like or first available).
    default_entrance = next((k for k in valid_sfx_keys if "swoosh" in k), None)
    default_accent   = next((k for k in valid_sfx_keys if "shine" in k or "anime" in k), None)
    if not default_entrance:
        default_entrance = next(iter(valid_sfx_keys), None)
    if not default_accent:
        default_accent = default_entrance

    sfx = []
    for s in (raw.get("sfx", []) if isinstance(raw, dict) else [])[:6]:
        if not isinstance(s, dict):
            continue
        key = s.get("key", "")
        # Accept the key if it matches an available SFX file stem
        if key not in valid_sfx_keys:
            continue
        try:
            at = int(_clamp(int(s.get("atMs", 0)), 0, hi))
        except (TypeError, ValueError):
            continue
        vol = s.get("volume", 0.7)
        try:
            vol = float(vol)
        except (TypeError, ValueError):
            vol = 0.7
        sfx.append({"atMs": at, "key": key, "volume": _clamp(vol, 0.1, 1.0)})

    # Fallback: one sound per card entrance if the AI gave no valid sfx
    if not sfx and default_entrance:
        for i, c in enumerate(cards):
            sfx.append({"atMs": c["atMs"],
                        "key": default_entrance if i == 0 else (default_accent or default_entrance),
                        "volume": 0.75})

    return {"cards": cards, "sfx": sfx}


def fallback_popup(scene_ms: int, valid_sfx_keys: set) -> dict:
    """Used when a scene has no tokens (alignment failed) or the AI call fails."""
    return validate_popup({}, scene_ms, valid_sfx_keys)


def _sync_remotion_sfx_map(sfx_catalog: dict, remotion_src: Path):
    """Update PopupAsset.tsx SFX map to include all sfx/ files so Remotion can play them.

    Reads the current SFX object, adds any new keys from the catalog, and rewrites the
    block. This means if you add new .mp3 files to sfx/, they automatically become
    available to Remotion on the next stage-07 run — no manual tsx editing needed.
    """
    popup_tsx = remotion_src / "PopupAsset.tsx"
    if not popup_tsx.exists() or not sfx_catalog:
        return
    content = popup_tsx.read_text(encoding="utf-8")

    # Find the SFX block: from "const SFX = {" to the closing "};"
    match = re.search(r"(const SFX = \{)(.*?)(\};)", content, re.DOTALL)
    if not match:
        return

    # Parse existing entries to preserve comments/formatting for known keys
    existing_keys = set(re.findall(r"^\s*([\w-]+)\s*[:]", match.group(2), re.MULTILINE))
    # Also handle quoted keys like 'swooshHard'
    existing_keys.update(re.findall(r"['\"]?([\w-]+)['\"]?\s*:", match.group(2)))

    new_keys = set(sfx_catalog.keys()) - existing_keys
    if not new_keys:
        return  # nothing new

    # Append new entries before the closing brace
    additions = "\n  // ── auto-added by stage 07 ──\n"
    for key in sorted(new_keys):
        info = sfx_catalog[key]
        # TSX keys with hyphens need quoting
        safe_key = f"'{key}'" if "-" in key else key
        additions += f"  {safe_key}: 'sfx/{info['file']}',  // {info['mood']}\n"

    insert_pos = match.end(2)
    new_content = content[:insert_pos] + additions + content[insert_pos:]
    popup_tsx.write_text(new_content, encoding="utf-8")
    log(f"   🔧 Added {len(new_keys)} new SFX keys to PopupAsset.tsx")


def main():
    ap = argparse.ArgumentParser(description="Stage 07 — AI popup/icon designer (per scene)")
    ap.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = ap.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys = get_api_keys(config)
    model = ai_model(config)

    # ── Scan sfx/ library and build catalog ──
    sfx_catalog = scan_sfx_library(paths.SFX)
    valid_sfx_keys = set(sfx_catalog.keys())
    sfx_catalog_text = format_sfx_catalog_for_prompt(sfx_catalog)
    log(f"🔊 SFX library: {len(sfx_catalog)} sounds available")

    # Sync Remotion's PopupAsset.tsx SFX map so it can play any new sounds
    _sync_remotion_sfx_map(sfx_catalog, paths.REMOTION / "src")

    cap_path = paths.CAPTION
    if not cap_path.exists():
        raise SystemExit(f"❌ caption.json not found at {cap_path} — run stage 06 (process) first.")
    data = json.loads(cap_path.read_text(encoding="utf-8"))

    scenes = data.get("scenes", [])
    pages = data.get("pages", [])
    fps = data.get("fps", 30)
    n = min(len(scenes), len(pages))
    log(f"🎨 Designing popups for {n} scenes...")

    for i in range(n):
        scene, page = scenes[i], pages[i]
        scene_ms = int(scene.get("durationInFrames", 150) / fps * 1000)
        page_start = page.get("startMs", 0)
        local_tokens = [{"text": t.get("text", ""),
                         "startMs": max(0, t.get("startMs", 0) - page_start)}
                        for t in page.get("tokens", [])]
        narration = page.get("text", "")

        if not local_tokens:
            scene["popup"] = fallback_popup(scene_ms, valid_sfx_keys)
            log(f"   scene {scene.get('index', i)}: no tokens → generic popup")
            continue

        try:
            raw = call_ai(keys, config, model,
                          build_prompt(narration, local_tokens, sfx_catalog_text),
                          max_tokens=1500, label=f"Popup scene {scene.get('index', i)}")
            scene["popup"] = validate_popup(raw, scene_ms, valid_sfx_keys)
            log(f"   scene {scene.get('index', i)}: {len(scene['popup']['cards'])} cards, "
                f"{len(scene['popup']['sfx'])} sfx")
        except Exception as e:
            scene["popup"] = fallback_popup(scene_ms, valid_sfx_keys)
            log(f"   ⚠️ scene {scene.get('index', i)} AI failed ({str(e)[:80]}) → generic popup")

    cap_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 Saved popups into {cap_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Stage 07 — Popup Designer.

Reads caption.json and, per scene, asks the AI to design 2-4 glass-card icon popups
synced to the spoken words, writing them into each scene's `popup` field.
Rendered by remotion/src/PopupAsset.tsx. Runs AFTER stage 06, BEFORE render.

  requires:  project/scripting/caption.json  (scenes + pages with tokens)
  produces:  project/scripting/caption.json  (each scene gains a `popup` field)

Run:  python3 stages/07_popups/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/popup_designer.py (logic unchanged; paths via core).
"""
import argparse
import json
import math
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log

# Icons the Remotion renderer understands natively (curated SVG set).
CURATED_SVG = {"chatgpt", "robot", "check", "code", "brain", "human",
               "gear", "shield", "question", "google", "microsoft", "amazon"}
# Sound effects available in PopupAsset's SFX map.
SFX_KEYS = {"pop", "popSoft", "popHard", "swoosh", "swooshHard", "shine",
            "shineAnime", "impact", "boom", "rise", "ding", "success", "alert"}
SLOTS = ("left", "center", "right")

PROMPT = """You are a motion-graphics director for a vertical (9:16) Hindi explainer reel.
For ONE scene you design floating glass "popup" cards that pop up over the B-roll to
visually reinforce the narration. Each card pops in EXACTLY when its concept is spoken.

SCENE NARRATION (Hindi):
{narration}

SPOKEN WORDS WITH TIMING (scene-local milliseconds; this is your timing spine):
{tokens}

VIDEO COLOR GRADING / THEME (cards must match this look):
{palette}

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
8. SFX: add one "sfx" entry per card at the same atMs. Choose by feeling from this list ONLY:
   {sfx}. entrance->swoosh/pop, sub-item->popSoft/ding, payoff/reveal->shineAnime/success/boom,
   warning->alert, build-up->rise.

Return ONLY this JSON (no markdown, no commentary):
{{
  "cards": [
    {{"icon": {{"type": "svg", "value": "shield"}}, "label": "SECURITY", "sub": "AT RISK",
      "color": "#EF4444", "atMs": 420, "slot": "left", "accent": false}},
    {{"icon": {{"type": "emoji", "value": "🤖"}}, "label": "AI ATTACK",
      "color": "#9333EA", "atMs": 1850, "slot": "right", "accent": true}}
  ],
  "sfx": [
    {{"atMs": 420, "key": "swoosh", "volume": 0.75}},
    {{"atMs": 1850, "key": "shineAnime", "volume": 0.8}}
  ]
}}"""


def build_prompt(narration: str, local_tokens: list) -> str:
    return (PROMPT
            .replace("{narration}", narration or "(no narration)")
            .replace("{tokens}", json.dumps(local_tokens, ensure_ascii=False))
            .replace("{curated}", ", ".join(sorted(CURATED_SVG)))
            .replace("{sfx}", ", ".join(sorted(SFX_KEYS))))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def validate_popup(raw: dict, scene_ms: int) -> dict:
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

    # Ensure at least 2 cards
    while len(cards) < 2:
        i = len(cards)
        cards.append({
            "icon": {"type": "svg", "value": "robot" if i == 0 else "brain"},
            "label": "AI" if i == 0 else "SMART",
            "color": "#9333EA" if i == 0 else "#60A5FA",
            "atMs": int(_clamp(int(scene_ms * (0.2 + 0.3 * i)), 0, hi)),
            "slot": SLOTS[i % 3],
            "accent": i == 1,
        })

    sfx = []
    for s in (raw.get("sfx", []) if isinstance(raw, dict) else [])[:6]:
        if not isinstance(s, dict):
            continue
        key = s.get("key")
        if key not in SFX_KEYS:
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

    # Fallback: one swoosh per card entrance if the AI gave no valid sfx
    if not sfx:
        for i, c in enumerate(cards):
            sfx.append({"atMs": c["atMs"], "key": "swoosh" if i == 0 else "shineAnime",
                        "volume": 0.75})

    return {"cards": cards, "sfx": sfx}


def fallback_popup(scene_ms: int) -> dict:
    """Used when a scene has no tokens (alignment failed) or the AI call fails."""
    return validate_popup({}, scene_ms)


def main():
    ap = argparse.ArgumentParser(description="Stage 07 — AI popup/icon designer (per scene)")
    ap.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = ap.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys = get_api_keys(config)
    model = ai_model(config)

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
            scene["popup"] = fallback_popup(scene_ms)
            log(f"   scene {scene.get('index', i)}: no tokens → generic popup")
            continue

        try:
            raw = call_ai(keys, config, model, build_prompt(narration, local_tokens),
                          max_tokens=1500, label=f"Popup scene {scene.get('index', i)}")
            scene["popup"] = validate_popup(raw, scene_ms)
            log(f"   scene {scene.get('index', i)}: {len(scene['popup']['cards'])} cards")
        except Exception as e:
            scene["popup"] = fallback_popup(scene_ms)
            log(f"   ⚠️ scene {scene.get('index', i)} AI failed ({str(e)[:80]}) → generic popup")

    cap_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 Saved popups into {cap_path}")


if __name__ == "__main__":
    main()

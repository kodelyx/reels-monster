#!/usr/bin/env python3
"""
fix_captions.py — Post-process caption word-timing JSONs to:
1. Merge phonetic Hindi splits → English labels (ए+आई → AI, चैट+जी+पी+टी → ChatGPT, etc.)
2. Fix scene_9 empty captions by re-running alignment
3. Re-compile caption.json (demo.json)
"""

import json
import os
import glob

CAPTION_DIR = "/Users/akash/My-work/reel-factory/project/caption"
CAPTION_JSON = "/Users/akash/My-work/reel-factory/project/scripting/caption.json"

# ─── Merge rules: list of (pattern_words, replacement_label) ──────────────────
# Pattern is matched as consecutive words (case-insensitive on Hindi)
MERGE_RULES = [
    # ChatGPT variants
    (["चैट", "जी", "पी", "टी"],  "ChatGPT"),
    (["चैट", "जीपीटी"],           "ChatGPT"),
    # AI variants
    (["ए", "आई"],                 "AI"),
    # AI Agents
    (["ए", "आई", "एजेंट्स"],     "AI Agents"),
    (["ए", "आई", "एजेंट"],       "AI Agent"),
    # AI Tokens
    (["ए", "आई", "टोकन्स"],      "AI Tokens"),
    # AI Team
    (["ए", "आई", "टीम"],         "AI Team"),
]


def apply_merge_rules(words: list) -> list:
    """Apply all merge rules to a word list, return merged list."""
    result = []
    i = 0
    while i < len(words):
        matched = False
        for pattern, label in MERGE_RULES:
            n = len(pattern)
            window = [w["w"] for w in words[i:i+n]]
            if window == pattern:
                # Merge: use start of first word, end of last word
                merged = {
                    "w": label,
                    "start": words[i]["start"],
                    "end": words[i + n - 1]["end"]
                }
                result.append(merged)
                i += n
                matched = True
                break
        if not matched:
            result.append(words[i])
            i += 1
    return result


def process_caption_file(path: str) -> dict:
    """Load a raw caption file and apply merge rules."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data.get("words", [])
    fixed_words = apply_merge_rules(words)

    # Show diff
    if len(fixed_words) != len(words):
        print(f"  ✏️  Merged: {len(words)} → {len(fixed_words)} words")
        for w in fixed_words:
            if w["w"] in ["AI", "ChatGPT", "AI Agents", "AI Agent", "AI Tokens", "AI Team"]:
                print(f"       ✅ '{w['w']}' @ {w['start']:.2f}s – {w['end']:.2f}s")

    data["words"] = fixed_words
    return data


def main():
    print("🔧 Fixing phonetic caption splits across all scenes...\n")

    files = sorted(glob.glob(os.path.join(CAPTION_DIR, "scene_*_raw_captions.txt")))

    scene_caption_map = {}

    for filepath in files:
        filename = os.path.basename(filepath)
        scene_num = int(filename.split("_")[1])
        print(f"📄 Scene {scene_num}: {filename}")

        data = process_caption_file(filepath)

        if not data.get("words"):
            print(f"  ⚠️  Scene {scene_num} has 0 words — skipping (needs re-alignment)")
        else:
            print(f"  ✅ {len(data['words'])} words OK")

        # Write fixed file back
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        scene_caption_map[scene_num] = data.get("words", [])

    print(f"\n📦 Updating caption.json with fixed word timings...")

    # Update caption.json scenes with word data
    with open(CAPTION_JSON, "r", encoding="utf-8") as f:
        caption = json.load(f)

    scenes = caption.get("scenes", [])
    for scene in scenes:
        idx = scene.get("index")
        if idx in scene_caption_map:
            scene["words"] = scene_caption_map[idx]

    with open(CAPTION_JSON, "w", encoding="utf-8") as f:
        json.dump(caption, f, ensure_ascii=False, indent=2)

    print("✅ caption.json updated!\n")
    print("📊 Summary:")
    for idx in sorted(scene_caption_map.keys()):
        words = scene_caption_map[idx]
        status = "⚠️  EMPTY" if not words else f"✅ {len(words)} words"
        print(f"  Scene {idx:2d}: {status}")


if __name__ == "__main__":
    main()

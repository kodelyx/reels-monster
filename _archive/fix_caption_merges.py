#!/usr/bin/env python3
"""
fix_caption_merges.py — Rule-based phonetic merge fixer for caption.json pages
Merges phonetic Hindi splits → English display tokens, preserving exact timing.

Usage:
    python3 scripts/fix_caption_merges.py -p /Users/akash/My-work/reel-factory
"""

import json
import os
import sys
import argparse

# ─── Merge rules ─────────────────────────────────────────────────────────────
# Each rule: (list_of_consecutive_tokens_to_match, display_label)
MERGE_RULES = [
    # Longest match first (greedy)
    (["ए", "आई", "एजेंट्स"],  "AI Agents"),
    (["ए", "आई", "एजेंट"],    "AI Agent"),
    (["ए", "आई", "टोकन्स"],   "AI Tokens"),
    (["ए", "आई", "टीम"],      "AI Team"),
    (["ए", "आई"],              "AI"),
    (["चैट", "जी", "पी", "टी"], "ChatGPT"),
    (["चैट", "जीपीटी"],        "ChatGPT"),
]

def apply_merges(tokens: list) -> list:
    """Apply merge rules to a token list, return merged list."""
    result = []
    i = 0
    total_merges = 0
    while i < len(tokens):
        matched = False
        for pattern, label in MERGE_RULES:
            n = len(pattern)
            # Match against the Devanagari form; tokens may carry Hinglish in "text"
            window = [
                t.get("devanagari", t.get("text", t.get("w", "")))
                for t in tokens[i:i+n]
            ]
            if window == pattern:
                merged_token = {
                    "text": label,
                    "devanagari": " ".join(window),
                    "startMs": tokens[i].get("startMs", tokens[i].get("start", 0)),
                    "endMs":   tokens[i+n-1].get("endMs", tokens[i+n-1].get("end", 0)),
                }
                result.append(merged_token)
                total_merges += 1
                i += n
                matched = True
                break
        if not matched:
            result.append(tokens[i])
            i += 1
    return result, total_merges


def fix_pages(caption: dict) -> tuple:
    """Fix all pages in caption.json."""
    pages = caption.get("pages", [])
    total = 0

    for page in pages:
        tokens = page.get("tokens", [])
        if not tokens:
            continue

        fixed, merges = apply_merges(tokens)
        total += merges

        if merges > 0:
            page["tokens"] = fixed
            # Rebuild page text from fixed tokens
            page["text"] = " ".join(t["text"] for t in fixed)

    return caption, total


def fix_raw_caption_files(caption_dir: str) -> int:
    """Fix scene_X_raw_captions.txt files too (uses 'w' key)."""
    import glob
    total = 0
    files = sorted(glob.glob(os.path.join(caption_dir, "scene_*_raw_captions.txt")))

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        words = data.get("words", [])
        if not words:
            continue

        # Convert to common format temporarily
        temp = [{"text": w.get("w",""), "startMs": int(w.get("start",0)*1000), "endMs": int(w.get("end",0)*1000)} for w in words]
        fixed_temp, merges = apply_merges(temp)
        total += merges

        if merges > 0:
            # Convert back to raw format
            fixed_words = [{"w": t["text"], "start": t["startMs"]/1000, "end": t["endMs"]/1000} for t in fixed_temp]
            data["words"] = fixed_words
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✏️  {os.path.basename(filepath)}: {merges} merge(s)")

    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--project", default=".", help="Project root")
    args = parser.parse_args()

    caption_path = os.path.join(args.project, "project/scripting/caption.json")
    caption_dir  = os.path.join(args.project, "project/caption")

    print("🔧 Fixing phonetic caption merges...\n")

    # 1. Fix caption.json pages
    with open(caption_path, "r", encoding="utf-8") as f:
        caption = json.load(f)

    pages = caption.get("pages", [])
    print(f"📄 Processing {len(pages)} pages in caption.json:")

    caption, total_page_merges = fix_pages(caption)

    for i, page in enumerate(pages):
        print(f"  Page {i+1:2d}: \"{page.get('text','')[:60]}\"")

    with open(caption_path, "w", encoding="utf-8") as f:
        json.dump(caption, f, ensure_ascii=False, indent=2)

    print(f"\n✅ caption.json saved — {total_page_merges} token(s) merged\n")

    # 2. Fix raw caption txt files
    print("📂 Fixing raw caption txt files:")
    total_raw_merges = fix_raw_caption_files(caption_dir)
    print(f"✅ Raw files fixed — {total_raw_merges} merge(s)\n")

    # 3. Summary
    print("=" * 50)
    print(f"🎉 Done! Total merges: {total_page_merges + total_raw_merges}")
    print("\nFixed tokens:")
    for _, label in MERGE_RULES:
        print(f"  → {label}")


if __name__ == "__main__":
    main()

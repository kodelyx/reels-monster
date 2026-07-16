#!/usr/bin/env python3
"""
compile_captions.py — Compiles raw caption files (scene_*_raw_captions.txt)
into the final project/scripting/caption.json file, applying timing offsets,
silence interval trimming mapping, and phonetic word merging.

Usage:
    python3 scripts/compile_captions.py -p /Users/akash/My-work/reel-factory
"""

import json
import os
import sys
import glob
import argparse
from pathlib import Path

# ─── Merge rules ─────────────────────────────────────────────────────────────
MERGE_RULES = [
    (["ए", "आई", "एजेंट्स"],  "AI Agents"),
    (["ए", "आई", "एजेंट"],    "AI Agent"),
    (["ए", "आई", "टोकन्स"],   "AI Tokens"),
    (["ए", "आई", "टीम"],      "AI Team"),
    (["ए", "आई"],              "AI"),
    (["चैट", "जी", "पी", "टी"], "ChatGPT"),
    (["चैट", "जीपीटी"],        "ChatGPT"),
]

def apply_merges(tokens: list) -> list:
    """Apply merge rules to a token list, return merged list.

    Matches on the Devanagari form (tokens now carry Hinglish in "text" and
    the original word in "devanagari").
    """
    result = []
    i = 0
    while i < len(tokens):
        matched = False
        for pattern, label in MERGE_RULES:
            n = len(pattern)
            window = [t.get("devanagari", t["text"]) for t in tokens[i:i+n]]
            if window == pattern:
                merged_token = {
                    "text": label,
                    "devanagari": " ".join(window),
                    "startMs": tokens[i]["startMs"],
                    "endMs": tokens[i+n-1]["endMs"],
                }
                result.append(merged_token)
                i += n
                matched = True
                break
        if not matched:
            result.append(tokens[i])
            i += 1
    return result

def map_raw_to_trimmed(raw_time, keep_intervals):
    trimmed_time = 0.0
    for start, end in keep_intervals:
        if raw_time < start:
            return trimmed_time
        elif raw_time <= end:
            return trimmed_time + (raw_time - start)
        else:
            trimmed_time += (end - start)
    return trimmed_time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--project", default=".", help="Project root")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    script_path = project_dir / "project" / "scripting" / "script.json"
    caption_dir = project_dir / "project" / "caption"
    intervals_dir = project_dir / "project" / "intervals"
    demo_json_path = project_dir / "project" / "scripting" / "caption.json"

    if not script_path.exists():
        print(f"❌ script.json not found: {script_path}")
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    segments = script_data.get("segments", [])
    if not segments:
        print("❌ No segments in script.json")
        sys.exit(1)

    all_pages = []

    print("⚡ Compiling all 10 scene captions...")

    for seg in segments:
        scene_num = seg["scene"]
        dialogue = seg["narration"]
        
        raw_captions_file = caption_dir / f"scene_{scene_num}_raw_captions.txt"
        intervals_file = intervals_dir / f"scene_{scene_num}_intervals.json"

        if not raw_captions_file.exists():
            print(f"⚠️ Scene {scene_num}: Raw caption file not found at {raw_captions_file}")
            continue

        if not intervals_file.exists():
            print(f"⚠️ Scene {scene_num}: Intervals file not found at {intervals_file}")
            continue

        with open(intervals_file, "r") as f:
            intervals_data = json.load(f)
        keep_intervals = intervals_data.get("active_keep_intervals", [])

        with open(raw_captions_file, "r") as f:
            raw_data = json.load(f)
        
        words = raw_data.get("words", [])
        if not words:
            print(f"⚠️ Scene {scene_num}: No words in raw caption file!")
            continue

        clean_duration_s = sum(end - start for start, end in keep_intervals)
        clean_duration_ms = int(clean_duration_s * 1000)

        tokens = []
        for w in words:
            raw_start = float(w["start"])
            raw_end = float(w["end"])
            
            trimmed_start = map_raw_to_trimmed(raw_start, keep_intervals)
            trimmed_end = map_raw_to_trimmed(raw_end, keep_intervals)
            
            w_start_ms = max(0, int(trimmed_start * 1000))
            w_end_ms = min(clean_duration_ms, int(trimmed_end * 1000))
            
            # Captions render in Hinglish (Roman script); Devanagari is the fallback
            tokens.append({
                "text": (w.get("roman") or w["w"]).strip(),
                "devanagari": w["w"],
                "startMs": w_start_ms,
                "endMs": w_end_ms
            })

        # Apply phonetic merges (ए + आई -> AI, etc.)
        tokens = apply_merges(tokens)
        page_text = " ".join(t["text"] for t in tokens)

        page_entry = {
            "text": page_text,
            "startMs": 0,
            "endMs": clean_duration_ms,
            "tokens": tokens
        }
        all_pages.append((scene_num, page_entry, clean_duration_ms))
        print(f"  Scene {scene_num:2d}: Compiled {len(tokens)} words successfully!")

    # Load structure from existing caption.json if exists
    with open(demo_json_path, "r", encoding="utf-8") as f:
        demo_data = json.load(f)

    fps = demo_data.get("fps", 30)
    overlap_frames = demo_data["style"].get("overlapFrames", 0)
    overlap_ms = int((overlap_frames / fps) * 1000)

    # Sort pages by scene number
    all_pages.sort(key=lambda x: x[0])

    global_time_ms = 0
    final_pages = []

    for i, (scene_num, page, duration_ms) in enumerate(all_pages):
        if i > 0:
            global_time_ms -= overlap_ms

        shifted_page = {
            "text": page["text"],
            "startMs": global_time_ms,
            "endMs": global_time_ms + duration_ms,
            "tokens": []
        }
        for token in page["tokens"]:
            shifted_page["tokens"].append({
                "text": token["text"],
                "devanagari": token.get("devanagari", token["text"]),
                "startMs": global_time_ms + token["startMs"],
                "endMs": global_time_ms + token["endMs"]
            })
        final_pages.append(shifted_page)
        global_time_ms += duration_ms

    demo_data["pages"] = final_pages

    with open(demo_json_path, "w", encoding="utf-8") as f:
        json.dump(demo_data, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Successfully compiled all captions into final caption.json!")

if __name__ == "__main__":
    main()

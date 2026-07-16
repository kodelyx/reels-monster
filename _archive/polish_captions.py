#!/usr/bin/env python3
"""
polish_captions.py — AI-powered caption polisher

Sends each scene's caption tokens to ChatGPT and gets back:
  - English brands/tech terms in English (AI, ChatGPT, etc.)
  - Proper spacing and word merges
  - High-end creator style display text
  - Timing-safe: only changes display text, never timing

Usage:
    python3 scripts/polish_captions.py -p /Users/akash/My-work/reel-factory
"""

import json
import os
import re
import sys
import argparse
import requests

# ─── Config ───────────────────────────────────────────────────────────────────
from config import CHATGPT_SERVER_URL
CHATGPT_API = f"{CHATGPT_SERVER_URL}/v1/chat/completions"
CAPTION_JSON = "project/scripting/caption.json"

SYSTEM_PROMPT = """You are a professional Hinglish YouTube caption editor for high-end tech creators.

Your job is to clean and polish word-level caption tokens from Hindi narration audio.
The display text is Hinglish (Hindi written in Roman script, the way Indians type in chat).
The tokens were extracted via forced audio alignment, so they may have phonetic spelling issues.

RULES (follow strictly):
1. Fix phonetic spellings of English brands/tech terms (works for Devanagari or Roman splits):
   - "ए" + "आई" or "e" + "aai" → merge into single token "AI"
   - "चैट" + "जी" + "पी" + "टी" or "chat" + "g" + "p" + "t" → merge into single token "ChatGPT"
   - same pattern for "AI Agents", "AI Tokens", "AI Team", "AI Agent"

2. If any token is still in Devanagari, transliterate it to natural Hinglish
   (e.g. "दुनिया" → "duniya", "क्या" → "kya"). No diacritics/accent marks.
   Keep Hinglish words as-is otherwise — do NOT translate them to English.

3. When merging tokens, combine their time ranges:
   - merged startMs = first token's startMs
   - merged endMs = last token's endMs

4. Do NOT change any startMs or endMs values for non-merged tokens.

5. Output ONLY valid JSON array of token objects. No explanation, no markdown.

OUTPUT FORMAT (JSON array):
[
  {"text": "bhool", "startMs": 50, "endMs": 600},
  {"text": "jao", "startMs": 630, "endMs": 1020},
  {"text": "ChatGPT", "startMs": 1030, "endMs": 1990},
  ...
]"""


def call_chatgpt(tokens: list, page_text: str) -> list:
    """Send tokens to ChatGPT, get back polished tokens."""
    
    user_message = f"""Scene narration: "{page_text}"

Current tokens (with timing in milliseconds):
{json.dumps(tokens, ensure_ascii=False, indent=2)}

Polish these tokens following all the rules. Return ONLY the JSON array."""

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1
    }

    try:
        resp = requests.post(CHATGPT_API, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        
        polished = json.loads(content)
        return polished
        
    except requests.exceptions.ConnectionError:
        print("  ❌ ChatGPT API not reachable (port 9225). Is Docker running?")
        return tokens
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        print(f"  Raw response: {content[:200]}")
        return tokens
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return tokens


def validate_tokens(original: list, polished: list) -> bool:
    """Basic sanity check: timing should be preserved roughly."""
    if not polished:
        return False
    
    orig_start = original[0].get("startMs", 0)
    orig_end = original[-1].get("endMs", 0)
    pol_start = polished[0].get("startMs", 0)
    pol_end = polished[-1].get("endMs", 0)
    
    # Allow 100ms tolerance
    if abs(orig_start - pol_start) > 100 or abs(orig_end - pol_end) > 100:
        print(f"  ⚠️  Timing mismatch: orig [{orig_start}-{orig_end}] vs polished [{pol_start}-{pol_end}]")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Polish captions with ChatGPT")
    parser.add_argument("-p", "--project", default=".", help="Project root path")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
    args = parser.parse_args()

    caption_path = os.path.join(args.project, CAPTION_JSON)

    if not os.path.exists(caption_path):
        print(f"❌ caption.json not found at {caption_path}")
        sys.exit(1)

    with open(caption_path, "r", encoding="utf-8") as f:
        caption = json.load(f)

    pages = caption.get("pages", [])
    
    if not pages:
        print("❌ No pages found in caption.json")
        sys.exit(1)

    print(f"🎬 Polishing {len(pages)} caption pages with ChatGPT...\n")

    total_merges = 0
    
    for i, page in enumerate(pages):
        page_num = i + 1
        tokens = page.get("tokens", [])
        page_text = page.get("text", "")
        
        print(f"📄 Page {page_num:2d}/{len(pages)}: \"{page_text[:60]}...\"")
        print(f"   Tokens: {len(tokens)}")

        if not tokens:
            print(f"   ⚠️  Skipping — no tokens")
            continue

        polished = call_chatgpt(tokens, page_text)

        if not validate_tokens(tokens, polished):
            print(f"   ⚠️  Validation failed — keeping original tokens")
            continue

        merges = len(tokens) - len(polished)
        total_merges += merges

        # Show what changed
        orig_words = [t["text"] for t in tokens]
        new_words = [t["text"] for t in polished]
        
        changed = [w for w in new_words if w not in orig_words]
        if changed:
            print(f"   ✅ Merged/changed: {changed}")
        else:
            print(f"   ✅ No changes needed")

        if not args.dry_run:
            page["tokens"] = polished
            # Also update page text to use correct English
            new_text = " ".join(t["text"] for t in polished)
            page["text"] = new_text

        print()

    if not args.dry_run:
        # Save updated caption.json
        with open(caption_path, "w", encoding="utf-8") as f:
            json.dump(caption, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved polished caption.json")
        print(f"📊 Total merges applied: {total_merges}")
    else:
        print(f"🔍 Dry run complete — {total_merges} merges would be applied")
        print("   Run without --dry-run to save changes")


if __name__ == "__main__":
    main()

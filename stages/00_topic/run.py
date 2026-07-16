#!/usr/bin/env python3
"""Stage 00 — Topic Discovery.

Reads profile/profile.json, web-searches fresh AI/tech news, picks ONE viral topic
matched to the creator profile, and never repeats a past topic (profile/topic_history.json).

  requires:  profile/profile.json
  produces:  project/topic.json  { topic, hook, why_trending, visuals_suggested, source }

Run standalone:  python3 stages/00_topic/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/topic_finder.py (logic unchanged).
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log

WEB_SEARCHES = 5  # how many live web searches the model may run


def load_topic_history(paths: PATHS) -> list:
    if paths.TOPIC_HISTORY.exists():
        try:
            return json.loads(paths.TOPIC_HISTORY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("⚠️  topic_history.json corrupt, starting fresh.")
    return []


def save_topic_history(paths: PATHS, history: list) -> None:
    paths.TOPIC_HISTORY.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def build_topic_prompt(profile: dict, history: list, today: str) -> str:
    past_topics = [h["topic"] for h in history][-30:]
    return f"""You are a master Trend Analyst + Virality Expert for short-form video.
Today's date is {today}.

CREATOR PROFILE:
{json.dumps(profile, ensure_ascii=False, indent=2)}

ALREADY USED TOPICS (never repeat or closely overlap these):
{json.dumps(past_topics, ensure_ascii=False, indent=2)}

TASK:
1. Use web search to find the freshest, most viral AI / technology news from the
   last few days (prefer the last 7 days). Run a few different searches — e.g.
   new AI model launches, AI robots/humanoids, AI agents, viral AI demos, and
   AI news relevant to India.
2. From what you find, select the ONE story with the highest viral potential for
   this creator's audience. It must satisfy every rule in profile.virality_rules
   and avoid everything in profile.avoid_topics.
3. Base it on a REAL story you found via search. You may sharpen the angle, but
   do not invent fake news. Cite the real source in the "source" field.

After searching, reply with ONLY this JSON (no other text, no markdown):
{{
  "topic": "The exact story/phenomenon in English",
  "hook": "The opening 2-second hook line in Hindi (Devanagari)",
  "why_trending": "Why this has viral potential right now",
  "visuals_suggested": "What dark, cinematic AI B-roll clips we will need",
  "source": "The real headline/outlet + date this is based on"
}}"""


def main():
    parser = argparse.ArgumentParser(description="Stage 00 — Topic Discovery")
    parser.add_argument("--project", "-p",
                        default=str(Path(__file__).resolve().parents[2]),
                        help="Path to the reels-monster project root")
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys = get_api_keys(config)
    model = ai_model(config)

    if not paths.PROFILE_JSON.exists():
        raise SystemExit(f"❌ profile.json not found at {paths.PROFILE_JSON}")
    profile = json.loads(paths.PROFILE_JSON.read_text(encoding="utf-8"))

    history = load_topic_history(paths)
    today = datetime.now().strftime("%Y-%m-%d")
    log(f"🌐 Asking AI ({model}) to web-search fresh AI news & pick a viral topic... "
        f"({len(keys)} key(s), up to {WEB_SEARCHES} searches)")
    prompt = build_topic_prompt(profile, history, today)
    topic = call_ai(keys, config, model, prompt, max_tokens=2048,
                    label="Topic pick", web_search=WEB_SEARCHES)

    paths.TOPIC.write_text(
        json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8")

    history.append({"topic": topic["topic"], "date": today})
    save_topic_history(paths, history)

    log(f"💾 Saved: {paths.rel(paths.TOPIC)}")
    print(json.dumps(topic, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

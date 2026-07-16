#!/usr/bin/env python3
"""Stage 04 — Music Prompt.

Brief + narration → a 60-80 word background-music prompt for Lyria/MusicFX.

  requires:  project/scripting/pre_production.json, project/scripting/script.json
  produces:  project/scripting/music_prompt.txt  (plain text, 60-80 words)

Run:  python3 stages/04_music_prompt/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/pipeline.py::step4_music_prompt (logic unchanged).
"""
import argparse
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log
from core.promptlib import read_prompt, fill, load_json


def main():
    parser = argparse.ArgumentParser(description="Stage 04 — Music Prompt")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys, model = get_api_keys(config), ai_model(config)

    pre = load_json(paths.PRE_PRODUCTION)
    script = load_json(paths.SCRIPT)
    brief = pre["brief"]
    style = pre.get("style_bible", {})
    prompt = fill(read_prompt(STAGE_DIR),
                  topic=brief.get("topic", ""),
                  tone=brief.get("tone", ""),
                  audience=brief.get("audience", ""),
                  visual_style=style.get("visual_style", ""),
                  segments=script.get("segments", []))

    log("▶️  Stage 04: Music Prompt")
    text = call_ai(keys, config, model, prompt, max_tokens=1024,
                   expect_json=False, label="Music Prompt")
    paths.MUSIC_PROMPT.parent.mkdir(parents=True, exist_ok=True)
    paths.MUSIC_PROMPT.write_text(text, encoding="utf-8")
    log(f"💾 Saved {paths.rel(paths.MUSIC_PROMPT)}")


if __name__ == "__main__":
    main()

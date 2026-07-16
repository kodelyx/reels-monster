#!/usr/bin/env python3
"""Stage 01 — Pre-Production.

Topic → creative brief + research + style bible.

  requires:  project/topic.json
  produces:  project/scripting/pre_production.json  { brief, research, style_bible }

Run:  python3 stages/01_preproduction/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/pipeline.py::step1_pre_production (logic unchanged).
"""
import argparse
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log
from core.promptlib import read_prompt, fill, load_json, save_json


def main():
    parser = argparse.ArgumentParser(description="Stage 01 — Pre-Production")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys, model = get_api_keys(config), ai_model(config)

    topic = load_json(paths.TOPIC)
    duration = topic.get("duration_seconds", 30)
    prompt = fill(read_prompt(STAGE_DIR), topic=topic["topic"], duration=str(duration))

    log("▶️  Stage 01: Pre-Production")
    result = call_ai(keys, config, model, prompt, max_tokens=4096, label="Pre-Production")
    save_json(paths.PRE_PRODUCTION, result)
    log(f"💾 Saved {paths.rel(paths.PRE_PRODUCTION)}")


if __name__ == "__main__":
    main()

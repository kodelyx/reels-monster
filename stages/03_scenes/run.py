#!/usr/bin/env python3
"""Stage 03 — Scene Planning.

Narration segments → shot plan with a `video_prompt` per scene (for B-roll gen).

  requires:  project/scripting/pre_production.json, project/scripting/script.json
  produces:  project/scripting/scenes.json  { scenes[{ video_prompt, ... }] }

Run:  python3 stages/03_scenes/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/pipeline.py::step3_scene_planner (logic unchanged).
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
    parser = argparse.ArgumentParser(description="Stage 03 — Scene Planning")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys, model = get_api_keys(config), ai_model(config)

    pre = load_json(paths.PRE_PRODUCTION)
    script = load_json(paths.SCRIPT)
    prompt = fill(read_prompt(STAGE_DIR),
                  style_bible=pre.get("style_bible", {}),
                  segments=script.get("segments", []),
                  prev_context="none")

    log("▶️  Stage 03: Scene Planning")
    result = call_ai(keys, config, model, prompt, max_tokens=8192, label="Scene Planning")
    save_json(paths.SCENES, result)
    log(f"💾 Saved {paths.rel(paths.SCENES)}")


if __name__ == "__main__":
    main()

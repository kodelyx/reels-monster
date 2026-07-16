#!/usr/bin/env python3
"""Stage 02 — Scriptwriting.

Brief → full Hindi (Devanagari) narration, split into scene segments.

  requires:  project/scripting/pre_production.json
  produces:  project/scripting/script.json  { logline, segments[] }

Run:  python3 stages/02_script/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/pipeline.py::step2_scriptwriter (logic unchanged).
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
    parser = argparse.ArgumentParser(description="Stage 02 — Scriptwriting")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys, model = get_api_keys(config), ai_model(config)

    pre = load_json(paths.PRE_PRODUCTION)
    brief = pre["brief"]
    num_scenes = brief.get("num_scenes", 5)
    scene_seconds = brief.get("scene_seconds", 6)
    words_per_scene = round(scene_seconds * 2.5)
    prompt = fill(read_prompt(STAGE_DIR),
                  num_scenes=str(num_scenes),
                  scene_seconds=str(scene_seconds),
                  words_per_scene=str(words_per_scene),
                  brief=brief,
                  research=pre.get("research", {}),
                  style_bible=pre.get("style_bible", {}),
                  format=brief.get("format", "portrait (9:16)"))

    log("▶️  Stage 02: Scriptwriting")
    result = call_ai(keys, config, model, prompt, max_tokens=6144, label="Scriptwriting")
    save_json(paths.SCRIPT, result)
    log(f"💾 Saved {paths.rel(paths.SCRIPT)}")


if __name__ == "__main__":
    main()

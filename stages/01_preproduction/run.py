#!/usr/bin/env python3
"""Stage 01 — Pre-Production.

Topic → creative brief + research + style bible.

  requires:  project/topic.json
  produces:  project/scripting/pre_production.json  { brief, research, style_bible }

Run:  python3 stages/01_preproduction/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/pipeline.py::step1_pre_production (logic unchanged).
"""
import argparse
import json
import re
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, ai_model
from core.ai_client import get_api_keys, call_ai, log
from core.promptlib import read_prompt, fill, load_json, save_json


def _profile_duration(paths) -> int:
    """Target seconds — the SINGLE source of truth is profile.json format.duration_seconds.

    Accepts a plain number ("70") or a range ("60-80", uses the upper bound so the
    story gets full coverage). There is NO hardcoded fallback: if the key is missing,
    empty, or unparseable, the workflow must NOT run with a guessed length — we raise
    SystemExit so the user fixes profile.json first.
    """
    if not paths.PROFILE_JSON.exists():
        raise SystemExit(f"❌ profile.json not found at {paths.PROFILE_JSON} — "
                         "cannot determine video duration. Aborting.")
    prof = json.loads(paths.PROFILE_JSON.read_text(encoding="utf-8"))
    raw = str(prof.get("format", {}).get("duration_seconds", "")).strip()
    nums = re.findall(r"\d+", raw)
    if not nums:
        raise SystemExit(
            "❌ profile.json → format.duration_seconds is missing or has no number "
            f"(got: {raw!r}). Set it (e.g. \"60-80\" or \"70\") before running. Aborting.")
    return int(nums[-1])


def main():
    parser = argparse.ArgumentParser(description="Stage 01 — Pre-Production")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    keys, model = get_api_keys(config), ai_model(config)

    topic = load_json(paths.TOPIC)
    duration = _profile_duration(paths)
    prompt = fill(read_prompt(STAGE_DIR), topic=topic["topic"], duration=str(duration))

    log("▶️  Stage 01: Pre-Production")
    result = call_ai(keys, config, model, prompt, max_tokens=4096, label="Pre-Production",
                     web_search=5)
    save_json(paths.PRE_PRODUCTION, result)
    log(f"💾 Saved {paths.rel(paths.PRE_PRODUCTION)}")


if __name__ == "__main__":
    main()

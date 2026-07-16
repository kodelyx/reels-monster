#!/usr/bin/env python3
"""Reels-Monster — master orchestrator.

Runs the 12-stage pipeline end-to-end with two-layer handover:
  • Layer A (contracts): before a stage its `requires` are validated, after it its
    `produces` are validated — a stage never runs on missing input or is marked done
    on broken output.
  • Layer B (state): project/state.json tracks every stage's status so --resume picks
    up exactly where a failed/partial run stopped.

Merges reel-factory's two old orchestrators (pipeline.py = text 1-4, auto_media.py =
media + verify) into one. Each stage is run as its own `stages/<name>/run.py` subprocess,
so orchestration and stage logic stay decoupled.

Usage:
  python3 orchestrator.py                     # run all incomplete stages
  python3 orchestrator.py --resume            # skip stages already DONE in state.json
  python3 orchestrator.py --from 06_process   # start at a stage (name or number)
  python3 orchestrator.py --only 09_music     # run just one stage
  python3 orchestrator.py --to 04_music_prompt# stop after a stage (text-only run)
  python3 orchestrator.py --dry-run           # print the plan, run nothing
  python3 orchestrator.py --no-ai             # deterministic contract checks only (skip AI QC)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from core.config import PATHS, load_config, ai_model
from core.contracts import ORDER, check as contract_check, get as get_contract
from core.state import State, PENDING, RUNNING, DONE, FAILED
from core import preflight, media_utils
from core.ai_client import log

# Stages from this index onward hit external services → need preflight + verify.
FIRST_MEDIA = ORDER.index("05_avatar")


# ─── stage resolution ─────────────────────────────────────────────────────────

def resolve(token: str) -> str:
    """Map '6', '06', '06_process', or 'process' → canonical stage name."""
    if token in ORDER:
        return token
    t = token.lstrip("0") or "0"
    for name in ORDER:
        num = name.split("_", 1)[0]
        if token == num or t == num.lstrip("0") or token in name.split("_", 1)[1]:
            return name
    raise SystemExit(f"❌ Unknown stage '{token}'. Valid: {', '.join(ORDER)}")


def plan_stages(args) -> list:
    if args.only:
        return [resolve(args.only)]
    stages = list(ORDER)
    if args.from_stage:
        stages = stages[ORDER.index(resolve(args.from_stage)):]
    if args.to_stage:
        end = ORDER.index(resolve(args.to_stage))
        stages = [s for s in stages if ORDER.index(s) <= end]
    return stages


# ─── AI QC (optional) ─────────────────────────────────────────────────────────

def collect_facts(stage, paths) -> dict:
    """Inspect a stage's produced files and return real, machine-collected facts
    (existence, counts, durations, key JSON fields) for the QC AI to judge.
    Bina iske QC ke paas verify karne ko kuch nahi hota."""
    n = media_utils.n_scenes(paths)
    produces = get_contract(stage).produces
    has_per_scene = any(f.per_scene for f in produces)
    facts = {"stage": stage}
    # scene count sirf tab relevant hai jab stage per-scene files banata hai
    # (avatar/broll). Single-file outputs (script, scenes.json, music_prompt.txt)
    # ko scene count se match karne ki zaroorat NAHI — warna QC AI galat FAIL deta.
    if has_per_scene:
        facts["expected_scenes"] = n
    for f in produces:
        if f.per_scene:
            clips = {}
            for i in range(1, (n or 0) + 1):
                p = f.resolve(paths, i)
                ok, dur = (media_utils.audio_ok(p) if f.kind == "audio"
                           else media_utils.mp4_ok(p))
                clips[p.name] = {"exists": p.exists(), "seconds": round(dur, 1)}
            facts[f.path] = {"expected": n, "clips": clips}
        else:
            p = f.resolve(paths)
            info = {"exists": p.exists(),
                    "size_bytes": p.stat().st_size if p.exists() else 0}
            if f.kind == "json" and p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    for key in ("scenes", "segments", "pages"):
                        if isinstance(data.get(key), list):
                            info[f"{key}_count"] = len(data[key])
                    info["top_keys"] = list(data.keys())[:10]
                except Exception as e:
                    info["json_error"] = str(e)[:60]
            elif f.kind in ("mp4",) and p.exists():
                ok, dur = media_utils.mp4_ok(p)
                info["seconds"] = round(dur, 1)
            elif f.kind == "audio" and p.exists():
                ok, dur = media_utils.audio_ok(p)
                info["seconds"] = round(dur, 1)
            elif f.kind == "text" and p.exists():
                info["chars"] = len(p.read_text(encoding="utf-8"))
            facts[f.path] = info
    return facts


def ai_verify(stage, facts, keys, config, model, use_ai):
    if not use_ai or not keys:
        return True, "AI QC skipped"
    from core.ai_client import call_ai
    prompt = (
        f"You are a QC supervisor for an automated video pipeline.\n"
        f"Stage: {stage}\nMachine-collected facts:\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
        f"Judge ONLY from the facts above. The stage SUCCEEDS if every listed file "
        f"exists, is non-empty, and looks structurally sane. It FAILS only if a file "
        f"is missing, empty (0 bytes / 0 chars), a json_error is present, or a "
        f"duration is ~0.\n"
        f"If 'expected_scenes' is present, per-scene clip counts must match it; if it "
        f"is ABSENT, this stage produces whole-video/single outputs — do NOT expect "
        f"per-scene structure or invent a scene-count requirement.\n"
        f'Reply ONLY JSON: {{"verdict":"PASS"|"FAIL","reason":"one short sentence"}}'
    )
    try:
        res = call_ai(keys, config, model, prompt, max_tokens=300, label=f"QC {stage}")
        return res.get("verdict", "FAIL").upper() == "PASS", res.get("reason", "")
    except Exception as e:
        return True, f"AI QC unavailable ({str(e)[:50]}); contract checks passed"


# ─── run one stage ────────────────────────────────────────────────────────────

def run_stage(stage, paths, state, config, keys, model, use_ai) -> bool:
    log(f"━━━ {stage} ━━━")

    ok, errs = contract_check(stage, "requires", paths)
    if not ok:
        state.mark(stage, FAILED, error="requires: " + "; ".join(errs))
        log(f"   ❌ requires not met:\n     - " + "\n     - ".join(errs))
        return False

    state.mark(stage, RUNNING)
    cmd = [sys.executable, str(paths.ROOT / "stages" / stage / "run.py"), "-p", str(paths.ROOT)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        state.mark(stage, FAILED, error=f"run.py exited {proc.returncode}")
        log(f"   ❌ {stage} exited {proc.returncode}")
        return False

    ok, errs = contract_check(stage, "produces", paths)
    if not ok:
        state.mark(stage, FAILED, error="produces: " + "; ".join(errs))
        log(f"   ❌ output invalid:\n     - " + "\n     - ".join(errs))
        return False

    facts = collect_facts(stage, paths)
    ai_ok, reason = ai_verify(stage, facts, keys, config, model, use_ai)
    if not ai_ok:
        state.mark(stage, FAILED, error=f"AI QC: {reason}")
        log(f"   ❌ AI QC failed: {reason}")
        return False

    state.mark(stage, DONE, output=reason or "contract ok")
    log(f"   ✅ {stage} done — {reason or 'contract ok'}\n")
    return True


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Reels-Monster orchestrator")
    ap.add_argument("--project", "-p", default=str(ROOT))
    ap.add_argument("--from", dest="from_stage", default=None, help="start at stage (name/number)")
    ap.add_argument("--to", dest="to_stage", default=None, help="stop after stage (name/number)")
    ap.add_argument("--only", default=None, help="run exactly one stage")
    ap.add_argument("--resume", action="store_true", help="skip stages already DONE")
    ap.add_argument("--dry-run", action="store_true", help="print plan, run nothing")
    ap.add_argument("--no-ai", action="store_true", help="deterministic contract checks only")
    args = ap.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    model = ai_model(config)
    state = State(paths.STATE)

    stages = plan_stages(args)
    if args.resume:
        stages = [s for s in stages if not state.is_done(s)]

    log(f"🐲 Reels-Monster | model={model} | plan: {', '.join(stages) or '(nothing to do)'}\n")
    if args.dry_run:
        for s in stages:
            log(f"   • {s}  [{state.status(s)}]")
        log("\n(dry-run — nothing executed)")
        return 0
    if not stages:
        log("✅ Nothing to do — all requested stages already done.")
        return 0

    use_ai = not args.no_ai
    keys = []
    if use_ai:
        try:
            from core.ai_client import get_api_keys
            keys = get_api_keys(config)
        except SystemExit:
            log("⚠️  No AI keys — AI QC disabled, deterministic checks still run.\n")
            use_ai = False

    # Preflight once, only if the plan reaches a media stage.
    if any(ORDER.index(s) >= FIRST_MEDIA for s in stages):
        all_ok, blocking = preflight.run(config, paths)
        if not all_ok:
            log(f"❌ Preflight blocked by: {', '.join(blocking)}. Fix services, then retry.")
            return 1

    for s in stages:
        if not run_stage(s, paths, state, config, keys, model, use_ai):
            log("\n" + state.summary(ORDER))
            log(f"\n🛑 Stopped at {s}. Fix it, then: python3 orchestrator.py --resume")
            return 1

    log("\n" + state.summary(ORDER))
    log("\n🎉 Pipeline complete! → output/final_trimmed.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())

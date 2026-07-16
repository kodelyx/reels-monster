#!/usr/bin/env python3
"""Stage 08 — B-roll generation.

For each scene, generates two top-screen B-roll clips (a = first half, b = second
half) via the Flow API, sized to match the scene's caption duration. Runs in
parallel, capped at 4 concurrent Flow jobs.

  requires:  project/scripting/scenes.json (video_prompt per scene)
  produces:  project/broll/scene_N_a.mp4, project/broll/scene_N_b.mp4
             (durations read from caption.json if present, else 10s)

Run:  python3 stages/08_broll/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/broll_generator.py (logic unchanged; paths via core).
"""
import argparse
import json
import shutil
import sys
import threading
import urllib.request
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, flow_api_url

_FLOW_SEM = threading.Semaphore(4)  # Flow recommends ~4 parallel jobs


def log(scene_num, msg):
    print(f"🎬 [Scene {scene_num}] {msg}", file=sys.stderr)


def generate_and_download(scene_num, prompt, paths, flow_url, duration, suffix=""):
    with _FLOW_SEM:
        _generate_and_download(scene_num, prompt, paths, flow_url, duration, suffix)


def _generate_and_download(scene_num, prompt, paths, flow_url, duration, suffix=""):
    temp_dir = paths.PROJECT / f"temp_broll_scene_{scene_num}{suffix}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"temp_scene_{scene_num}{suffix}.mp4"

    payload = {"prompt": prompt, "aspect": "landscape", "n": 1, "duration": duration}
    req = urllib.request.Request(
        f"{flow_url}/v1/videos/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")

    log(scene_num, f"Sending B-roll request to Flow API (duration={duration}s)...")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            if resp.status != 200:
                log(scene_num, f"❌ Flow API error: HTTP {resp.status}")
                return
            res_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(scene_num, f"❌ Video generation API call failed: {e}")
        return

    videos = res_data.get("data", [])
    if not videos:
        log(scene_num, "❌ No video returned by Flow API.")
        return
    video_url = videos[0]["url"]
    log(scene_num, f"Video generated! URL: {video_url}")

    log(scene_num, f"Downloading video to {temp_file}...")
    try:
        with urllib.request.urlopen(urllib.request.Request(video_url), timeout=300) as resp:
            temp_file.write_bytes(resp.read())
    except Exception as e:
        log(scene_num, f"❌ Video download failed: {e}")
        return

    dest = paths.BROLL / f"scene_{scene_num}{suffix}.mp4"
    if temp_file.exists() and temp_file.stat().st_size > 0:
        shutil.move(str(temp_file), str(dest))
        log(scene_num, f"✅ Saved: {paths.rel(dest)}")
    else:
        log(scene_num, "❌ Download file invalid or empty.")
    shutil.rmtree(temp_dir, ignore_errors=True)


def snap(sec):
    for d in (4, 6, 8, 10):
        if d >= sec:
            return d
    return 10


def main():
    parser = argparse.ArgumentParser(description="Stage 08 — B-roll generation")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    # Boot the bundled Flow server on-demand (Python/FastAPI via uv; no Docker). If
    # the bundle isn't present this is a no-op and we assume an external server.
    try:
        from core import flow_server
        from core.config import flow_server_dir
        if flow_server_dir(config):
            flow_server.ensure_server(config)
    except Exception as e:
        print(f"⚠️  Flow server not auto-started: {str(e)[:80]}")
    flow_url = flow_api_url(config)

    if not paths.SCENES.exists():
        print(f"❌ scenes.json not found: {paths.SCENES}")
        sys.exit(1)

    # Match clip length to each scene's caption duration if available.
    durations = {}
    if paths.CAPTION.exists():
        try:
            cap = json.loads(paths.CAPTION.read_text(encoding="utf-8"))
            fps = cap.get("fps", 30)
            for entry in cap.get("scenes", []):
                idx, frames = entry.get("index"), entry.get("durationInFrames")
                if idx and frames:
                    durations[idx] = float(frames) / float(fps)
        except Exception as e:
            print(f"⚠️ Warning: Could not parse caption.json: {e}")

    scenes = json.loads(paths.SCENES.read_text(encoding="utf-8")).get("scenes", [])
    if not scenes:
        print("❌ No scenes found in scenes.json.")
        sys.exit(1)

    paths.BROLL.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Generating {len(scenes)} scenes × 2 B-roll clips (landscape)...")
    print(f"📁 Project directory: {paths.ROOT}")

    threads = []
    for s in scenes:
        scene_num = s["scene"]
        prompt_a = s["video_prompt"]
        prompt_b = s.get("video_prompt_2") or prompt_a
        required_dur = durations.get(scene_num, 10.0)
        half = snap(max(2.0, required_dur / 2))
        print(f"🎬 Scene {scene_num}: {required_dur:.2f}s → 2 clips × {half}s (a + b)")
        for suffix, prompt in (("_a", prompt_a), ("_b", prompt_b)):
            t = threading.Thread(target=generate_and_download,
                                 args=(scene_num, prompt, paths, flow_url, half, suffix))
            threads.append(t)
            t.start()

    for t in threads:
        t.join()
    print("\n🎉 Batch B-roll generation completed!")


if __name__ == "__main__":
    main()

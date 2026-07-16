#!/usr/bin/env python3
import json
import subprocess
import sys
import shutil
import argparse
from pathlib import Path

def log(scene_num, msg):
    print(f"✂️ [Scene {scene_num}] {msg}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Trim Avatar Videos Only Using Silence Intervals")
    parser.add_argument(
        "--project_dir", "-p",
        default=str(Path.cwd()),
        help="Path to the video project folder (default: current directory)"
    )
    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()

    # Load project config
    sys.path.append(str(project_dir / "scripts"))
    from config import load_env, REMOTION_AVATAR_DIR, RAPID_EDIT_SCRIPT_PATH, SCRIPT_JSON_PATH, REMOTION_CAPTION_JSON_PATH
    load_env()

    avatar_dir = REMOTION_AVATAR_DIR
    rapid_edit_script = RAPID_EDIT_SCRIPT_PATH
    script_path = SCRIPT_JSON_PATH
    caption_json_path = REMOTION_CAPTION_JSON_PATH

    if not script_path.exists():
        print(f"❌ script.json not found: {script_path}")
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    segments = script_data.get("segments", [])
    if not segments:
        print("❌ No segments found in script.json.")
        sys.exit(1)

    scene_updates = []

    for seg in segments:
        scene_num = seg["scene"]
        raw_video = avatar_dir / f"scene_{scene_num}.mp4"
        clean_video = avatar_dir / f"scene_{scene_num}_clean.mp4"
        intervals_json_path = project_dir / "project" / "intervals" / f"scene_{scene_num}_intervals.json"

        if not raw_video.exists():
            log(scene_num, f"⚠️ Raw video not found at {raw_video}, skipping.")
            continue

        if not intervals_json_path.exists():
            log(scene_num, f"⚠️ Intervals JSON not found at {intervals_json_path}, skipping.")
            continue

        with open(intervals_json_path, "r", encoding="utf-8") as f:
            intervals_data = json.load(f)

        keep_intervals = intervals_data.get("active_keep_intervals", [])
        if not keep_intervals:
            log(scene_num, "⚠️ No active keep intervals found, skipping.")
            continue

        # Calculate clean video duration
        duration_s = sum(end - start for start, end in keep_intervals)
        duration_frames = int(duration_s * 30)

        # Create temporary config for rapid_edit.py
        temp_config = project_dir / "project" / f"temp_intervals_{scene_num}.json"
        with open(temp_config, "w", encoding="utf-8") as f:
            json.dump({"intervals": keep_intervals}, f)

        # Run rapid_edit.py to trim silence
        log(scene_num, f"Running rapid_edit silence trimmer for {duration_s:.2f}s active speech...")
        try:
            subprocess.run([
                "python3", str(rapid_edit_script),
                "-path", str(raw_video),
                "-out", str(clean_video),
                "-config", str(temp_config)
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log(scene_num, f"❌ Trimming failed: {e.stderr.decode('utf-8')}")
            if temp_config.exists():
                temp_config.unlink()
            continue
        finally:
            if temp_config.exists():
                temp_config.unlink()

        # Replace raw video with clean video
        if clean_video.exists():
            raw_video.unlink()
            shutil.move(str(clean_video), str(raw_video))
            log(scene_num, "✅ Trimming complete. Clean video saved!")

        scene_updates.append({
            "index": scene_num,
            "brollSrc": f"broll/scene_{scene_num}.mp4",
            "avatarSrc": f"avatar/scene_{scene_num}.mp4",
            "durationInFrames": duration_frames,
            "playbackRate": 1.0
        })

    # Update caption.json
    if not caption_json_path.exists():
        print(f"⚠️ caption.json not found at {caption_json_path}. Creating empty base...")
        caption_json_path.parent.mkdir(parents=True, exist_ok=True)
        demo_data = {
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "scenes": [],
            "pages": [],
            "style": {
                "gold": "#FFD23F",
                "captionColor": "#FFFFFF",
                "transition": "zoom-dissolve",
                "overlapFrames": 12
            }
        }
    else:
        with open(caption_json_path, "r", encoding="utf-8") as f:
            demo_data = json.load(f)

    # Sort scene updates by index
    scene_updates.sort(key=lambda x: x["index"])
    demo_data["scenes"] = scene_updates

    with open(caption_json_path, "w", encoding="utf-8") as f:
        json.dump(demo_data, f, indent=2, ensure_ascii=False)

    print(f"\n📦 Successfully updated scenes inside caption.json: {caption_json_path}")
    print("🎉 All avatar videos trimmed and scenes registered in caption.json!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import shutil
from pathlib import Path

def log(scene_num, msg):
    print(f"✂️ [Scene {scene_num}] {msg}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Trim Avatar Videos and Align Captions")
    parser.add_argument(
        "--project_dir", "-p",
        default=str(Path.cwd()),
        help="Path to the video project folder containing script.json (default: current directory)"
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    from config import SCRIPT_JSON_PATH
    script_path = SCRIPT_JSON_PATH
    
    if not script_path.exists():
        print(f"❌ script.json not found in project directory: {project_dir}")
        sys.exit(1)

    # 1. Load dialogues
    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)
    
    segments = script_data.get("segments", [])
    if not segments:
        print("❌ No segments found in script.json.")
        sys.exit(1)

    from config import REMOTION_AVATAR_DIR, RAPID_EDIT_SCRIPT_PATH
    avatar_dir = REMOTION_AVATAR_DIR
    rapid_edit_script = RAPID_EDIT_SCRIPT_PATH
    
    all_pages = []
    scene_updates = []

    # 2. Process each scene
    for seg in segments:
        scene_num = seg["scene"]
        dialogue = seg["narration"]
        
        raw_video = avatar_dir / f"scene_{scene_num}.mp4"
        clean_video = avatar_dir / f"scene_{scene_num}_clean.mp4"
        intervals_json_path = project_dir / "project" / "intervals" / f"scene_{scene_num}_intervals.json"
        
        if not raw_video.exists():
            log(scene_num, f"❌ Raw video not found: {raw_video}")
            continue

        if not intervals_json_path.exists():
            log(scene_num, f"❌ Intervals JSON not found: {intervals_json_path}")
            continue

        # Load intervals
        with open(intervals_json_path, "r", encoding="utf-8") as f:
            intervals_data = json.load(f)
        
        # In case the key is active_keep_intervals
        intervals = intervals_data.get("active_keep_intervals", [])
        if not intervals:
            log(scene_num, "❌ No active_keep_intervals key in intervals JSON.")
            continue

        log(scene_num, f"Trimming video with intervals: {intervals}")

        # Write temp config specifically formatted for rapid_edit.py
        temp_config_path = project_dir / "project" / f"temp_intervals_config_{scene_num}.json"
        with open(temp_config_path, "w", encoding="utf-8") as f:
            json.dump({"intervals": intervals}, f)

        # Run silence trimmer
        try:
            subprocess.run([
                "python3", rapid_edit_script,
                "-path", str(raw_video),
                "-out", str(clean_video),
                "-config", str(temp_config_path)
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log(scene_num, f"❌ Trimming failed: {e}")
            log(scene_num, f"Stderr: {e.stderr}")
            continue
        finally:
            if temp_config_path.exists():
                temp_config_path.unlink()

        # Replace raw video with clean video
        if clean_video.exists():
            raw_video.unlink()
            shutil.move(str(clean_video), str(raw_video))
            log(scene_num, "Trimming complete! Clean video saved.")

        # Get duration of clean video
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(raw_video)
        ]
        try:
            duration_s = float(subprocess.check_output(ffprobe_cmd).decode().strip())
        except Exception as e:
            log(scene_num, f"⚠️ Failed to get duration: {e}")
            duration_s = 5.0 # fallback
            
        clean_duration_ms = int(duration_s * 1000)

        # Call Gemini MCP for precise word-by-word alignment on clean video
        log(scene_num, "Aligning word-by-word captions on clean video...")
        prompt = f"""You are a precise audio-to-text forced aligner. The attached video contains a clean Hindi narration.
The exact spoken text is (Devanagari, in order):

{dialogue}

Your task:
1. Listen to the audio and report the start and end times of each word in seconds relative to the beginning of the video (which starts at 0.00s).

STRICT RULES:
- Output one entry per word of the text above, in the SAME order. Do not skip, merge, or add words.
- Reply with ONLY valid JSON, no commentary, no markdown fences:

{{
  "words": [
    {{"w": "शब्द", "start": 0.05, "end": 0.45}},
    ...
  ]
}}"""

        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "chat",
                "arguments": {
                    "prompt": prompt,
                    "ref_video_path": str(raw_video)
                }
            }
        }

        try:
            from config import GEMINI_MCP_CMD
            proc = subprocess.run(
                GEMINI_MCP_CMD,
                input=json.dumps(request_data),
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            log(scene_num, f"❌ Gemini MCP failed: {e}")
            continue

        # Parse output
        stdout_lines = proc.stdout.strip().split("\n")
        json_response = None
        for line in stdout_lines:
            if line.startswith("{") and line.endswith("}"):
                try:
                    json_response = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        if not json_response or "result" not in json_response:
            log(scene_num, "❌ Failed to parse response from Gemini MCP.")
            continue

        result = json_response["result"]
        content = ""
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text":
                    content += item.get("text", "")
        
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            align_data = json.loads(content)
        except json.JSONDecodeError as e:
            log(scene_num, f"❌ Failed to parse Gemini response as JSON: {e}")
            log(scene_num, f"Raw response: {content}")
            continue

        words = align_data.get("words", [])
        
        # Build Remotion tokens
        tokens = []
        for w in words:
            w_start_ms = max(0, int(w["start"] * 1000))
            w_end_ms = min(clean_duration_ms, int(w["end"] * 1000))
            tokens.append({
                "text": w["w"],
                "startMs": w_start_ms,
                "endMs": w_end_ms
            })

        page_entry = {
            "text": dialogue,
            "startMs": 0,
            "endMs": clean_duration_ms,
            "tokens": tokens
        }
        all_pages.append((scene_num, page_entry, clean_duration_ms))
        
        duration_frames = int(duration_s * 30)
        scene_updates.append({
            "index": scene_num,
            "brollSrc": f"broll/scene_{scene_num}.mp4",
            "avatarSrc": f"avatar/scene_{scene_num}.mp4",
            "durationInFrames": duration_frames,
            "playbackRate": 1.0
        })
        log(scene_num, f"✅ Done! Clean duration: {duration_s:.2f}s ({duration_frames} frames)")

    # 3. Compile global props/caption.json
    print("\n📦 Compiling global caption.json props...")
    
    fps = 30
    overlap_frames = 12
    overlap_ms = int((overlap_frames / fps) * 1000)

    global_time_ms = 0
    final_pages = []
    
    all_pages.sort(key=lambda x: x[0])
    scene_updates.sort(key=lambda x: x["index"])

    for i, (scene_num, page, duration_ms) in enumerate(all_pages):
        # Shift start time back by transition overlap for subsequent scenes
        if i > 0:
            global_time_ms -= overlap_ms

        shifted_page = {
            "text": page["text"],
            "startMs": global_time_ms,
            "endMs": global_time_ms + duration_ms,
            "tokens": []
        }
        for token in page["tokens"]:
            shifted_page["tokens"].append({
                "text": token["text"],
                "startMs": global_time_ms + token["startMs"],
                "endMs": global_time_ms + token["endMs"]
            })
        final_pages.append(shifted_page)
        global_time_ms += duration_ms

    demo_data = {
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "scenes": scene_updates,
        "pages": final_pages,
        "style": {
            "gold": "#FFD23F",
            "captionColor": "#FFFFFF",
            "transition": "zoom-dissolve",
            "overlapFrames": 12
        }
    }

    from config import REMOTION_CAPTION_JSON_PATH
    demo_json_path = REMOTION_CAPTION_JSON_PATH
    with open(demo_json_path, "w", encoding="utf-8") as f:
        json.dump(demo_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully compiled and updated: {demo_json_path}")
    print("🎉 All avatar videos trimmed and captions aligned perfectly!")

if __name__ == "__main__":
    main()

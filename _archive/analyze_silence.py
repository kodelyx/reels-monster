#!/usr/bin/env python3
import json
import httpx
import sys
import re
import argparse
from pathlib import Path

def clean_json_response(text):
    # Strip markdown code fences if present
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = text.strip()
    return text

def main():
    parser = argparse.ArgumentParser(description="Speech Interval Detection with ChatGPT Free API")
    parser.add_argument(
        "--project_dir", "-p",
        default=str(Path.cwd()),
        help="Path to the video project folder (default: current directory)"
    )
    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()

    from config import CHATGPT_SERVER_URL

    prompt = """You are an audio speech detector. You receive an audio file. Return ONLY the time intervals where real speech exists.

REMOVE these from output:
- Silence, dead air, long pauses
- Filler sounds: "aa", "umm", "uhh", "hmm", "uh-huh"
- Leading silence before first word
- Trailing silence after last word
- Throat clearing, lip smacking, non-speech noise

RULES:
- Never cut inside a word. Cut between words only.
- Keep 0.05-0.10s safety margin before/after each speech segment.
- If gap between two speech segments < 0.20s, merge them into one interval.
- Keep natural micro-pauses that make speech sound human.
- Start from first real spoken word.
- Intervals must be in chronological order.

OUTPUT:
- ONLY valid JSON. Nothing else.
- No markdown. No code fences. No explanation. No extra text.
- Response starts with { and ends with }

FORMAT:
{
  "total_duration": 10.50,
  "active_keep_intervals": [
    [0.52, 2.10],
    [2.28, 3.65],
    [4.10, 7.82],
    [8.05, 10.20]
  ]
}"""
    from config import SCRIPT_JSON_PATH
    
    if not SCRIPT_JSON_PATH.exists():
        print(f"❌ script.json not found: {SCRIPT_JSON_PATH}")
        sys.exit(1)
        
    with open(SCRIPT_JSON_PATH, "r", encoding="utf-8") as f:
        script_data = json.load(f)
        
    segments = script_data.get("segments", [])
    if not segments:
        print("❌ No segments found in script.json.")
        sys.exit(1)
        
    temp_dir = project_dir / "project"
    temp_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = temp_dir / "avatar_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_dir = temp_dir / "intervals"
    output_dir.mkdir(parents=True, exist_ok=True)

    chatgpt_api_url = f"{CHATGPT_SERVER_URL}/api/chat/edit"
    conversation_ids = {}

    print(f"🚀 Starting speech interval detection with ChatGPT Free API for {len(segments)} scenes...")
    
    for seg in segments:
        scene_num = seg["scene"]
        audio_file = audio_dir / f"scene_{scene_num}.mp3"
        raw_video = project_dir / "project" / "avatar" / f"scene_{scene_num}.mp4"
        
        # Auto-extract audio from MP4 if MP3 is missing
        if not audio_file.exists():
            if raw_video.exists():
                print(f"🎵 Scene {scene_num}: Extracting audio from raw video {raw_video.name}...")
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(raw_video),
                        "-vn", "-acodec", "libmp3lame", str(audio_file)
                    ], check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    print(f"❌ Scene {scene_num}: Failed to extract audio: {e.stderr.decode('utf-8')}")
                    continue
            else:
                print(f"⚠️ Scene {scene_num}: Neither audio nor raw video found!")
                continue

        print(f"\n🎙️ Scene {scene_num}: Sending {audio_file.name} to ChatGPT...")

        try:
            with open(audio_file, "rb") as f:
                resp = httpx.post(
                    chatgpt_api_url,
                    data={
                        "prompt": prompt,
                        "conversation_id": "new"
                    },
                    files={"image": (audio_file.name, f, "audio/mp3")},
                    timeout=300
                )
            
            if resp.status_code != 200:
                print(f"❌ Scene {scene_num}: API Error {resp.status_code}: {resp.text}")
                continue

            res_data = resp.json()
            raw_text = res_data.get("response", "")
            conv_id = res_data.get("conversation_id", "")
            
            if conv_id:
                conversation_ids[str(scene_num)] = conv_id
            
            # Save raw AI response for debugging
            raw_output_path = output_dir / f"scene_{scene_num}_raw_ai.txt"
            raw_output_path.write_text(raw_text, encoding="utf-8")
            
            clean_text = clean_json_response(raw_text)
            try:
                interval_data = json.loads(clean_text)
                
                # Save parsed intervals JSON
                out_path = output_dir / f"scene_{scene_num}_intervals.json"
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(interval_data, out_f, indent=2, ensure_ascii=False)
                
                print(f"✅ Scene {scene_num}: Done! Saved to: {out_path}")
                print(f"   Keep Intervals: {interval_data.get('active_keep_intervals', [])}")
            except Exception as parse_err:
                print(f"⚠️ Scene {scene_num}: Failed to parse JSON from AI response: {parse_err}")
                print(f"   Raw text saved to: {raw_output_path}")

        except Exception as e:
            print(f"❌ Scene {scene_num}: Request failed: {e}")

    # Save conversation IDs mapping for align_captions_chatgpt.py
    conv_ids_path = temp_dir / "scripting" / "conversation_ids.json"
    conv_ids_path.parent.mkdir(parents=True, exist_ok=True)
    with open(conv_ids_path, "w", encoding="utf-8") as f:
        json.dump(conversation_ids, f, indent=2)
    print(f"\n📦 Saved all conversation IDs to: {conv_ids_path}")
    print("\n🎉 Silence analysis loop complete!")

if __name__ == "__main__":
    import subprocess
    main()

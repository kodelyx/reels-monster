#!/usr/bin/env python3
"""
normalize_avatar_audio.py — Normalizes the audio tracks of all avatar videos in-place 
to a standard loudness of -14.0 LUFS using FFmpeg's loudnorm filter.
Uses video copy (-c:v copy) to prevent video quality degradation and run instantly.
"""

import subprocess
import os
import sys
from pathlib import Path

AVATAR_DIR = Path("/Users/akash/My-work/reel-factory/remotion/public/avatar")

def normalize_file(file_path: Path):
    temp_path = file_path.with_name(f"{file_path.stem}_temp.mp4")
    print(f"🎙️ Normalizing: {file_path.name}...")
    
    # Run ffmpeg with loudnorm filter, target integrated loudness = -14.0 LUFS, true peak = -1.0 dB
    cmd = [
        "ffmpeg", "-y",
        "-i", str(file_path),
        "-filter_complex", "[0:a]loudnorm=I=-14:TP=-1.0[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        str(temp_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Replace original with normalized temp file
        file_path.unlink()
        temp_path.rename(file_path)
        print(f"✅ Normalized successfully: {file_path.name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to normalize {file_path.name}: {e.stderr.decode()}", file=sys.stderr)
        if temp_path.exists():
            temp_path.unlink()

def main():
    if not AVATAR_DIR.exists():
        print(f"❌ Avatar directory not found: {AVATAR_DIR}")
        sys.exit(1)
        
    avatar_files = sorted(AVATAR_DIR.glob("scene_*.mp4"))
    if not avatar_files:
        print("❌ No scene_*.mp4 files found in avatar directory.")
        sys.exit(1)
        
    for f in avatar_files:
        normalize_file(f)
        
    print("\n🎉 All avatar voice files normalized to -14.0 LUFS standard loudness!")

if __name__ == "__main__":
    main()

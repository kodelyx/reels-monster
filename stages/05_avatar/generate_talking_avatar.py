#!/usr/bin/env python3
"""
Talking Avatar Video Generator
Generates a talking avatar video using the Flow MCP API (Docker/OrbStack).
Uses Akash's avatar image as the starting frame reference.
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# === CONFIG (endpoints via core.config; paths are project-relative) ===
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    from core.config import PATHS, load_config, flow_api_url
    _paths = PATHS(Path(__file__).resolve().parents[2])
    FLOW_API_URL = flow_api_url(load_config(_paths.ROOT))
    AVATAR_IMAGE = str(_paths.AVATAR_IMAGE)
    DEFAULT_OUTPUT_DIR = str(_paths.AVATAR)
except Exception:
    FLOW_API_URL = "http://localhost:8001"
    AVATAR_IMAGE = ""
    DEFAULT_OUTPUT_DIR = "."
PROMPT_TEMPLATE = """Use the uploaded avatar image as the exact identity reference. Create a highly realistic 10-second talking avatar video.

Keep the person exactly the same as the reference image: same face, same skin tone, same hairstyle, same hairline, same eyes, same eyebrows, same nose, same lips, same mustache, same beard line, same jaw shape, same shirt, same sitting posture, same body size, and same professional indoor background.

The video must look like a real human recording, not an AI avatar.

The person must look completely real, like an actual camera recording. Natural skin texture, visible pores, slight asymmetry, micro-imperfections, realistic eyes, natural lips, no AI-smooth face.

Background:
Keep the EXACT same background as the reference image. Do NOT change, replace, redesign, or add anything to the background. The room, walls, furniture, lighting, colors, objects — everything behind the person must remain identical to the uploaded reference image. No new props, no new lights, no new setup.

Lighting:
Keep lighting exactly as it appears in the reference image. Do NOT change brightness, color temperature, shadows, or add new light sources.

Camera:
Keep the same framing, angle, and composition as the reference image. Stable camera, no movement.

--- DIALOGUE ---

{{DIALOGUE}}

--- MOTION ---
Animate only natural human speaking movement:
realistic Hindi lip-sync,
natural mouth movement,
soft eye blinking,
very subtle head nod,
very subtle shoulder movement,
slight breathing,
natural hand gestures according to the dialogue,
direct eye contact with camera,
calm confident expression.

Hand movement must look real and minimal, like a real person casually explaining something on camera. Do not over-animate the hands. Do not create extra fingers. Do not distort the fingers, palms, arms, or shoulders. Keep hand movement smooth, natural, and synced with the dialogue.

--- AUDIO ---
Natural Indian male Hindi voice, clear, confident, friendly, normal-slow pace, slight breathing, accurate lip sync, no robotic voice, no overacting.

--- STYLE ---
Ultra realistic, high detail, cinematic, DSLR quality, real human recording look. The final output must be indistinguishable from a real human recording.

--- IMPORTANT ---
Do NOT add fake smile.
Do NOT add plastic skin.
Do NOT beautify the face.
Do NOT change the face.
Do NOT change the skin tone.
Do NOT change the hairstyle or hairline.
Do NOT change the eyes, eyebrows, nose, lips, jaw shape, beard, or mustache.
Do NOT change body shape.
Do NOT change shirt or outfit.
Do NOT change sitting posture.
Do NOT change the background in any way.
Do NOT change the room, walls, furniture, or any background element.
Do NOT add random objects.
Do NOT add fake office props.
Do NOT add new lights or change existing lighting.
Do NOT redesign or replace the environment.
Do NOT add text overlay.
Do NOT add captions or subtitles.
Do NOT add watermark.
Do NOT add logo.
Do NOT make hands robotic.
Do NOT overuse hand gestures.
Do NOT distort fingers or hands.
Keep the identity, background, posture, and overall look exactly the same as the uploaded reference image.

--- NEGATIVE ---
cartoon, anime, CGI, fake skin, plastic face, waxy face, glossy skin, over-smooth skin, beautified face, changed identity, changed beard, changed mustache, changed hairstyle, changed body shape, changed background, different room, different environment, new furniture, new props, redesigned background, distorted face, distorted hands, extra fingers, missing fingers, twisted fingers, robotic hands, unnatural hand motion, distorted arms, distorted mouth, bad lip sync, robotic motion, artificial lighting, changed lighting, fake smile, blurry, over-sharp, random objects, fake props, text, captions, subtitles, watermark, logo.

Make the final output indistinguishable from a real human recording."""


def log(msg):
    print(f"[talking-avatar] {msg}", file=sys.stderr)


def check_credits():
    """Check remaining Flow credits."""
    try:
        req = urllib.request.Request(f"{FLOW_API_URL}/v1/credits")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("credits", 0)
    except Exception as e:
        log(f"Credits check failed: {e}")
        return -1


def load_image_base64(path):
    """Read image file and return data URI base64 string."""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def build_prompt(dialogue):
    """Inject dialogue into prompt template."""
    return PROMPT_TEMPLATE.replace("{{DIALOGUE}}", dialogue)


def generate_video(prompt, image_b64, aspect="landscape", duration=6):
    """Call Flow API to generate video. Returns video URL or raises."""
    payload = {
        "prompt": prompt,
        "aspect": aspect,
        "n": 1,
        "duration": duration,
        "image_base64": image_b64,
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{FLOW_API_URL}/v1/videos/generations",
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    log("Sending video generation request to Flow API...")
    log("This may take 5-10 minutes. Please wait...")

    with urllib.request.urlopen(req, timeout=700) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Flow API error: HTTP {resp.status}")
        res_data = json.loads(resp.read().decode("utf-8"))

    videos = res_data.get("data", [])
    if not videos:
        raise RuntimeError("No video returned by Flow API.")

    return videos[0]["url"]


def download_video(url, output_path):
    """Download video from URL to local file."""
    log(f"Downloading video to {output_path} ...")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(output_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    log(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a talking avatar video using Flow MCP API"
    )
    parser.add_argument(
        "--dialogue", "-d",
        required=True,
        help="The dialogue text the avatar should speak (Hindi/English)"
    )
    parser.add_argument(
        "--aspect", "-a",
        choices=["landscape", "portrait"],
        default="landscape",
        help="Video aspect ratio (default: landscape)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for saved video (default: Avatar folder)"
    )
    parser.add_argument(
        "--avatar", 
        default=AVATAR_IMAGE,
        help=f"Path to avatar image (default: {AVATAR_IMAGE})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated prompt without calling the API"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=6,
        help="Video duration in seconds (default: 6)"
    )
    args = parser.parse_args()

    # Boot the bundled Flow server on-demand (Python/FastAPI via uv; no Docker).
    # Skip for --dry-run (no API needed). No-op if the bundle isn't present.
    if not args.dry_run and "_paths" in globals():
        try:
            from core import flow_server
            from core.config import flow_server_dir, load_config as _lc
            _cfg = _lc(_paths.ROOT)
            if flow_server_dir(_cfg):
                flow_server.ensure_server(_cfg)
        except Exception as e:
            print(f"⚠️  Flow server not auto-started: {str(e)[:80]}", file=sys.stderr)

    # Validate avatar image
    if not os.path.exists(args.avatar):
        print(f"ERROR: Avatar image not found: {args.avatar}", file=sys.stderr)
        sys.exit(1)

    # Build prompt
    prompt = build_prompt(args.dialogue)

    if args.dry_run:
        print("=== DRY RUN — Generated Prompt ===")
        print(prompt)
        print("=== END ===")
        sys.exit(0)

    # Check credits
    credits = check_credits()
    if credits == 0:
        print("ERROR: No Flow credits remaining.", file=sys.stderr)
        sys.exit(1)
    elif credits > 0:
        log(f"Flow credits available: {credits}")

    # Load avatar image
    log(f"Loading avatar image: {args.avatar}")
    image_b64 = load_image_base64(args.avatar)

    # Generate video
    try:
        video_url = generate_video(prompt, image_b64, args.aspect, args.duration)
    except Exception as e:
        print(f"ERROR: Video generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    log(f"Video generated! URL: {video_url}")

    # Download video
    output_dir = args.output or DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"talking_avatar_{timestamp}.mp4"
    output_path = os.path.join(output_dir, filename)

    try:
        download_video(video_url, output_path)
    except Exception as e:
        print(f"ERROR: Download failed: {e}", file=sys.stderr)
        print(f"VIDEO_URL: {video_url}")
        sys.exit(1)

    # Final output — this is what the AI agent reads
    print(f"VIDEO_PATH: {output_path}")
    print(f"VIDEO_URL: {video_url}")


if __name__ == "__main__":
    main()

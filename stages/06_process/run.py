#!/usr/bin/env python3
"""Stage 06 — Process avatars: silence-trim + word-level caption alignment.

For each scene: extracts audio, asks the local ChatGPT server for per-word timings
(Hinglish), trims silence with core/rapid_edit.py, and compiles the global
caption.json (scenes + karaoke pages on the global timeline) that Remotion renders.

  requires:  project/avatar/scene_N.mp4, project/scripting/script.json
  produces:  project/scripting/caption.json  { fps, width, height, scenes, pages, style }
             (also trims each avatar clip in place)

Run:  python3 stages/06_process/run.py -p /path/to/reels-monster
Migrated from reel-factory/scripts/process_avatar.py (logic unchanged; paths via core).
"""
import argparse
import json
import subprocess
import shutil
import sys
from pathlib import Path

import httpx

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, chatgpt_url

RAPID_EDIT = STAGE_DIR.parents[1] / "core" / "rapid_edit.py"

# Phonetic merge rules: consecutive Devanagari tokens that should display as one
# English term in karaoke captions (e.g. ए+आई → "AI").
MERGE_RULES = [
    (["ए", "आई", "एजेंट्स"],   "AI Agents"),
    (["ए", "आई", "एजेंट"],     "AI Agent"),
    (["ए", "आई", "टोकन्स"],    "AI Tokens"),
    (["ए", "आई", "टीम"],       "AI Team"),
    (["ए", "आई"],               "AI"),
    (["चैट", "जी", "पी", "टी"], "ChatGPT"),
    (["चैट", "जीपीटी"],         "ChatGPT"),
]


def apply_merges(tokens: list) -> list:
    """Merge consecutive tokens matching phonetic patterns (longest-first)."""
    result = []
    i = 0
    while i < len(tokens):
        matched = False
        for pattern, label in MERGE_RULES:
            n = len(pattern)
            window = [t.get("devanagari", t["text"]) for t in tokens[i:i+n]]
            if window == pattern:
                result.append({
                    "text": label,
                    "devanagari": " ".join(window),
                    "startMs": tokens[i]["startMs"],
                    "endMs": tokens[i + n - 1]["endMs"],
                })
                i += n
                matched = True
                break
        if not matched:
            result.append(tokens[i])
            i += 1
    return result

def log(scene_num, msg):
    print(f"🎙️ [Scene {scene_num}] {msg}", file=sys.stderr)


def align_scene(scene_num, dialogue, raw_video, paths, chatgpt_api_url):
    """Extract audio, get per-word timings from ChatGPT. Returns align dict or None."""
    audio_path = paths.AVATAR / f"scene_{scene_num}_audio.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_video), "-vn",
             "-acodec", "libmp3lame", "-q:a", "2", str(audio_path)],
            check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        log(scene_num, f"❌ Audio extraction failed: {e.stderr[-200:] if e.stderr else e}")
        return None

    prompt = f"""For the audio file you have in this conversation, the exact spoken Devanagari text is:

{dialogue}

Please listen to the audio file and return the start and end times of each spoken word of that text relative to the beginning of the file.

STRICT RULES:
- Output one entry per word of the text above, in the SAME order. Do not skip, merge, or add words.
- "w" is the exact Devanagari word. "roman" is the SAME word in natural Hinglish (Roman script), the way Indians type Hindi in chat (e.g. "दुनिया"->"duniya", "क्या"->"kya"). English loanwords stay plain English ("एआई"->"AI", "रोबोट"->"robot"). No diacritics.
- "start" and "end" are seconds from the beginning of the file (decimals allowed).
- Reply with ONLY valid JSON, no commentary, no markdown fences:

{{
  "words": [
    {{"w": "शब्द", "roman": "shabd", "start": 0.05, "end": 0.45}}
  ]
}}"""

    align_data = None
    for attempt in range(1, 4):
        try:
            with open(audio_path, "rb") as audio_f:
                resp = httpx.post(
                    chatgpt_api_url,
                    data={"prompt": prompt, "conversation_id": "new"},
                    files={"image": (audio_path.name, audio_f, "audio/mp3")},
                    timeout=300)
        except Exception as e:
            log(scene_num, f"⚠️ ChatGPT request failed (try {attempt}/3): {e}")
            continue
        if resp.status_code != 200:
            log(scene_num, f"⚠️ ChatGPT API error {resp.status_code} (try {attempt}/3): {resp.text[:120]}")
            continue
        content = resp.json().get("response", "").replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            log(scene_num, f"⚠️ ChatGPT gave non-JSON (try {attempt}/3): {content[:80]}")
            continue
        words = parsed.get("words", [])
        if not words:
            log(scene_num, f"⚠️ ChatGPT returned no words (try {attempt}/3)")
            continue
        span = float(words[-1]["end"]) - float(words[0]["start"])
        n_expected = len(dialogue.split())
        # Sanity: alignment span must be plausible for the word count. ChatGPT
        # sometimes collapses timings (e.g. 16 words in 1.4s) — that would trim
        # the clip mid-narration. Reject + retry. ~0.20s/word ≈ very fast speech.
        min_span = 0.20 * n_expected
        if span < min_span:
            log(scene_num, f"⚠️ Implausible timing: {n_expected} words in {span:.2f}s "
                           f"(need ≥{min_span:.1f}s) (try {attempt}/3) — retrying")
            continue
        # Sanity: returned word entries should roughly match the dialogue length.
        if len(words) < 0.6 * n_expected:
            log(scene_num, f"⚠️ Too few words: got {len(words)}, expected ~{n_expected} "
                           f"(try {attempt}/3) — retrying")
            continue
        align_data = {"speech_start": float(words[0]["start"]),
                      "speech_end": float(words[-1]["end"]), "words": words}
        break

    audio_path.unlink(missing_ok=True)
    return align_data


def normalize_audio(video_path, scene_num):
    """Normalize avatar audio to -14.0 LUFS for consistent loudness across scenes.

    Uses ffmpeg loudnorm filter with video copy (no re-encode). Non-fatal: if
    normalization fails the original trimmed clip is kept unchanged.
    """
    temp_path = video_path.with_name(f"{video_path.stem}_norm.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-filter_complex", "[0:a]loudnorm=I=-14:TP=-1.0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        str(temp_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        video_path.unlink()
        temp_path.rename(video_path)
        log(scene_num, "🔊 Audio normalized to -14.0 LUFS")
    except subprocess.CalledProcessError as e:
        log(scene_num, f"⚠️ Audio normalization failed (non-fatal): "
                       f"{e.stderr[-200:] if e.stderr else e}")
        if temp_path.exists():
            temp_path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Stage 06 — Trim + Caption Align")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    config = load_config(paths.ROOT)
    # Boot the bundled ChatGPT bridge on-demand (native binary; no Docker). If the
    # bundle isn't present this is a no-op and we assume an external server on :9225.
    try:
        from core import chatgpt_server
        from core.config import chatgpt_server_bin
        if chatgpt_server_bin(config):
            chatgpt_server.ensure_server(config)
    except Exception as e:
        print(f"⚠️  ChatGPT server not auto-started: {str(e)[:80]}")
    chatgpt_api_url = f"{chatgpt_url(config)}/api/chat/edit"

    if not paths.SCRIPT.exists():
        print(f"❌ script.json not found: {paths.SCRIPT}")
        sys.exit(1)
    segments = json.loads(paths.SCRIPT.read_text(encoding="utf-8")).get("segments", [])
    if not segments:
        print("❌ No segments found in script.json.")
        sys.exit(1)

    all_pages = []
    scene_updates = []
    failed_scenes = []

    for seg in segments:
        scene_num = seg["scene"]
        dialogue = seg["narration"]
        raw_video = paths.AVATAR / f"scene_{scene_num}.mp4"
        clean_video = paths.AVATAR / f"scene_{scene_num}_clean.mp4"

        if not raw_video.exists():
            log(scene_num, f"❌ Raw video not found: {raw_video}")
            failed_scenes.append(scene_num)
            continue

        log(scene_num, f"Analyzing speech timing for dialogue: '{dialogue}'")
        align_data = align_scene(scene_num, dialogue, raw_video, paths, chatgpt_api_url)
        if align_data is None:
            log(scene_num, "❌ ChatGPT alignment failed after 3 tries.")
            failed_scenes.append(scene_num)
            continue

        speech_start = align_data.get("speech_start", 0)
        speech_end = align_data.get("speech_end", 6.0)
        words = align_data.get("words", [])

        # Small tail pad so accurate speech is never clipped mid-word.
        TAIL_PAD = 0.35
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(raw_video)],
                capture_output=True, text=True, timeout=30)
            clip_dur = float(probe.stdout.strip() or speech_end)
        except Exception:
            clip_dur = speech_end + TAIL_PAD
        speech_start = max(0.0, float(speech_start) - 0.05)
        speech_end = min(clip_dur, float(speech_end) + TAIL_PAD)

        log(scene_num, f"Speech detected: {speech_start}s to {speech_end}s "
                       f"(Duration: {speech_end - speech_start:.2f}s)")

        intervals_path = paths.PROJECT / f"temp_intervals_{scene_num}.json"
        intervals_path.write_text(json.dumps({"intervals": [[speech_start, speech_end]]}))

        log(scene_num, "Running rapid-edit silence trimmer...")
        try:
            subprocess.run(["python3", str(RAPID_EDIT),
                            "-path", str(raw_video), "-out", str(clean_video),
                            "-config", str(intervals_path)],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log(scene_num, f"❌ Trimming failed: {e}\nStderr: {e.stderr}")
            failed_scenes.append(scene_num)
            continue
        finally:
            intervals_path.unlink(missing_ok=True)

        if clean_video.exists():
            raw_video.unlink()
            shutil.move(str(clean_video), str(raw_video))
            log(scene_num, "✅ Trimming complete. Clean video saved!")

        # Normalize audio loudness to -14.0 LUFS (consistent volume across scenes).
        normalize_audio(raw_video, scene_num)

        trimmed_duration_ms = int((speech_end - speech_start) * 1000)
        tokens = []
        for w in words:
            w_start_ms = max(0, int((w["start"] - speech_start) * 1000))
            w_end_ms = min(trimmed_duration_ms, int((w["end"] - speech_start) * 1000))
            tokens.append({"text": (w.get("roman") or w["w"]).strip(),
                           "devanagari": w["w"],
                           "startMs": w_start_ms, "endMs": w_end_ms})

        # Merge phonetic splits: ए+आई → "AI", चैट+जी+पी+टी → "ChatGPT", etc.
        tokens = apply_merges(tokens)

        all_pages.append((scene_num,
                          {"text": dialogue, "startMs": 0,
                           "endMs": trimmed_duration_ms, "tokens": tokens},
                          trimmed_duration_ms))
        scene_updates.append({
            "index": scene_num,
            "brollSrc": f"broll/scene_{scene_num}_a.mp4",
            "brollSrc2": f"broll/scene_{scene_num}_b.mp4",
            "avatarSrc": f"avatar/scene_{scene_num}.mp4",
            "durationInFrames": int((trimmed_duration_ms / 1000) * 30),
            "playbackRate": 1.0})

    # Fail-fast: agar koi bhi scene process nahi hua to adhura caption.json mat likho.
    # Warna render silently gap ke saath toot jaata hai (missing avatar/broll refs).
    if failed_scenes:
        print(f"\n❌ Scenes failed: {sorted(set(failed_scenes))} — "
              f"caption.json NOT written (would be incomplete). Fix & re-run stage 06.")
        sys.exit(1)

    # Compile global caption.json (scene offsets applied to page/token times).
    print("\n📦 Compiling final caption.json props...")
    global_time_ms = 0
    final_pages = []
    all_pages.sort(key=lambda x: x[0])
    scene_updates.sort(key=lambda x: x["index"])

    for scene_num, page, duration_ms in all_pages:
        shifted = {"text": page["text"], "startMs": global_time_ms,
                   "endMs": global_time_ms + duration_ms, "tokens": []}
        for token in page["tokens"]:
            shifted["tokens"].append({
                "text": token["text"],
                "devanagari": token.get("devanagari", token["text"]),
                "startMs": global_time_ms + token["startMs"],
                "endMs": global_time_ms + token["endMs"]})
        final_pages.append(shifted)
        global_time_ms += duration_ms

    demo_data = {
        "fps": 30, "width": 1080, "height": 1920,
        "scenes": scene_updates, "pages": final_pages,
        "style": {"gold": "#FFD23F", "captionColor": "#FFFFFF",
                  "transition": "zoom-dissolve", "overlapFrames": 12}}

    paths.CAPTION.parent.mkdir(parents=True, exist_ok=True)
    paths.CAPTION.write_text(json.dumps(demo_data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print(f"✅ Compiled: {paths.rel(paths.CAPTION)}")
    print("🎉 All avatar videos trimmed and captions aligned!")


if __name__ == "__main__":
    main()

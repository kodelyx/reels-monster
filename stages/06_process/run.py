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
from core.config import PATHS, load_config, chatgpt_url, elevenlabs_api_key
from core import elevenlabs_align

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


def romanize_words(devanagari_words: list, keys, config, model) -> dict:
    """Map each Devanagari word → natural Hinglish (Roman) for caption display.

    Text-only AI call (NO audio) — so it's accurate and can't hallucinate timing;
    the timing already came from ElevenLabs. Returns {devanagari: roman}. On any
    failure returns {} and the caller falls back to showing Devanagari.
    """
    from core.ai_client import call_ai
    uniq = list(dict.fromkeys(w for w in devanagari_words if w.strip()))
    if not uniq:
        return {}
    listing = "\n".join(f"{i+1}. {w}" for i, w in enumerate(uniq))
    prompt = f"""Transliterate each Hindi (Devanagari) word below into natural Hinglish (Roman script), the way Indians type Hindi in chat.

RULES:
- "क्या"->"kya", "दुनिया"->"duniya", "न्यूयॉर्क"->"New York". No diacritics.
- English loanwords stay plain English ("एआई"->"AI", "रोबोट"->"robot").
- Keep numbers as words the way they're spoken ("आठ"->"aath", "सौ"->"sau").
- Reply with ONLY valid JSON: {{"map": {{"<devanagari>": "<roman>", ...}}}}

Words:
{listing}"""
    try:
        result = call_ai(keys, config, model, prompt, max_tokens=2048,
                         expect_json=True, label="romanize captions")
        mp = result.get("map", {}) if isinstance(result, dict) else {}
        return {k: str(v).strip() for k, v in mp.items() if str(v).strip()}
    except Exception as e:
        print(f"⚠️  Romanization failed (captions will show Devanagari): {str(e)[:120]}",
              file=sys.stderr)
        return {}


# Hindi filler / function words — dropped by the rule-based keyword fallback so
# only meaning-carrying words stay on screen. Not exhaustive, just the common glue.
_HINDI_STOPWORDS = {
    "के", "का", "की", "को", "है", "हैं", "कि", "से", "में", "पर", "तक", "भी",
    "और", "या", "एक", "यह", "वह", "ये", "वे", "इस", "उस", "जो", "तो", "ही",
    "था", "थे", "थी", "हो", "होता", "होती", "होते", "गया", "गयी", "गए", "रहा",
    "रही", "रहे", "ने", "कर", "करके", "लिए", "साथ", "अब", "जब", "तब", "फिर",
}

# Words that must ALWAYS stay visible even if a model/rule wants to drop them —
# negation & scope words flip the sentence's meaning ("theory नहीं, सच" → "theory
# सच" reverses it). Never hide these, in AI mode or rule mode.
_PROTECTED_WORDS = {
    "नहीं", "ना", "न", "मत", "बिना", "सिर्फ", "केवल", "कभी", "बिल्कुल", "बल्कि",
}


def select_keywords(devanagari_words: list, dialogue: str, keys, config, model) -> list:
    """Return a set of indices (into devanagari_words) that should stay visible as
    on-screen captions — the punchy keywords, not filler. Viral-reel style: 2-3
    keywords at a time instead of the full sentence.

    AI decides (understands meaning); on any failure we fall back to a rule that
    drops Hindi stopwords. Either way ALL tokens are kept in caption.json — this
    only sets each token's `show` flag, so nothing about timing/audio changes and
    a bad result at worst shows the full sentence (today's behaviour).

    Negation/scope words (_PROTECTED_WORDS) are force-kept in both paths so the
    on-screen meaning can never be reversed by hiding a "नहीं".
    """
    n = len(devanagari_words)
    if n == 0:
        return []
    protected = {i for i, w in enumerate(devanagari_words)
                 if w.strip() in _PROTECTED_WORDS}

    # Rule-based fallback (also used if AI returns nothing usable).
    def _rule():
        idxs = [i for i, w in enumerate(devanagari_words)
                if w.strip() and w.strip() not in _HINDI_STOPWORDS]
        idxs = sorted(set(idxs) | protected)
        return idxs if idxs else list(range(n))

    from core.ai_client import call_ai
    listing = "\n".join(f"{i}. {w}" for i, w in enumerate(devanagari_words))
    prompt = f"""You are a viral Hindi reel caption editor. Below is one spoken sentence, split into numbered words. On screen we show ONLY the punchy keywords (2-3 at a time), NOT the whole sentence — so viewers' eyes catch the important words as they're spoken.

SENTENCE: {dialogue}

WORDS (index. word):
{listing}

TASK: Pick the indices of the KEYWORDS to keep on screen — nouns, numbers, names, strong verbs, the emotional/surprising words. DROP filler/glue words (के, है, कि, का, को, से, तक, में, भी, और, तो, ही, etc.).
- Be PUNCHY: keep only about 40-55% of the words. When in doubt, drop it.
- NEVER drop negation/scope words (नहीं, ना, मत, बिना, सिर्फ, केवल) — hiding them REVERSES the meaning.
- Keep multi-word names/numbers together (e.g. "आठ सौ साल" → keep all three).
- Reply with ONLY valid JSON: {{"keep": [<index>, <index>, ...]}}"""
    try:
        result = call_ai(keys, config, model, prompt, max_tokens=1024,
                         expect_json=True, label="select caption keywords")
        keep = result.get("keep", []) if isinstance(result, dict) else []
        idxs = {int(i) for i in keep if isinstance(i, (int, float)) and 0 <= int(i) < n}
        idxs |= protected  # negation words are non-negotiable
        idxs = sorted(idxs)
        return idxs if idxs else _rule()
    except Exception as e:
        print(f"⚠️  Keyword selection failed (rule fallback): {str(e)[:120]}",
              file=sys.stderr)
        return _rule()


# Devanagari number-words — used to detect which tokens form a spoken number so we
# can offer them to the AI for digit conversion (e.g. आठ+सौ → "800").
_NUMBER_WORDS = {
    "शून्य", "एक", "दो", "तीन", "चार", "पांच", "पाँच", "छह", "छः", "सात", "आठ",
    "नौ", "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह",
    "अठारह", "उन्नीस", "बीस", "पच्चीस", "तीस", "पैंतीस", "चालीस", "पचास",
    "साठ", "सत्तर", "अस्सी", "नब्बे", "सौ", "हज़ार", "हजार", "लाख", "करोड़",
    "छिहत्तर", "इक्कीस", "बाईस", "तेईस", "चौबीस", "छब्बीस", "सत्ताईस", "अट्ठाईस",
    "उनतीस", "इकतीस", "बत्तीस", "अड़तीस", "उनतालीस", "इकतालीस", "पैंतालीs",
    "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास", "इक्यावन",
}


def format_numbers(tokens: list, dialogue: str, keys, config, model) -> list:
    """Turn spoken number-words into reel-friendly digits, merging the tokens that
    make up one number into a single token (timing preserved: start of first word →
    end of last). E.g. tokens आठ|सौ → one token "800" spanning both.

    AI decides the display form (digit vs word, 50K vs 50000, year vs count) because
    it understands context; only consecutive number-word runs are offered to it, so
    non-numbers are never touched. On any failure the tokens are returned unchanged
    (spoken words stay — today's behaviour), so this can only improve, never break.
    """
    if not tokens:
        return tokens
    # Find consecutive runs of number-word tokens.
    runs = []
    i = 0
    while i < len(tokens):
        dev = tokens[i].get("devanagari", "").strip().rstrip("।,.?!")
        if dev in _NUMBER_WORDS:
            j = i
            while j < len(tokens):
                d = tokens[j].get("devanagari", "").strip().rstrip("।,.?!")
                if d in _NUMBER_WORDS:
                    j += 1
                else:
                    break
            runs.append((i, j))  # [i, j)
            i = j
        else:
            i += 1
    if not runs:
        return tokens

    # Ask the AI for a digit/display form per run (spoken words + sentence context).
    from core.ai_client import call_ai
    run_desc = []
    for ri, (a, b) in enumerate(runs):
        spoken = " ".join(tokens[k].get("devanagari", "") for k in range(a, b))
        roman = " ".join(tokens[k]["text"] for k in range(a, b))
        run_desc.append(f'{ri}. spoken="{spoken}" (roman="{roman}")')
    listing = "\n".join(run_desc)
    prompt = f"""You are a viral Hindi reel caption editor. In the sentence below, some spoken number-words should be shown on screen as DIGITS — digits are read instantly, spelled-out numbers slow the viewer down.

SENTENCE: {dialogue}

NUMBER GROUPS (each is one spoken number):
{listing}

TASK: For each group, give the best on-screen DISPLAY form:
- Plain counts/measures → digits: "आठ सौ" → "800", "पैंतीस" → "35", "पच्चीस" → "25".
- Years stay full: "उन्नीस सौ छिहत्तर" → "1976", "दो हज़ार पच्चीस" → "2025".
- Big round numbers may use K/M: "पचास हज़ार" → "50K", "दस लाख" → "10L" or "1M" — whichever reads cleaner.
- Keep it faithful to what's spoken. If a group is better left as a word (e.g. "एक" meaning "a/one" not a count), return the roman as-is.
- Reply with ONLY valid JSON: {{"forms": {{"0": "800", "1": "1976", ...}}}} — key is the group index, value is the display string."""
    try:
        result = call_ai(keys, config, model, prompt, max_tokens=512,
                         expect_json=True, label="format numbers")
        forms = result.get("forms", {}) if isinstance(result, dict) else {}
    except Exception as e:
        print(f"⚠️  Number formatting failed (spoken words kept): {str(e)[:120]}",
              file=sys.stderr)
        return tokens

    # Rebuild the token list, collapsing each run into one token with its digit form.
    out = []
    consumed = {}
    for ri, (a, b) in enumerate(runs):
        consumed[a] = (b, ri)
    i = 0
    while i < len(tokens):
        if i in consumed:
            b, ri = consumed[i]
            disp = str(forms.get(str(ri), "")).strip()
            if disp:
                merged = dict(tokens[i])  # keep show/other fields of first token
                merged["text"] = disp
                merged["devanagari"] = " ".join(tokens[k].get("devanagari", "")
                                                for k in range(i, b))
                merged["startMs"] = tokens[i]["startMs"]
                merged["endMs"] = tokens[b - 1]["endMs"]
                # If ANY word in the run was a shown keyword, the digit stays shown.
                merged["show"] = any(tokens[k].get("show", True) for k in range(i, b))
                out.append(merged)
            else:
                out.extend(tokens[i:b])  # AI declined → keep spoken words
            i = b
        else:
            out.append(tokens[i])
            i += 1
    return out


def align_scene_elevenlabs(scene_num, dialogue, raw_video, paths, api_key):
    """Force-align via ElevenLabs — it actually listens to the audio and aligns it
    against our known transcript, so word timings are exact (not guessed). Returns
    an align dict {speech_start, speech_end, words:[{w,start,end}]} or None."""
    audio_path = paths.AVATAR / f"scene_{scene_num}_audio.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_video), "-vn",
             "-acodec", "libmp3lame", "-q:a", "2", str(audio_path)],
            check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        log(scene_num, f"❌ Audio extraction failed: {e.stderr[-200:] if e.stderr else e}")
        return None

    try:
        result = elevenlabs_align.align(api_key, audio_path, dialogue)
    except Exception as e:
        log(scene_num, f"⚠️ ElevenLabs alignment failed: {str(e)[:200]}")
        audio_path.unlink(missing_ok=True)
        return None
    finally:
        audio_path.unlink(missing_ok=True)

    words = result.get("words", [])
    if not words:
        return None
    return {"speech_start": float(words[0]["start"]),
            "speech_end": float(words[-1]["end"]), "words": words}


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
    ai_keys = None
    ai_model = config.get("AI_MODEL", "claude-opus-4-8")
    el_key = elevenlabs_api_key(config)
    if el_key:
        print("🎯 Word-timing: ElevenLabs Forced Alignment (accurate, listens to audio).")
    else:
        print("⚠️  No ELEVENLABS_API_KEY (secrets.env) — falling back to ChatGPT bridge word-timing.")
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
        # Prefer ElevenLabs forced-alignment (real audio → exact timing). If no key
        # or it fails, fall back to the local ChatGPT bridge (guessed timing).
        align_data = None
        if el_key:
            align_data = align_scene_elevenlabs(scene_num, dialogue, raw_video, paths, el_key)
        if align_data is None:
            align_data = align_scene(scene_num, dialogue, raw_video, paths, chatgpt_api_url)
        if align_data is None:
            log(scene_num, "❌ Alignment failed (ElevenLabs + ChatGPT).")
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

        # ElevenLabs gives Devanagari + timing but no Roman display text. Captions
        # render the Roman (Hinglish) form, so transliterate here via a text-only AI
        # call (no audio → can't hallucinate timing; timing stays ElevenLabs-exact).
        if any(not w.get("roman") for w in words):
            if ai_keys is None:
                from core.ai_client import get_api_keys
                ai_keys = get_api_keys(config)
            roman_map = romanize_words([w["w"] for w in words], ai_keys, config, ai_model)
            for w in words:
                if not w.get("roman"):
                    w["roman"] = roman_map.get(w["w"], "")

        tokens = []
        for w in words:
            w_start_ms = max(0, int((w["start"] - speech_start) * 1000))
            w_end_ms = min(trimmed_duration_ms, int((w["end"] - speech_start) * 1000))
            tokens.append({"text": (w.get("roman") or w["w"]).strip(),
                           "devanagari": w["w"],
                           "startMs": w_start_ms, "endMs": w_end_ms})

        # Merge phonetic splits: ए+आई → "AI", चैट+जी+पी+टी → "ChatGPT", etc.
        tokens = apply_merges(tokens)

        # Keyword captions: pick the punchy words to keep on screen (viral-reel
        # style) — done AFTER merges so indices match the final token list. Every
        # token stays in caption.json; we only tag each with show:true/false. The
        # renderer shows only show:true. Fail ⇒ all-true ⇒ full sentence (old look).
        if ai_keys is None:
            from core.ai_client import get_api_keys
            ai_keys = get_api_keys(config)
        keep_idxs = set(select_keywords([t["devanagari"] for t in tokens],
                                         dialogue, ai_keys, config, ai_model))
        for i, t in enumerate(tokens):
            t["show"] = i in keep_idxs

        # Reel-friendly numbers: spoken number-words → digits (आठ सौ → "800"),
        # merging their tokens into one. Runs after show flags so a shown number
        # stays shown. Fail ⇒ spoken words kept unchanged (nothing breaks).
        tokens = format_numbers(tokens, dialogue, ai_keys, config, ai_model)

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
                "endMs": global_time_ms + token["endMs"],
                "show": token.get("show", True)})
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

"""core/elevenlabs_align.py — accurate word-level timing via ElevenLabs Forced Alignment.

Stage 06 needs the exact start/end time of every spoken Devanagari word so captions
land on the right frame and silence-trim cuts at real pauses. The local ChatGPT
bridge *guesses* these times (it can be ~1s off); Gemini can't hear audio at all.

ElevenLabs Forced Alignment actually listens to the audio and aligns it against the
known transcript, returning per-word (and per-character) timings — no hallucinated
numbers. We pass our own correct Devanagari script as the transcript, so the words
are always right and only the timing comes from the model.

  align(api_key, audio_path, transcript) -> {"words": [{"w","start","end"}, ...]}

Raises on HTTP / network error so the caller can fall back to the ChatGPT bridge.
Roman (Hinglish) display text is NOT produced here — that's a separate text-only
transliteration step in stage 06 (audio is never sent for that).
"""
import json
import re
import uuid
import urllib.request
import urllib.error
from pathlib import Path

ENDPOINT = "https://api.elevenlabs.io/v1/forced-alignment"

# A real caption word must contain a letter or digit (Devanagari or ASCII). Standalone
# punctuation tokens like "—", ",", "।" get their own alignment slot from ElevenLabs
# but must NOT become karaoke words (they'd flash for ~1ms). They're dropped; the next
# real word keeps its own start time, so the natural pause is preserved.
_HAS_LETTER = re.compile(r'[\wऀ-ॿ]')


def _multipart(fields: dict, file_field: str, filename: str, data: bytes,
               content_type: str = "audio/mpeg") -> tuple:
    """Build a multipart/form-data body. Returns (body_bytes, content_type_header)."""
    boundary = "----reelsmonster" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f'{value}\r\n'.encode("utf-8"))
    parts.append(
        (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
         f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n').encode("utf-8")
        + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode("utf-8"))
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def align(api_key: str, audio_path, transcript: str, timeout: float = 180.0) -> dict:
    """Force-align `transcript` (Devanagari) against the audio file.

    Returns {"words": [{"w": <devanagari>, "start": <sec>, "end": <sec>}, ...]}
    containing only real word tokens (whitespace-only alignment slots dropped).
    Raises RuntimeError on any API/parse failure.
    """
    audio = Path(audio_path).read_bytes()
    body, ctype = _multipart(
        {"text": transcript}, "file", Path(audio_path).name, audio)
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"xi-api-key": api_key, "Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            obj = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"ElevenLabs HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"ElevenLabs request failed: {str(e)[:200]}")

    raw = obj.get("words") or []
    words = []
    for w in raw:
        text = (w.get("text") or "").strip()
        if not text:  # ElevenLabs emits whitespace slots between words — skip them
            continue
        if not _HAS_LETTER.search(text):
            # Punctuation-only token (e.g. "—", "।"): drop it — it must not become a
            # karaoke word. The next real word keeps its own start, so the pause holds.
            continue
        words.append({"w": text,
                      "start": float(w["start"]),
                      "end": float(w["end"])})
    if not words:
        raise RuntimeError(f"ElevenLabs returned no words: {str(obj)[:200]}")
    return {"words": words}

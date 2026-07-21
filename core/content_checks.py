"""core/content_checks.py — deterministic, content-level gate per stage.

The contract layer only proves a file EXISTS and is non-empty. The AI QC layer
judges loosely from summary facts. Neither caught the title silently dropping out
of the render, because the file was present and "structurally sane" — the missing
piece was a specific FIELD nobody asserted on.

This module adds hard, code-level assertions on the ACTUAL CONTENT a stage must
produce, run BEFORE the stage is marked done and handed to the next one. No AI, no
guessing: if the thing that must be there isn't, the stage FAILS loudly.

Each check returns (ok: bool, problems: list[str]). A stage with no check passes
trivially. Add a stage's key requirements here as they're discovered.
"""
import json


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check_caption_has_title(paths) -> tuple:
    """caption.json must carry style.title so the studio AND render show it.

    This is the exact gap that shipped a title-less video: the render read a
    caption whose style.title was absent and silently rendered no headline.
    """
    problems = []
    cap = paths.CAPTION
    if not cap.exists():
        return False, [f"caption.json missing at {cap}"]
    try:
        data = _load_json(cap)
    except Exception as e:
        return False, [f"caption.json unreadable: {str(e)[:80]}"]

    title = data.get("style", {}).get("title")
    # A title MUST exist if any source produced one. If no source has a title at
    # all, we don't invent a failure — but if a source HAS one and it didn't make
    # it into the caption, that's the silent-drop bug we're guarding against.
    from core.title import resolve_title_text
    expected = resolve_title_text(paths)
    if expected and not title:
        problems.append(
            f"style.title is MISSING but a headline exists ('{expected}') — "
            f"it would render/preview with no title (studio↔render mismatch).")
    elif expected and isinstance(title, list) and len(title) == 0:
        problems.append("style.title is an empty list — headline would not render.")
    return (len(problems) == 0), problems


def _check_popups_present(paths) -> tuple:
    """Every scene should have a popup block (stage 07's whole job)."""
    problems = []
    cap = paths.CAPTION
    if not cap.exists():
        return False, [f"caption.json missing at {cap}"]
    data = _load_json(cap)
    scenes = data.get("scenes", [])
    missing = [s.get("index", i) for i, s in enumerate(scenes) if not s.get("popup")]
    if missing:
        problems.append(f"{len(missing)} scene(s) have no popup: {missing}")
    return (len(problems) == 0), problems


def _check_music_not_silent(paths) -> tuple:
    """bg_music.mp3 must be REAL audio, not the silent fallback.

    Stage 09 writes a silent placeholder (+ project/music/_PLACEHOLDER.txt) when
    Gemini music is unavailable, so a music outage never blocks the render. That
    is fine as a stop-gap, but it must NOT pass silently as 'music done' — the
    exact bug that shipped a video with no background bed. We flag it as a
    WARNING-level failure so the operator re-runs stage 09 once cookies are live.
    """
    problems = []
    mp3 = paths.BG_MUSIC
    if not mp3.exists():
        return False, [f"bg_music.mp3 missing at {mp3}"]

    placeholder = paths.MUSIC / "_PLACEHOLDER.txt"
    if placeholder.exists():
        problems.append(
            "bg_music.mp3 is the SILENT placeholder (Gemini music was unavailable) — "
            "re-run stage 09 with live cookies for a real track.")
        return False, problems

    # No placeholder marker, but verify the track actually carries sound.
    import shutil, subprocess
    if shutil.which("ffmpeg"):
        try:
            out = subprocess.run(
                ["ffmpeg", "-i", str(mp3), "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, timeout=30)
            log = out.stderr
            for line in log.splitlines():
                if "mean_volume" in line:
                    try:
                        db = float(line.split("mean_volume:")[1].split("dB")[0].strip())
                        if db < -70:  # effectively silent
                            problems.append(
                                f"bg_music.mp3 is effectively silent (mean {db} dB) — "
                                f"re-run stage 09 for a real track.")
                    except (IndexError, ValueError):
                        pass
        except Exception:
            pass  # ffmpeg probe best-effort; never crash the gate
    return (len(problems) == 0), problems


# Stage-name → list of check callables. Only stages with real content invariants
# need entries; everything else passes trivially.
CHECKS = {
    "07_popups": [_check_caption_has_title, _check_popups_present],
    "09_music": [_check_music_not_silent],
    # The render reads the same caption; assert the title is there before we ship.
    "10_render": [_check_caption_has_title],
}


def verify(stage: str, paths) -> tuple:
    """Run every content check registered for `stage`.

    Returns (ok, problems). Unknown/uncovered stages pass with an empty list.
    """
    checks = CHECKS.get(stage, [])
    problems = []
    for fn in checks:
        try:
            ok, probs = fn(paths)
            if not ok:
                problems.extend(probs)
        except Exception as e:
            problems.append(f"{fn.__name__} crashed: {str(e)[:80]}")
    return (len(problems) == 0), problems

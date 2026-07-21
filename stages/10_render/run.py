#!/usr/bin/env python3
"""Stage 10 — Remotion render.

Ensures remotion/public symlinks point at the current project media, then renders
the split-screen composite (B-roll + avatar + karaoke captions + popups + music)
with Bun, driven by caption.json.

  requires:  project/scripting/caption.json, project/music/bg_music.mp3,
             project/avatar/*, project/broll/*
  produces:  output/final.mp4

Run:  python3 stages/10_render/run.py -p /path/to/reels-monster
New thin wrapper around the `bunx remotion render` command from reel-factory's README
(the old flow ran it by hand). Logic = same command, paths via core.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parents[1]))
from core.config import PATHS, load_config, kie_api_key, endcard_seconds, ai_model, endcard_handle
from core.ai_client import log
from core.title import resolve_title_words, resolve_title_text
from core.promptlib import fill
from core import kie_image

# Bundled watermark-remover binary (vendor/Watermark-remover/Watermark-remover).
# Cleans transparent Veo/Flow watermarks off the generated avatar & b-roll clips
# before Remotion renders them. Path is relative to the package root, not cwd.
WATERMARK_BIN = STAGE_DIR.parents[1] / "vendor" / "Watermark-remover" / "Watermark-remover"

# public/ symlink → project source (so Remotion always sees fresh media).
# NOTE: only *directories* are symlinked — Remotion's dev server serves those.
# A symlinked *file* (bg_music.mp3) 404s, so that one is copied in below.
# Avatar/broll point at the *_clean* dirs (watermark-removed copies); the
# originals in project/avatar & project/broll stay untouched.
LINKS = {
    "avatar": Path("..") / ".." / "project" / "avatar_clean",
    "broll": Path("..") / ".." / "project" / "broll_clean",
    "sfx": Path("..") / ".." / "sfx",
}


def clean_watermarks(paths: PATHS):
    """Watermark-remove every avatar & b-roll clip into the *_clean dirs.

    Originals (project/avatar, project/broll) are NEVER modified — the cleaned
    copies go to project/avatar_clean & project/broll_clean, which is what
    Remotion renders from. If a clean looks wrong, delete the *_clean file and
    re-run; the source clip is always safe. A clip is only re-cleaned when its
    source is newer than the existing clean (mtime check), so re-renders are fast.

    No-op (with a warning) if the binary is missing, so the render still works —
    it just renders the originals (public symlinks fall back below).
    """
    if not WATERMARK_BIN.exists():
        log(f"   ⚠️  Watermark-remover binary not found ({WATERMARK_BIN}); "
            f"rendering ORIGINALS (watermarks may show).")
        return False

    pairs = [(paths.AVATAR, paths.AVATAR_CLEAN), (paths.BROLL, paths.BROLL_CLEAN)]
    cleaned = skipped = 0
    for src_dir, dst_dir in pairs:
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            continue
        for src in sorted(src_dir.glob("*.mp4")):
            dst = dst_dir / src.name
            # Skip if a fresh clean already exists (source not newer than clean).
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                skipped += 1
                continue
            proc = subprocess.run(
                [str(WATERMARK_BIN), "-i", str(src), "-o", str(dst)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0 or not dst.exists():
                # Clean failed → fall back to the original for THIS clip so the
                # render never breaks (original copied verbatim, no watermark
                # removal for it).
                shutil.copyfile(src, dst)
                log(f"   ⚠️  clean failed for {src.name}; copied original instead.")
            else:
                cleaned += 1
    log(f"   🧹 Watermarks removed: {cleaned} cleaned, {skipped} up-to-date "
        f"(originals untouched in project/avatar & project/broll).")
    return True


def ensure_symlinks(paths: PATHS):
    public = paths.REMOTION / "public"
    public.mkdir(parents=True, exist_ok=True)
    # avatar/broll normally point at the *_clean dirs, but if a clean dir is
    # missing or empty (binary absent, clean skipped) fall back to the ORIGINAL
    # so the render still has media. Everything else uses the static LINKS map.
    fallbacks = {
        "avatar": (paths.AVATAR_CLEAN, Path("..") / ".." / "project" / "avatar"),
        "broll": (paths.BROLL_CLEAN, Path("..") / ".." / "project" / "broll"),
    }
    for name, target in LINKS.items():
        if name in fallbacks:
            clean_dir, orig_rel = fallbacks[name]
            if not clean_dir.exists() or not any(clean_dir.glob("*.mp4")):
                target = orig_rel  # clean empty → render originals
                log(f"   ↩︎  {name}: clean dir empty, symlinking ORIGINALS.")
        link = public / name
        if link.exists() or link.is_symlink():
            if link.is_symlink() or link.is_file():
                link.unlink()
            else:  # a real directory (shouldn't happen) — leave it
                continue
        link.symlink_to(target)
    # bg_music.mp3 must be a real file, not a symlink (Remotion won't serve a
    # symlinked file — it 404s). Copy the current track in.
    music_dst = public / "bg_music.mp3"
    if paths.BG_MUSIC.exists():
        if music_dst.exists() or music_dst.is_symlink():
            music_dst.unlink()
        shutil.copyfile(paths.BG_MUSIC, music_dst)
    # caption.json → props (Remotion reads it via --props too, but keep the link fresh)
    props = paths.REMOTION / "props" / "caption.json"
    props.parent.mkdir(parents=True, exist_ok=True)
    if props.exists() or props.is_symlink():
        props.unlink()
    props.symlink_to(Path("..") / ".." / "project" / "scripting" / "caption.json")


def popups_enabled(config: dict) -> bool:
    """ENABLE_POPUPS toggle from config.env / env. Default ON (back-compat).

    Set ENABLE_POPUPS=false (or 0/no/off) to render WITHOUT the icon popups —
    without re-running stage 07. The popup data stays untouched in caption.json;
    we just render from a popup-stripped copy, so flipping it back to true and
    re-rendering brings the icons straight back (no AI cost).
    """
    val = str(config.get("ENABLE_POPUPS", "true")).strip().lower()
    return val not in ("false", "0", "no", "off")


def sfx_enabled(config: dict) -> bool:
    """ENABLE_SFX toggle from config.env / env. Default OFF.

    Popup cards trigger sound effects (shine, boom, alert, impact, chime) that
    play ON TOP of the avatar voice + bg music. Many users find these extra
    sounds distracting, so SFX default to OFF: the visual popup cards still
    render, only their audio is dropped. Set ENABLE_SFX=true to bring them back.
    """
    val = str(config.get("ENABLE_SFX", "false")).strip().lower()
    return val in ("true", "1", "yes", "on")


def build_render_caption(paths: PATHS, keep_popups: bool, keep_sfx: bool) -> Path:
    """Return the caption path to render from.

    Popups ON  → the real caption.json (unchanged), unless SFX is OFF in which
                 case a sibling copy with every scene's popup.sfx emptied.
    Popups OFF → a sibling caption.no_popups.json with every scene's `popup`
    field removed. The original is never modified. SFX ride on popups, so
    dropping popup drops their sfx too (BG-music ducking reads the same field,
    so it stays consistent automatically).
    """
    if not keep_popups:
        data = json.loads(paths.CAPTION.read_text(encoding="utf-8"))
        stripped = 0
        for scene in data.get("scenes", []):
            if scene.pop("popup", None) is not None:
                stripped += 1
        out = paths.CAPTION.parent / "caption.no_popups.json"
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"   🚫 Popups OFF (ENABLE_POPUPS=false) — stripped {stripped} scene(s); "
            f"rendering from {paths.rel(out)} (caption.json untouched).")
        return out

    if keep_sfx:
        return paths.CAPTION

    # Popups ON but SFX OFF: keep the visual cards, drop only the sound effects.
    data = json.loads(paths.CAPTION.read_text(encoding="utf-8"))
    muted = 0
    for scene in data.get("scenes", []):
        popup = scene.get("popup")
        if isinstance(popup, dict) and popup.get("sfx"):
            muted += len(popup["sfx"])
            popup["sfx"] = []
    out = paths.CAPTION.parent / "caption.no_sfx.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"   🔇 SFX OFF (ENABLE_SFX=false) — muted {muted} sound effect(s); "
        f"popups kept, rendering from {paths.rel(out)} (caption.json untouched).")
    return out


def inject_title(paths: PATHS, caption_path: Path) -> Path:
    """Safety-net: ensure the render caption carries the top headline.

    Stage 07 already bakes the headline into caption.json's style.title (so the
    studio and the render match). This is a belt-and-suspenders check for the
    render path: if style.title is somehow missing (old caption, stage 07 skipped),
    re-resolve it from pre_production.json / topic.json and write a sibling copy.
    If the title is already present, the caption is used as-is (no dangling copy).
    The original caption.json is never modified — we always write a sibling.
    """
    data = json.loads(caption_path.read_text(encoding="utf-8"))
    existing = data.get("style", {}).get("title")
    if existing:
        return caption_path  # already baked by stage 07 — studio/render match

    words = resolve_title_words(paths)
    if not words:
        return caption_path  # no title anywhere — render without a headline

    data.setdefault("style", {})["title"] = words
    out = caption_path.parent / "caption.render.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    preview = " ".join(w["text"] for w in words if w["text"] != "\n")
    log(f"   🏷️  Title was missing from caption — re-baked “{preview}” → {paths.rel(out)}.")
    return out


def _hero_visual(paths: PATHS, config: dict) -> str:
    """Ask the AI for ONE topic-specific central hero image for the thumbnail.

    The old prompt hardcoded an "OpenAI-style logo", so every thumbnail showed the
    ChatGPT mark regardless of topic. Instead we seed from this video's topic +
    visuals_suggested and let the AI pick the single most iconic, instantly-readable
    central object for THIS story. Falls back to a neutral tech motif on any failure.
    """
    fallback = ("a bold glowing central symbol that instantly represents the story — "
                "high-contrast, iconic, with a blue neon rim glow")
    try:
        topic = json.loads(paths.TOPIC.read_text(encoding="utf-8"))
    except Exception:
        return fallback
    headline = topic.get("topic", "")
    visuals = topic.get("visuals_suggested", "")
    if not headline:
        return fallback
    prompt = (
        "You design viral YouTube/Instagram thumbnails. For the news story below, give "
        "the SINGLE most iconic central hero visual for a 9:16 thumbnail — one clear, "
        "instantly-recognisable subject that a viewer understands in half a second and "
        "that is SPECIFIC to THIS story (e.g. a national flag, a branded chip, a robot, "
        "a product) — NOT a generic 'AI brain' and NEVER a competitor's logo unless that "
        "company IS the story. Reply with ONLY JSON: {\"hero\": \"<8-20 word visual "
        "description, cinematic, with lighting/glow cues>\"}.\n\n"
        f"STORY: {headline}\nSUGGESTED VISUALS: {visuals}")
    try:
        from core.ai_client import get_api_keys, call_ai
        keys = get_api_keys(config)
        res = call_ai(keys, config, ai_model(config), prompt, max_tokens=512,
                      expect_json=True, label="thumbnail hero visual")
        hero = (res.get("hero") if isinstance(res, dict) else "") or ""
        return hero.strip() or fallback
    except Exception as e:
        log(f"   ⚠️  Hero-visual AI failed ({str(e)[:70]}); using neutral motif.")
        return fallback


def _build_caption(paths: PATHS, config: dict) -> None:
    """Generate a ready-to-paste viral social caption for THIS video and save it to
    output/caption.txt. The style is driven by caption.md (edit that, not code); the
    story content comes from topic.json + script.json so the caption is faithful to
    what the video actually says. Best-effort — any failure just skips the file."""
    spec = STAGE_DIR / "caption.md"
    if not spec.exists():
        return
    try:
        topic = json.loads(paths.TOPIC.read_text(encoding="utf-8"))
    except Exception:
        topic = {}
    headline = topic.get("topic", "") or topic.get("hook", "")
    logline, narration = "", ""
    try:
        script = json.loads(paths.SCRIPT.read_text(encoding="utf-8"))
        logline = script.get("logline", "")
        narration = " ".join(s.get("narration", "") for s in script.get("segments", [])).strip()
    except Exception:
        pass
    if not (headline or narration):
        log("   ⚠️  No topic/script text for caption; skipping caption.txt.")
        return

    prompt = fill(spec.read_text(encoding="utf-8"),
                  headline=headline, logline=logline, narration=narration)
    try:
        from core.ai_client import get_api_keys, call_ai
        keys = get_api_keys(config)
        text = call_ai(keys, config, ai_model(config), prompt, max_tokens=1024,
                       expect_json=False, label="social caption")
        text = (text or "").strip()
        if not text:
            log("   ⚠️  Caption AI returned empty; skipping caption.txt.")
            return
        out = paths.OUTPUT / "caption.txt"
        out.write_text(text + "\n", encoding="utf-8")
        log(f"   📝 Caption saved → {paths.rel(out)}")
    except Exception as e:
        log(f"   ⚠️  Caption generation failed ({str(e)[:80]}); skipping caption.txt.")


def _endcard_prompt(paths: PATHS, config: dict) -> str:
    """Prompt for the GPT-Image-2 end-card, seeded with THIS video's headline.

    Split the headline into the same two visual lines the render uses (line 1 gold,
    line 2 white with the last word red) so the poster matches the on-screen title.
    The central hero visual is chosen by the AI from the topic — no hardcoded logo.
    """
    words = resolve_title_words(paths)
    line1, line2 = [], []
    cur = line1
    for w in words:
        if w.get("text") == "\n":
            cur = line2
            continue
        cur.append(w.get("text", ""))
    l1 = " ".join(line1).strip() or resolve_title_text(paths) or "BREAKING NEWS"
    l2 = " ".join(line2).strip()
    headline = f'"{l1}" on the first line in bold GOLD'
    if l2:
        last = l2.split()[-1]
        rest = " ".join(l2.split()[:-1])
        headline += (f', and "{rest} {last}" on the second line in bold WHITE with '
                     f'the word "{last}" in RED')
    hero = _hero_visual(paths, config)
    # Design spec lives in a co-located MD so the look can be tuned without code
    # changes. Fall back to an inline prompt if the file is missing.
    design = STAGE_DIR / "thumbnail_design.md"
    if design.exists():
        spec = design.read_text(encoding="utf-8")
        return fill(spec, headline=headline, hero=hero)
    return (
        "Vertical 9:16 portrait poster, an END-CARD / outro frame for a tech-news "
        "short video. Dark cinematic tech background: deep navy-black with glowing "
        "blue circuit lines, a faint data-grid, soft bokeh. Bold condensed uppercase "
        f"headline in the upper-middle (with a safe margin from the top edge): {headline}. "
        f"In the center, as the dominant focal element: {hero}. "
        "Near the bottom (safe margin from the bottom edge) a rounded "
        "pill button with white bold text 'FOLLOW FOR MORE' and small like/comment/"
        "share icons. Keep all text within a safe zone. Professional YouTube-thumbnail "
        "style, high contrast, sharp, cinematic, no watermark.")


def build_endcard(paths: PATHS, config: dict) -> Path | None:
    """Ensure project/endcard.png exists (1080x1920), generating it via kie.ai if
    absent. Returns the padded PNG path, or None if disabled / unavailable.

    Skips (returns None) when KIE_API_KEY is empty. If a hand-made project/endcard
    source already exists we reuse it — no API cost on re-renders. The padded output
    is always project/endcard.png (exact 1080x1920, cropped-to-cover).
    """
    padded = paths.PROJECT / "endcard.png"
    # Already padded to the right size from a previous run → reuse, no API call.
    if padded.exists():
        w, h = _png_size(padded)
        if (w, h) == (1080, 1920):
            log(f"   🖼️  End-card: reusing {paths.rel(padded)} (1080x1920).")
            return padded

    api_key = kie_api_key(config)
    if not api_key:
        log("   ↩︎  End-card skipped (KIE_API_KEY empty). Render ends on last scene.")
        return None

    raw = paths.PROJECT / "endcard_raw.png"
    try:
        if not raw.exists():
            log("   🖼️  Generating end-card poster via kie.ai (GPT Image 2)…")
            kie_image.generate_image(api_key, _endcard_prompt(paths, config), raw,
                                     aspect_ratio="9:16", resolution="1K")
        # Pad/crop to exact 1080x1920 for a clean concat with the render.
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw), "-vf",
             "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
             str(padded)], capture_output=True, text=True, check=True)
        log(f"   ✅ End-card ready → {paths.rel(padded)}")
        return padded
    except Exception as e:
        log(f"   ⚠️  End-card generation failed ({str(e)[:100]}); render ends on last scene.")
        return None


def _png_size(path: Path) -> tuple:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        w, h = out.split(",")[:2]
        return int(w), int(h)
    except Exception:
        return (0, 0)


def append_endcard(paths: PATHS, config: dict, endcard_png: Path) -> None:
    """Append the end-card as the last `ENDCARD_SECONDS` of output/final.mp4.

    The bg music continues from where the render ended (so it doesn't restart) and
    fades out under the poster. Rewrites output/final.mp4 in place via a temp file.
    """
    hold = endcard_seconds(config)
    video_dur = _media_duration(paths.FINAL)
    clip = paths.OUTPUT / "_endcard_clip.mp4"

    # Build the end-card clip: still image + a slice of the same bg music (from the
    # render's end) so the track flows continuously, then fades out.
    music_args = []
    if paths.BG_MUSIC.exists() and video_dur > 0:
        music_args = ["-ss", f"{video_dur:.3f}", "-t", f"{hold:.3f}", "-i", str(paths.BG_MUSIC)]
    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{hold:.3f}", "-i", str(endcard_png)]
    cmd += music_args
    vf = "fade=t=in:st=0:d=0.4,format=yuv420p"
    if music_args:
        cmd += ["-vf", vf, "-af", f"volume=0.5,afade=t=out:st={max(0.0, hold-0.5):.2f}:d=0.5",
                "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-shortest", str(clip)]
    else:
        # No music → silent end-card with a matching silent audio track for concat.
        cmd += ["-f", "lavfi", "-t", f"{hold:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                "-vf", vf, "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-shortest", str(clip)]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Concat render + end-card (re-encode via filter — streams may differ slightly).
    merged = paths.OUTPUT / "_final_endcard.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(paths.FINAL), "-i", str(clip),
         "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", str(merged)],
        capture_output=True, text=True, check=True)
    merged.replace(paths.FINAL)
    clip.unlink(missing_ok=True)
    log(f"   🎬 End-card appended ({hold:.1f}s) → {paths.rel(paths.FINAL)}")


def _media_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def append_animated_endcard(paths: PATHS, config: dict) -> None:
    """Render the animated EndCard composition (Instagram Follow CTA) and append it
    to the tail of output/final.mp4. The bg music continues from where the render
    ended and fades out under the card. Best-effort — any failure leaves final.mp4
    intact. The end-card @handle comes from the profile (see core.config.endcard_handle),
    never hardcoded.

    All intermediate files are written to a private scratch dir OUTSIDE output/, so
    the output folder only ever holds the finished video + thumbnail — no temps,
    whether this succeeds or fails.
    """
    handle = endcard_handle(paths, config)
    props = {"ctaText": "Follow", "subText": "for more like this", "handle": handle,
             "gradFrom": "#feda75", "gradMid": "#d62976", "gradTo": "#4f5bd5",
             "bgTop": "#1a0a24", "bgBottom": "#070310"}

    with tempfile.TemporaryDirectory(prefix="reels_endcard_") as tmp:
        tmpd = Path(tmp)
        card = tmpd / "endcard_anim.mp4"

        # 1) Render the EndCard composition (portrait 1080x1920, 30fps, silent).
        #    The composition is 150f (5s) but the content settles by ~2s — hold the
        #    rest is dead air. Trim to ENDCARD_SECONDS so it ends right after settle.
        last_frame = max(1, round(endcard_seconds(config) * 30)) - 1
        cmd = ["bunx", "remotion", "render", "src/index.ts", "EndCard",
               str(card), f"--props={json.dumps(props)}",
               f"--frames=0-{last_frame}"]
        chrome = os.environ.get("REMOTION_CHROME", "")
        if chrome and os.path.exists(chrome):
            cmd.append(f"--browser-executable={chrome}")
        log(f"   🎬 Rendering animated end-card ({handle})…")
        proc = subprocess.run(cmd, cwd=str(paths.REMOTION), capture_output=True, text=True)
        if proc.returncode != 0 or not card.exists():
            log(f"   ⚠️  End-card render failed; keeping video as-is.")
            return

        # 2) Mux the bg-music tail onto the (silent) card so audio flows continuously.
        card_dur = _media_duration(card)
        video_dur = _media_duration(paths.FINAL)
        card_av = tmpd / "endcard_av.mp4"
        if paths.BG_MUSIC.exists() and video_dur > 0:
            # Continue the tail of bg-music past the video. video_dur can exceed the
            # music length (e.g. 55s video, 30s track), so -ss would seek past EOF and
            # yield empty audio — loop the track and wrap the offset into its length.
            music_dur = _media_duration(paths.BG_MUSIC)
            offset = (video_dur % music_dur) if music_dur > 0 else 0.0
            music = ["-stream_loop", "-1", "-ss", f"{offset:.3f}", "-t", f"{card_dur:.3f}",
                     "-i", str(paths.BG_MUSIC)]
            af = f"volume=0.5,afade=t=out:st={max(0.0, card_dur-0.6):.2f}:d=0.6"
        else:
            music = ["-f", "lavfi", "-t", f"{card_dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            af = "anull"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(card)] + music +
            ["-map", "0:v", "-map", "1:a", "-af", af, "-c:v", "libx264", "-pix_fmt",
             "yuv420p", "-c:a", "aac", "-ar", "48000", "-shortest", str(card_av)],
            capture_output=True, text=True, check=True)

        # 3) Concat render + end-card (re-encode via filter — streams may differ).
        merged = tmpd / "final_anim.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(paths.FINAL), "-i", str(card_av),
             "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", str(merged)],
            capture_output=True, text=True, check=True)
        shutil.copyfile(merged, paths.FINAL)
    log(f"   🎬 Animated end-card appended ({card_dur:.1f}s) → {paths.rel(paths.FINAL)}")


def main():
    parser = argparse.ArgumentParser(description="Stage 10 — Remotion render")
    parser.add_argument("--project", "-p", default=str(STAGE_DIR.parents[1]))
    args = parser.parse_args()

    paths = PATHS(args.project).ensure_dirs()
    if not paths.CAPTION.exists():
        raise SystemExit(f"❌ caption.json not found: {paths.CAPTION} — run stage 06/07 first.")

    config = load_config(args.project)
    clean_watermarks(paths)
    ensure_symlinks(paths)
    paths.OUTPUT.mkdir(parents=True, exist_ok=True)

    render_caption = build_render_caption(paths, popups_enabled(config), sfx_enabled(config))

    render_caption = inject_title(paths, render_caption)

    cmd = ["bunx", "remotion", "render", "src/index.ts", "Documentary",
           str(paths.FINAL), f"--props={render_caption}"]
    # Reuse an already-installed Chrome if one is pointed to via REMOTION_CHROME
    # (or a common playwright cache) so Remotion never needs to download its own
    # headless shell — critical on machines that can't reach googleapis.com.
    chrome = os.environ.get("REMOTION_CHROME", "")
    if chrome and os.path.exists(chrome):
        cmd.append(f"--browser-executable={chrome}")
        log(f"   using Chrome: {chrome}")
    log(f"🎬 Rendering with Remotion (Bun) → {paths.rel(paths.FINAL)}")
    log(f"   {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(paths.REMOTION))
    if proc.returncode != 0 or not paths.FINAL.exists():
        raise SystemExit(f"❌ Remotion render failed (exit {proc.returncode}).")
    log(f"✅ Rendered: {paths.rel(paths.FINAL)}")

    # Generate the poster (title + logo + CTA) and save it as the upload
    # thumbnail / cover image in output/. It is NOT appended to the video — the
    # render ends on the last scene; the poster is only a separate cover PNG.
    endcard = build_endcard(paths, config)
    if endcard:
        try:
            thumb = paths.OUTPUT / "thumbnail.png"
            shutil.copyfile(endcard, thumb)
            log(f"   🖼️  Thumbnail/cover saved → {paths.rel(thumb)}")
        except Exception as e:
            log(f"   ⚠️  Thumbnail copy failed ({str(e)[:80]}).")

    # Write the ready-to-paste viral social caption → output/caption.txt.
    _build_caption(paths, config)

    # Append the animated Instagram Follow end-card to the tail of the video.
    try:
        append_animated_endcard(paths, config)
    except Exception as e:
        log(f"   ⚠️  Animated end-card append failed ({str(e)[:100]}); keeping video as-is.")


if __name__ == "__main__":
    main()

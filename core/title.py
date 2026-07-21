"""core/title.py — resolve the top headline and lay it out for the TitleBar.

ONE place that both the studio and the render read from, so what you see in
`bunx remotion studio` is exactly what the final MP4 shows (no mismatch).

The headline is baked into caption.json's `style.title` (stage 07). Documentary.tsx
renders `style.title` directly, so studio + render share a single source of truth.
The render stage keeps a safety-net that re-bakes it if it's somehow missing.

Title text is looked up across the stages that actually produce one, in order:
  1. pre_production.json → brief.title   (stage 01 — the real, curated title)
  2. topic.json → title                  (legacy/manual override, if ever set)
Absent everywhere ⇒ no title (caption untouched).
"""
import json
from pathlib import Path

GOLD = "#FFD23F"
RED = "#FF3B3B"
WHITE = "#FFFFFF"


def resolve_title_text(paths) -> str:
    """Find the headline string from whichever stage produced it. '' if none."""
    # 1) stage 01 preproduction — brief.title (the normal source)
    pre = paths.PRE_PRODUCTION
    if pre.exists():
        try:
            brief = (json.loads(pre.read_text(encoding="utf-8")) or {}).get("brief", {})
            t = (brief.get("title", "") or "").strip()
            if t:
                return t
        except Exception:
            pass
    # 2) topic.json — top-level title (manual override, rarely present)
    topic = paths.PROJECT / "topic.json"
    if topic.exists():
        try:
            t = (json.loads(topic.read_text(encoding="utf-8")) or {}).get("title", "") or ""
            t = t.strip()
            if t:
                return t
        except Exception:
            pass
    return ""


def layout_title(title_text: str) -> list:
    """Two-line reference-reel layout: line 1 all GOLD, line 2 WHITE w/ last word RED.

    A word whose text is exactly "\\n" marks the line break for the TitleBar.
    Returns a list of {"text","color"} words, or [] for empty input.
    """
    title_text = (title_text or "").strip()
    if not title_text:
        return []

    words = title_text.split()
    if len(words) >= 3:
        cut = (len(words) + 1) // 2
        line1, line2 = words[:cut], words[cut:]
    else:
        line1, line2 = words, []

    coloured = [{"text": w, "color": GOLD} for w in line1]
    if line2:
        coloured.append({"text": "\n", "color": WHITE})
        for i, w in enumerate(line2):
            coloured.append({"text": w, "color": RED if i == len(line2) - 1 else WHITE})
    return coloured


def resolve_title_words(paths) -> list:
    """Convenience: resolve text + lay it out. [] if no title anywhere."""
    return layout_title(resolve_title_text(paths))

"""core/contracts.py — per-stage input/output contracts (Layer A handover).

This is the heart of the "100% accuracy" goal (docs/PRD.md G3). Each stage declares
what files it REQUIRES (must exist + be valid before it runs) and what it PRODUCES
(must exist + be valid after it runs). The orchestrator checks `requires` before a
stage and `produces` after — a stage never runs on bad input, and a broken output
never reaches the next stage.

Paths in each File() are relative to the project root; validate() resolves them via
a core.config.PATHS instance.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from core import media_utils


# ─── file specifications ──────────────────────────────────────────────────────

@dataclass
class File:
    """One required/produced file and how to validate it.

    kind:      "json" | "text" | "mp4" | "audio" | "image" | "exists"
    must_have: for json — top-level keys that must be present (and non-empty)
    per_scene: if set, this is a per-scene file pattern; {n} is the 1-based scene index.
               validate() then checks one file per scene (count from n_scenes()).
    min_count: for per_scene, minimum number that must be valid (default: all scenes)
    """
    path: str
    kind: str = "exists"
    must_have: list = field(default_factory=list)
    per_scene: bool = False
    label: str = ""

    def resolve(self, paths, n: str | int = "") -> Path:
        p = self.path.replace("{n}", str(n))
        return (paths.ROOT / p)

    def _check_one(self, fp: Path) -> tuple[bool, str]:
        if not fp.exists():
            return False, f"missing: {fp.name}"
        if self.kind == "json":
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                return False, f"invalid JSON in {fp.name}: {str(e)[:60]}"
            for key in self.must_have:
                if key not in data or (isinstance(data[key], (list, dict, str)) and len(data[key]) == 0):
                    return False, f"{fp.name} missing/empty key '{key}'"
        elif self.kind == "text":
            if fp.stat().st_size == 0 or not fp.read_text(encoding="utf-8").strip():
                return False, f"{fp.name} is empty"
        elif self.kind == "mp4":
            ok, dur = media_utils.mp4_ok(fp)
            if not ok:
                return False, f"{fp.name} not a valid mp4 (dur={dur:.1f}s)"
        elif self.kind == "audio":
            ok, dur = media_utils.audio_ok(fp)
            if not ok:
                return False, f"{fp.name} not valid audio (dur={dur:.1f}s)"
        elif self.kind == "image":
            if fp.stat().st_size < 1_000:
                return False, f"{fp.name} too small to be an image"
        return True, ""

    def validate(self, paths, n_scenes: int) -> tuple[bool, list]:
        """Return (ok, [error strings])."""
        if not self.per_scene:
            ok, err = self._check_one(self.resolve(paths))
            return ok, ([] if ok else [err])

        # per-scene: check scene_1 ... scene_N
        if n_scenes <= 0:
            return False, [f"{self.path}: scene count unknown (script.json not ready)"]
        errors = []
        for i in range(1, n_scenes + 1):
            ok, err = self._check_one(self.resolve(paths, i))
            if not ok:
                errors.append(err)
        return (len(errors) == 0), errors


@dataclass
class Contract:
    requires: list = field(default_factory=list)
    produces: list = field(default_factory=list)


# ─── the pipeline order + every stage's contract ──────────────────────────────

ORDER = [
    "00_topic", "01_preproduction", "02_script", "03_scenes", "04_music_prompt",
    "05_avatar", "06_process", "07_popups", "08_broll", "09_music",
    "10_render", "11_final_trim",
]

CONTRACTS = {
    "00_topic": Contract(
        requires=[File("profile/profile.json", "json", must_have=["niche"])],
        produces=[File("project/topic.json", "json", must_have=["topic"])],
    ),
    "01_preproduction": Contract(
        requires=[File("project/topic.json", "json", must_have=["topic"])],
        produces=[File("project/scripting/pre_production.json", "json", must_have=["brief"])],
    ),
    "02_script": Contract(
        requires=[File("project/scripting/pre_production.json", "json", must_have=["brief"])],
        produces=[File("project/scripting/script.json", "json", must_have=["segments"])],
    ),
    "03_scenes": Contract(
        requires=[File("project/scripting/pre_production.json", "json"),
                  File("project/scripting/script.json", "json", must_have=["segments"])],
        produces=[File("project/scripting/scenes.json", "json", must_have=["scenes"])],
    ),
    "04_music_prompt": Contract(
        requires=[File("project/scripting/pre_production.json", "json"),
                  File("project/scripting/script.json", "json", must_have=["segments"])],
        produces=[File("project/scripting/music_prompt.txt", "text")],
    ),
    "05_avatar": Contract(
        requires=[File("project/scripting/script.json", "json", must_have=["segments"]),
                  File("profile/avatar.jpg", "image")],
        produces=[File("project/avatar/scene_{n}.mp4", "mp4", per_scene=True)],
    ),
    "06_process": Contract(
        requires=[File("project/avatar/scene_{n}.mp4", "mp4", per_scene=True),
                  File("project/scripting/script.json", "json", must_have=["segments"])],
        produces=[File("project/scripting/caption.json", "json", must_have=["scenes"])],
    ),
    "07_popups": Contract(
        requires=[File("project/scripting/caption.json", "json", must_have=["scenes"])],
        produces=[File("project/scripting/caption.json", "json", must_have=["scenes"])],
    ),
    "08_broll": Contract(
        requires=[File("project/scripting/scenes.json", "json", must_have=["scenes"])],
        produces=[File("project/broll/scene_{n}_a.mp4", "mp4", per_scene=True)],
    ),
    "09_music": Contract(
        requires=[File("project/scripting/music_prompt.txt", "text")],
        produces=[File("project/music/bg_music.mp3", "audio")],
    ),
    "10_render": Contract(
        requires=[File("project/scripting/caption.json", "json", must_have=["scenes"]),
                  File("project/music/bg_music.mp3", "audio")],
        produces=[File("output/final.mp4", "mp4")],
    ),
    "11_final_trim": Contract(
        requires=[File("output/final.mp4", "mp4")],
        produces=[File("output/final_trimmed.mp4", "mp4")],
    ),
}


def get(stage: str) -> Contract:
    if stage not in CONTRACTS:
        raise KeyError(f"Unknown stage '{stage}'. Known: {', '.join(ORDER)}")
    return CONTRACTS[stage]


def check(stage: str, which: str, paths) -> tuple[bool, list]:
    """Validate a stage's 'requires' or 'produces'. Returns (ok, [errors])."""
    contract = get(stage)
    files = contract.requires if which == "requires" else contract.produces
    n = media_utils.n_scenes(paths)
    all_errors = []
    for f in files:
        ok, errs = f.validate(paths, n)
        if not ok:
            all_errors.extend(errs)
    return (len(all_errors) == 0), all_errors

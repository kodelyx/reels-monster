"""core/promptlib.py — small helpers shared by the AI text stages (01-04, 07).

These were inline in reel-factory/scripts/pipeline.py. Centralised here so each
stage's run.py stays thin (Rules R6: shared logic lives in core/).
"""
import json
from pathlib import Path


def read_prompt(stage_dir) -> str:
    """Read a stage's prompt.md (co-located with its run.py)."""
    path = Path(stage_dir) / "prompt.md"
    if not path.exists():
        raise SystemExit(f"❌ Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")


def fill(template: str, **values) -> str:
    """Replace {key} and {{key}} placeholders with stringified values."""
    out = template
    for key, val in values.items():
        text = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, indent=2)
        out = out.replace("{{" + key + "}}", text).replace("{" + key + "}", text)
    return out


def load_json(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"❌ Required file not found: {path}\n   Run the earlier stage first.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

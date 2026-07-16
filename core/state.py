"""core/state.py — master pipeline state (Layer B handover, see docs/Architecture.md §4).

Tracks every stage's status in `project/state.json` so the orchestrator knows what
is done, what failed, and where to resume. This is the single place that reads/writes
that file — stages never touch it directly (the orchestrator calls mark() for them).

state.json shape:
{
  "project":  "<slug or ''>",
  "updated":  "<ISO timestamp>",
  "stages": {
     "00_topic": {"status": "done", "output": "project/topic.json", "at": "...", "error": null},
     ...
  }
}

status values: "pending" | "running" | "done" | "failed"
"""
import json
from datetime import datetime
from pathlib import Path

PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class State:
    def __init__(self, state_path):
        self.path = Path(state_path)
        self.data = {"project": "", "updated": _now(), "stages": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.setdefault("stages", {})
            except (json.JSONDecodeError, OSError):
                pass  # corrupt/empty → start fresh, don't crash the run

    # ─── read ────────────────────────────────────────────────────────────────

    def status(self, stage: str) -> str:
        return self.data["stages"].get(stage, {}).get("status", PENDING)

    def is_done(self, stage: str) -> bool:
        return self.status(stage) == DONE

    def stage(self, stage: str) -> dict:
        return self.data["stages"].get(stage, {"status": PENDING})

    def first_incomplete(self, order: list) -> str | None:
        """First stage in `order` that is not done — where --resume starts."""
        for s in order:
            if not self.is_done(s):
                return s
        return None

    # ─── write ───────────────────────────────────────────────────────────────

    def mark(self, stage: str, status: str, output=None, error=None) -> None:
        entry = self.data["stages"].setdefault(stage, {})
        entry["status"] = status
        entry["at"] = _now()
        if output is not None:
            entry["output"] = str(output)
        if error is not None:
            entry["error"] = str(error)[:500]
        elif status in (RUNNING, DONE):
            entry["error"] = None
        self.save()

    def set_project(self, slug: str) -> None:
        self.data["project"] = slug
        self.save()

    def save(self) -> None:
        self.data["updated"] = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ─── display ───────────────────────────────────────────────────────────────

    def summary(self, order: list) -> str:
        icon = {DONE: "✅", FAILED: "❌", RUNNING: "🔄", PENDING: "⚪"}
        lines = []
        for s in order:
            st = self.status(s)
            line = f"  {icon.get(st, '⚪')} {s:<18} {st}"
            err = self.stage(s).get("error")
            if st == FAILED and err:
                line += f"  — {err[:80]}"
            lines.append(line)
        return "\n".join(lines)

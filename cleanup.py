#!/usr/bin/env python3
"""Cleanup — reset generated state before starting a new reel.

Default (no flags): dry-run, sirf report. `--clean` actually deletes.

Cleaned:
    project/*   - saari pipeline state (topic, script, avatar, broll, captions,
                  music/bg_music.mp3, intervals, state.json). Stage 09 music ko
                  fresh regenerate kar deta hai; remotion/public/bg_music.mp3
                  isi ka symlink hai.
    output/*    - pichle runs ke rendered videos
    __pycache__, *.pyc, .DS_Store  - kahin bhi (reels-monster/ ke andar)

Never touched:
    stages/, core/, docs/, _archive/, profile/, sfx/, remotion/ (apne cache chhod ke),
    config.env, .env, README.md

Usage:
    python3 cleanup.py            # sirf dikhao kya stale hai
    python3 cleanup.py --clean    # delete karo
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules"}


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def rglob_skip(root: Path, pattern: str):
    for p in root.rglob(pattern):
        if not any(part in SKIP_DIRS for part in p.parts):
            yield p


def find_targets():
    targets = []  # (label, path, kind)

    project_dir = ROOT / "project"
    if project_dir.exists() and any(project_dir.iterdir()):
        targets.append(("project/ (pipeline state: topic, script, avatar, broll, captions, state.json)",
                        project_dir, "contents"))

    output_dir = ROOT / "output"
    if output_dir.exists() and any(output_dir.iterdir()):
        targets.append(("output/ (rendered videos)", output_dir, "contents"))

    for d in rglob_skip(ROOT, "__pycache__"):
        targets.append((f"__pycache__: {d.relative_to(ROOT)}", d, "dir"))
    for f in rglob_skip(ROOT, "*.pyc"):
        targets.append((f".pyc: {f.relative_to(ROOT)}", f, "file"))
    for f in rglob_skip(ROOT, ".DS_Store"):
        targets.append((f".DS_Store: {f.relative_to(ROOT)}", f, "file"))

    return targets


def main():
    parser = argparse.ArgumentParser(description="Report/clean stale state before a new reel")
    parser.add_argument("--clean", action="store_true", help="Actually delete (default: dry run)")
    args = parser.parse_args()

    targets = find_targets()
    if not targets:
        print("✅ Nothing stale — already clean.")
        return

    total = 0
    print("🔍 Stale/junk found:\n")
    for label, path, _kind in targets:
        try:
            size = dir_size(path) if path.is_dir() else path.stat().st_size
        except FileNotFoundError:
            size = 0
        total += size
        print(f"  - {label} ({human_size(size)})")

    print(f"\nTotal: {human_size(total)} across {len(targets)} item(s)")

    if not args.clean:
        print("\nDry run only — kuch delete nahi hua. `--clean` se hatao.")
        print("Protected: stages/, core/, docs/, _archive/, profile/, sfx/, remotion/, .env, README.md")
        return

    print("\n🧹 Cleaning...")
    for label, path, kind in targets:
        try:
            if kind == "contents":
                for child in path.iterdir():
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            elif kind == "dir":
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
    print("✅ Done. project/ aur output/ reset; caches cleared.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""sound_manager.py — MyInstants SFX downloader & library utility.

Downloads sound effects from MyInstants.com (categories, trending, or custom list),
deduplicates, and flattens them into the sfx/ directory. Run this once (or periodically)
to populate sfx/ with real sounds — the pipeline's stage 07 (popups) will then let AI
pick context-aware SFX from whatever's available.

Usage:
  python3 sound_manager.py --trending in --pages 5     # trending India sounds
  python3 sound_manager.py --categories --pages 3       # all categories, 3 pages each
  python3 sound_manager.py --file my_links.txt           # custom URL list

Output goes to: reels-monster/sfx/
"""
import urllib.request
import re
import os
import sys
import argparse
import hashlib
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from core.config import PATHS

SOUND_EFFECT_DIR = str(PATHS(ROOT).SFX)

# Pre-defined categories mapping
CATEGORY_MAP = {
    "anime_and_manga": "https://www.myinstants.com/en/categories/anime%20%26%20manga/",
    "games": "https://www.myinstants.com/en/categories/games/",
    "memes": "https://www.myinstants.com/en/categories/memes/",
    "movies": "https://www.myinstants.com/en/categories/movies/",
    "music": "https://www.myinstants.com/en/categories/music/",
    "politics": "https://www.myinstants.com/en/categories/politics/",
    "pranks": "https://www.myinstants.com/en/categories/pranks/",
    "reactions": "https://www.myinstants.com/en/categories/reactions/",
    "sound_effects": "https://www.myinstants.com/en/categories/sound%20effects/",
    "sports": "https://www.myinstants.com/en/categories/sports/",
    "television": "https://www.myinstants.com/en/categories/television/",
    "tiktok_trends": "https://www.myinstants.com/en/categories/tiktok%20trends/",
    "viral": "https://www.myinstants.com/en/categories/viral/",
    "whatsapp_audios": "https://www.myinstants.com/en/categories/whatsapp%20audios/",
    "trending_india": "https://www.myinstants.com/en/index/in/"
}


# --- MD5 & HELPER METHODS ---

def get_md5(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def download_file(url, dest_path):
    """Download a single file."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(dest_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception:
        return False


def fetch_mp3_path_from_page(page_url):
    """Fetch individual page HTML and extract the direct MP3 path."""
    req = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode("utf-8")
            match = re.search(r"(/media/sounds/[^\'\"\\s]+\.mp3)", html_content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def scrape_list_page(page_url):
    """Scrape a directory page for all MP3 paths."""
    req = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            media_paths = list(set(re.findall(r'/media/sounds/[^"]+\.mp3', body)))
            return media_paths
    except Exception:
        return []


# --- DEDUPLICATE & FLATTEN ENGINE ---

def run_cleanup_and_merge():
    """Flattens and deduplicates all files from the .temp/ directory into SOUND_EFFECT_DIR."""
    temp_dir = os.path.join(SOUND_EFFECT_DIR, ".temp")
    if not os.path.exists(temp_dir):
        return

    print("\n🧹 Running automatic flattening and deduplication...")

    # 1. Collect MD5s of existing flat files inside SOUND_EFFECT_DIR
    existing_hashes = set()
    for file in os.listdir(SOUND_EFFECT_DIR):
        file_path = os.path.join(SOUND_EFFECT_DIR, file)
        if os.path.isfile(file_path) and file.endswith(".mp3"):
            h = get_md5(file_path)
            if h:
                existing_hashes.add(h)

    total_moved = 0
    total_removed = 0

    # 2. Traverse temp files recursively and move to SoundEffect root
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if not file.endswith(".mp3"):
                continue

            src_path = os.path.join(root, file)
            md5 = get_md5(src_path)
            if not md5:
                continue

            # Duplicate: delete it
            if md5 in existing_hashes:
                try:
                    os.remove(src_path)
                    total_removed += 1
                except Exception:
                    pass
                continue

            # Handle name collision
            dest_filename = file
            dest_path = os.path.join(SOUND_EFFECT_DIR, dest_filename)
            counter = 1
            name_part, ext_part = os.path.splitext(file)

            while os.path.exists(dest_path):
                existing_md5 = get_md5(dest_path)
                if existing_md5 == md5:
                    break
                dest_filename = f"{name_part}_{counter}{ext_part}"
                dest_path = os.path.join(SOUND_EFFECT_DIR, dest_filename)
                counter += 1

            try:
                if src_path != dest_path:
                    shutil.move(src_path, dest_path)
                existing_hashes.add(md5)
                total_moved += 1
            except Exception as e:
                print(f"  ❌ Error moving {file}: {e}")

    # Remove temp folder
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    print(f"🎉 Merge Finished! Added {total_moved} new unique sounds, discarded {total_removed} duplicates.")


# --- CONCURRENT TASKS RUNNERS ---

def run_parallel_downloads(tasks):
    """Downloads tasks list in parallel using ThreadPoolExecutor."""
    total = len(tasks)
    success = 0

    def run_task(task):
        url, path = task
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return True
        return download_file(url, path)

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(run_task, task): task for task in tasks}
        for future in as_completed(futures):
            if future.result():
                success += 1
                if success % 50 == 0 or success == total:
                    print(f"    📥 Progress: {success}/{total} sounds downloaded.")
    return success


# --- MODES ---

def handle_category_mode(max_pages):
    """Scrapes and downloads from standard categories."""
    temp_dir = os.path.join(SOUND_EFFECT_DIR, ".temp", "categories")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"📂 Mode: Category Downloads (max {max_pages} pages per category)")

    for cat_name, cat_url in CATEGORY_MAP.items():
        print(f"📁 Processing Category: {cat_name.upper()}...")
        all_paths = []
        for p in range(1, max_pages + 1):
            sound_paths = scrape_list_page(f"{cat_url}?page={p}")
            if not sound_paths:
                break
            all_paths.extend(sound_paths)

        all_paths = list(set(all_paths))
        if not all_paths:
            continue

        tasks = []
        for path in all_paths:
            filename = path.split("/")[-1]
            tasks.append((f"https://www.myinstants.com{path}", os.path.join(temp_dir, filename)))

        run_parallel_downloads(tasks)


def handle_trending_mode(region, max_pages):
    """Scrapes and downloads trending sounds for a region (e.g. 'in' or 'us')."""
    temp_dir = os.path.join(SOUND_EFFECT_DIR, ".temp", f"trending_{region}")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"📂 Mode: Trending Region '{region.upper()}' (max {max_pages} pages)")

    all_paths = []
    print(f"  Scanning page links (page 1 to {max_pages})...")
    with ThreadPoolExecutor(max_workers=20) as page_executor:
        futures = {page_executor.submit(scrape_list_page, f"https://www.myinstants.com/en/index/{region}/?page={p}"): p for p in range(1, max_pages + 1)}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_paths.extend(res)

    all_paths = list(set(all_paths))
    print(f"  Discovered {len(all_paths)} trending sounds. Downloading...")

    tasks = [(f"https://www.myinstants.com{path}", os.path.join(temp_dir, path.split("/")[-1])) for path in all_paths]
    run_parallel_downloads(tasks)


def handle_file_mode(file_path):
    """Downloads individual sound page links from a text file list."""
    if not os.path.exists(file_path):
        print(f"❌ Custom list file not found: {file_path}")
        return

    temp_dir = os.path.join(SOUND_EFFECT_DIR, ".temp", "custom_list")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"📂 Mode: Custom file list ({file_path})")

    with open(file_path, "r") as f:
        links = [line.strip() for line in f if line.strip().startswith("https://www.myinstants.com")]

    total = len(links)
    print(f"  Loaded {total} URLs. Resolving direct MP3 sources...")

    def resolve_and_download(link):
        slug = [p for p in link.split("/") if p][-1]
        dest_path = os.path.join(temp_dir, f"{slug}.mp3")
        mp3_path = fetch_mp3_path_from_page(link)
        if not mp3_path:
            clean_slug = re.sub(r"-\d+$", "", slug)
            mp3_path = f"/media/sounds/{clean_slug}.mp3"
        url = f"https://www.myinstants.com{mp3_path}"
        download_file(url, dest_path)

    with ThreadPoolExecutor(max_workers=16) as resolver:
        futures = resolver.map(resolve_and_download, links)
        for _ in futures:
            pass


# --- MAIN CONTROLLER ---

def main():
    parser = argparse.ArgumentParser(description="SFX Download & Management CLI for reels-monster.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--categories", action="store_true", help="Download sound categories.")
    group.add_argument("--trending", type=str, metavar="REGION", help="Download trending region (e.g. 'in' or 'us').")
    group.add_argument("--file", type=str, metavar="PATH", help="Download from a custom text file list of MyInstants URLs.")

    parser.add_argument("--pages", type=int, default=5, help="Number of pages to scan (for categories or trending).")

    args = parser.parse_args()

    os.makedirs(SOUND_EFFECT_DIR, exist_ok=True)

    start_time = time.time()

    if args.categories:
        handle_category_mode(args.pages)
    elif args.trending:
        handle_trending_mode(args.trending, args.pages)
    elif args.file:
        handle_file_mode(args.file)

    # Automatically clean up, flatten and deduplicate into flat directory
    run_cleanup_and_merge()

    print(f"\n🚀 All operations completed in {time.time() - start_time:.1f}s.")


if __name__ == "__main__":
    main()

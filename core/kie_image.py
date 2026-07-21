"""core/kie_image.py — kie.ai GPT Image 2 text-to-image client.

Used by stage 10 to generate the end-card / outro poster (title + logo +
"FOLLOW FOR MORE") that gets appended to the tail of the render.

Two-step async API:
  1. POST /api/v1/jobs/createTask  → returns a taskId
  2. GET  /api/v1/jobs/recordInfo?taskId=…  (poll until state == success|fail)
     → resultJson.resultUrls[0] is the PNG URL, which we download.

Auth: Bearer <KIE_API_KEY> (paid; key lives in git-ignored .env).

Public API:
    generate_image(api_key, prompt, dest, aspect_ratio="9:16", resolution="1K")
        -> Path (downloaded PNG at `dest`)   |   raises RuntimeError on failure
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.kie.ai"
MODEL = "gpt-image-2-text-to-image"


def _request(url: str, api_key: str, payload: dict = None, timeout: float = 30.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        obj = json.loads(r.read().decode("utf-8"))
    if not isinstance(obj, dict) or obj.get("code") != 200:
        msg = obj.get("msg") if isinstance(obj, dict) else str(obj)[:120]
        raise RuntimeError(f"kie.ai error: {msg}")
    return obj


def create_task(api_key: str, prompt: str, aspect_ratio: str = "9:16",
                resolution: str = "1K") -> str:
    """Create a generation task; return its taskId."""
    payload = {"model": MODEL,
               "input": {"prompt": prompt, "aspect_ratio": aspect_ratio,
                         "resolution": resolution}}
    obj = _request(f"{BASE}/api/v1/jobs/createTask", api_key, payload)
    task_id = (obj.get("data") or {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"kie.ai: no taskId in response ({str(obj)[:120]})")
    return task_id


def wait_for_result(api_key: str, task_id: str, timeout: float = 300.0,
                    interval: float = 5.0) -> str:
    """Poll recordInfo until the task succeeds; return the result image URL."""
    deadline = time.time() + timeout
    url = f"{BASE}/api/v1/jobs/recordInfo?taskId={task_id}"
    while time.time() < deadline:
        obj = _request(url, api_key, timeout=20.0)
        data = obj.get("data") or {}
        state = data.get("state")
        if state == "success":
            result = json.loads(data.get("resultJson") or "{}")
            urls = result.get("resultUrls") or []
            if not urls:
                raise RuntimeError("kie.ai: success but no resultUrls")
            return urls[0]
        if state == "fail":
            raise RuntimeError(
                f"kie.ai task failed: {data.get('failMsg') or data.get('failCode')}")
        time.sleep(interval)
    raise RuntimeError(f"kie.ai task {task_id} timed out after {timeout:.0f}s")


def download(url: str, dest: Path, timeout: float = 60.0) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # The result CDN rejects the default python-urllib UA with 403 — send a browser UA.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dest.write_bytes(r.read())
    return dest


def generate_image(api_key: str, prompt: str, dest, aspect_ratio: str = "9:16",
                   resolution: str = "1K", timeout: float = 300.0) -> Path:
    """End-to-end: create task → poll → download PNG to `dest`. Returns the path.

    Raises RuntimeError on any failure (empty key, HTTP error, task fail, timeout)
    so the caller can decide to skip the end-card gracefully.
    """
    if not api_key:
        raise RuntimeError("kie.ai: no API key (set KIE_API_KEY in .env)")
    task_id = create_task(api_key, prompt, aspect_ratio, resolution)
    img_url = wait_for_result(api_key, task_id, timeout=timeout)
    return download(img_url, dest)

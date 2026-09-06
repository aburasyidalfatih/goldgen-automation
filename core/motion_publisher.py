"""Explicit, opt-in Facebook video publisher for Motion Studio.

This adapter is not called by the worker. It is kept behind the disabled
manual-first boundary until staging approval is complete.
"""

import os
from pathlib import Path

import requests


def publish_video(page_id, access_token, video_path, caption, api_version=None):
    if os.getenv("MOTION_AUTO_PUBLISH_ENABLED", "false").lower() != "true":
        raise RuntimeError("Automatic video publishing is disabled")
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if not page_id or not access_token:
        raise ValueError("page_id dan access_token wajib diisi")
    version = api_version or os.getenv("META_GRAPH_API_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{version}/{page_id}/videos"
    with path.open("rb") as video:
        response = requests.post(
            url,
            data={"access_token": access_token, "description": caption or ""},
            files={"source": (path.name, video, "video/mp4")},
            timeout=180,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Facebook video publish failed ({response.status_code})")
    result = response.json()
    return {"id": result.get("id"), "raw": result}

"""Technical quality gates for rendered Motion Studio videos."""

import json
import shutil
import subprocess
from pathlib import Path


def inspect_media(path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "errors": ["ffprobe belum terpasang"]}
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return {"ok": False, "errors": [result.stderr.strip() or "ffprobe gagal"]}
    return {"ok": True, "data": json.loads(result.stdout or "{}"), "errors": []}


def validate_render(video_path, manifest_path):
    errors = []
    video = Path(video_path)
    manifest = Path(manifest_path)
    if not video.is_file() or video.stat().st_size < 1024:
        errors.append("File video tidak ada atau terlalu kecil")
    if not manifest.is_file():
        errors.append("Scene manifest tidak ditemukan")
    subtitle_name = manifest.name.replace(".manifest.json", ".srt")
    subtitle = manifest.with_name(subtitle_name)
    if not subtitle.is_file() or not subtitle.read_text(encoding="utf-8").strip():
        errors.append("Subtitle manifest tidak ditemukan atau kosong")
    details = inspect_media(video) if not errors else {"ok": False, "errors": []}
    streams = details.get("data", {}).get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video_stream:
        if video_stream.get("width") != 1080 or video_stream.get("height") != 1920:
            errors.append("Resolusi video bukan 1080x1920")
        if float(video_stream.get("duration", 0) or 0) <= 0:
            errors.append("Durasi video tidak valid")
    elif not errors:
        errors.append("Video stream tidak ditemukan")
    return {
        "ok": not errors,
        "errors": errors + details.get("errors", []),
        "video_path": str(video),
        "manifest_path": str(manifest),
    }

"""Deterministic portrait motion renderer.

The renderer is intentionally independent from auto_poster.py. It consumes a
scene manifest and uses FFmpeg when available; no AI video generation is used.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.motion_studio import MOTION_ASSETS_DIR, MOTION_RENDERS_DIR

WIDTH, HEIGHT, FPS = 1080, 1920, 30


def _timestamp(seconds):
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(job_id, manifest):
    """Create subtitle timing from scene text layers."""
    path = MOTION_RENDERS_DIR / f"{job_id}.srt"
    current = 0.0
    entries = []
    for index, scene in enumerate(manifest.get("scenes", []), start=1):
        duration = max(float(scene.get("duration", 1)), 1)
        text = next((layer.get("text") for layer in scene.get("layers", [])
                     if layer.get("type") == "text"), "")
        if text:
            entries.append(f"{index}\n{_timestamp(current)} --> {_timestamp(current + duration)}\n{text}\n")
        current += duration
    path.write_text("\n".join(entries), encoding="utf-8")
    return path


def ffmpeg_path():
    return shutil.which("ffmpeg")


def default_manifest(topic):
    """Create a safe first-pass storyboard from an existing topic."""
    points = topic.get("list_points") or []
    scenes = [{
        "id": "hook",
        "duration": 5,
        "background": None,
        "layers": [{"type": "text", "text": topic.get("headline", "Gold facts"), "role": "title"}],
    }]
    for index, point in enumerate(points[:5], start=1):
        scenes.append({
            "id": f"fact-{index}",
            "duration": 8,
            "background": None,
            "layers": [
                {"type": "text", "text": point, "role": "fact"},
                {"type": "arrow", "direction": "up", "role": "callout"},
            ],
        })
    scenes.append({
        "id": "outro",
        "duration": 7,
        "background": None,
        "layers": [{"type": "text", "text": "Observe. Test. Compare.", "role": "cta"}],
    })
    motions = ("slide-left", "slide-right", "float", "center")
    for index, scene in enumerate(scenes):
        scene["motion"] = motions[index % len(motions)]
    target_duration = 60.0
    current_duration = sum(float(scene["duration"]) for scene in scenes)
    scale = target_duration / current_duration if current_duration else 1
    for scene in scenes:
        scene["duration"] = round(float(scene["duration"]) * scale, 3)
    # Correct rounding drift on the outro so the final duration is exactly 60s.
    rounded_duration = sum(float(scene["duration"]) for scene in scenes)
    scenes[-1]["duration"] = round(float(scenes[-1]["duration"]) + target_duration - rounded_duration, 3)
    return {"width": WIDTH, "height": HEIGHT, "fps": FPS, "duration": target_duration, "scenes": scenes}


def write_manifest(job_id, manifest):
    path = MOTION_RENDERS_DIR / f"{job_id}.manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_manifest(job_id, manifest, audio_path=None):
    """Render scene cards with deterministic overlays and join them to MP4."""
    binary = ffmpeg_path()
    if not binary:
        raise RuntimeError("FFmpeg belum terpasang; renderer belum dapat membuat MP4")
    manifest_path = write_manifest(job_id, manifest)
    subtitle_path = write_srt(job_id, manifest)
    output = MOTION_RENDERS_DIR / f"{job_id}.mp4"
    duration = sum(float(scene.get("duration", 0)) for scene in manifest.get("scenes", []))
    with tempfile.TemporaryDirectory(prefix=f"motion-{job_id}-") as temp_dir:
        temp = Path(temp_dir)
        clips = []
        for index, scene in enumerate(manifest.get("scenes", [])):
            seconds = max(float(scene.get("duration", 1)), 1)
            text = next((layer.get("text") for layer in scene.get("layers", [])
                         if layer.get("type") == "text"), scene.get("id", "GoldGen"))
            text_file = temp / f"text-{index}.txt"
            text_file.write_text(str(text), encoding="utf-8")
            clip = temp / f"scene-{index}.mp4"
            # textfile avoids shell escaping and keeps facts out of a filter string.
            vf = (
                f"drawtext=font='Arial':textfile='{text_file.as_posix()}':"
                "fontcolor=white:fontsize=64:line_spacing=14:"
                "box=1:boxcolor=black@0.55:boxborderw=28:"
                "fade=t=in:st=0:d=0.35,fade=t=out:st=" + str(max(seconds - 0.35, 0.1)) + ":d=0.35"
            )
            motion = scene.get("motion", "center")
            if motion == "slide-left":
                position = "x='(w-text_w)*min(t/0.6,1)':y=(h-text_h)/2"
            elif motion == "slide-right":
                position = "x='(w-text_w)*(1-min(t/0.6,1))':y=(h-text_h)/2"
            elif motion == "float":
                position = "x=(w-text_w)/2:y='(h-text_h)/2+sin(t*2)*18'"
            else:
                position = "x=(w-text_w)/2:y=(h-text_h)/2"
            vf = vf.replace("box=1:boxcolor=black@0.55:boxborderw=28:",
                            "box=1:boxcolor=black@0.55:boxborderw=28:" + position + ",")
            background = scene.get("background")
            background_path = Path(background) if background else None
            if background_path and background_path.is_file():
                source = ["-loop", "1", "-i", str(background_path)]
                vf = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}," + vf
            else:
                source = ["-f", "lavfi", "-i", f"color=c=0x11100d:s={WIDTH}x{HEIGHT}:r={FPS}"]
            subprocess.run([
                binary, "-y", *source, "-vf", vf, "-t", str(seconds), "-an",
                "-pix_fmt", "yuv420p", str(clip),
            ], check=True, capture_output=True, text=True)
            clips.append(clip)
        concat_file = temp / "concat.txt"
        concat_file.write_text("\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8")
        command = [binary, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
        if audio_path and Path(audio_path).is_file():
            command += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-c:a", "aac", "-shortest"]
        else:
            command += ["-c", "copy"]
        command += ["-movflags", "+faststart", str(output)]
        subprocess.run(command, check=True, capture_output=True, text=True)
    return {"output_path": str(output), "manifest_path": str(manifest_path),
            "subtitle_path": str(subtitle_path), "duration": duration}

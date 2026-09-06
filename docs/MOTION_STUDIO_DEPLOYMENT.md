# GoldGen Motion Studio

Motion Studio is isolated from the existing image poster. It uses its own
database under `motion_studio/data`, assets under `motion_studio/assets`, and
renders under `motion_studio/renders`.

## Local prerequisites

- Python environment with the existing `requirements.txt`
- FFmpeg and ffprobe available on `PATH`
- `GEMINI_API_KEY` only when Gemini TTS is enabled
- A working GoldGen dashboard session for the protected UI/API

## Worker

Start the worker as a separate process:

```text
python motion_worker.py
```

Do not add Motion Studio jobs to the existing auto-poster scheduler. On the
VPS, run this worker as a separate service/process with its own restart policy.

## Manual publishing boundary

The first production mode is manual MP4 download. Automatic Facebook video
publishing should remain disabled until the render QA and staging tests pass.

The future publisher is guarded by `MOTION_AUTO_PUBLISH_ENABLED=false` by
default. Do not enable it until page permissions, duplicate protection, and
manual review have been verified on staging.

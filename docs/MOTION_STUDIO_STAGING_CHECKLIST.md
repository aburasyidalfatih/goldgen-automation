# Motion Studio staging checklist

## Before deploy

- [ ] Set a non-default `DASHBOARD_PIN` and stable `SECRET_KEY`.
- [ ] Configure `GEMINI_API_KEY` only in the VPS environment/secrets store.
- [ ] Keep `MOTION_AUTO_PUBLISH_ENABLED=false`.
- [ ] Back up `data/` and the existing `generated_images/` volume.
- [ ] Confirm the VPS has enough disk for `goldgen_motion` renders.

## Deploy

```text
docker compose config --quiet
docker compose build
docker compose up -d goldgen-bot goldgen-motion-worker
docker compose ps
```

The dashboard and worker must share the `goldgen_motion` volume. Do not run
the Motion worker inside the existing auto-poster process.

## Functional gates

- [ ] Dashboard health endpoint returns 200.
- [ ] Motion Video menu opens after dashboard login.
- [ ] A topic creates a Motion job with status `draft`.
- [ ] Worker changes the job to `ready` or a visible `failed` state.
- [ ] Preview and manual MP4 download work.
- [ ] Render is 1080x1920 portrait and passes QA.
- [ ] Existing image generation and scheduled image posting remain healthy.
- [ ] Gemini TTS is tested with a real staging key, if voice-over is enabled.

## Publishing gate

Only after the functional gates pass should page permissions and video upload
be tested manually. Keep automatic publishing disabled until duplicate
protection, failure retry, caption review, and page-level rate limits have
been verified.

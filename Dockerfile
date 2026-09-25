FROM node:24.21.0-bookworm-slim AS motion-build
WORKDIR /build/motion_engine
COPY motion_engine/package*.json ./
RUN npm ci --no-audit --no-fund
COPY motion_engine/ ./
RUN npm run build

FROM python:3.14.7-slim-bookworm
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg chromium fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=motion-build /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# /app/data ditutup volume permanen di produksi; salinan katalog ini yang
# membawa perubahan layouts.json dari repo ke server (lihat core/layout_policy.py).
RUN mkdir -p /app/catalog && cp data/layouts.json /app/catalog/
COPY --from=motion-build /build/motion_engine /app/motion_engine
COPY --from=motion-build /build/static/motion /app/static/motion
ENV MOTION_BROWSER_PATH=/usr/bin/chromium
ENV MOTION_RENDER_CONCURRENCY=1
EXPOSE 18794
CMD ["python", "api.py"]

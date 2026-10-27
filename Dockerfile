# Build the CPU-only Bodhan web app with PDF/OCR assets and no local speech models.
FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_XET=1 \
    HF_HUB_DOWNLOAD_TIMEOUT=120 \
    UV_HTTP_TIMEOUT=120

COPY --from=ghcr.io/astral-sh/uv:0.10.12@sha256:72ab0aeb448090480ccabb99fb5f52b0dc3c71923bffb5e2e26517a1c27b7fec /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/requirements-lite.txt /opt/lite/requirements.txt
RUN UV_CONCURRENT_DOWNLOADS=4 uv pip install --system --no-cache --only-binary=:all: \
        --index-strategy unsafe-best-match -r /opt/lite/requirements.txt \
    && uv pip check

COPY docker/prefetch_models.py docker/smoke.py /opt/lite/
RUN python /opt/lite/prefetch_models.py

COPY src/ ./src/
COPY web/ ./web/
COPY podcast_examples/ ./podcast_examples/
COPY config.yaml ./config.yaml

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/.api_tmp /app/Content /app/Audio \
    && chown app:app /app/.api_tmp /app/Content /app/Audio

# These apply only to this image, never to the host's normal Python setup.
ENV PODCAST_LITE=1 \
    DOCLING_DEVICE=cpu \
    DOCLING_ARTIFACTS_PATH=/opt/docling-models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    OMP_NUM_THREADS=4 \
    HOME=/home/app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).close()"
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

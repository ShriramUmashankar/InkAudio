# Docker Lite

Lite packages the web app for **Bodhan AI with typed feedback**. It runs on CPU,
including machines that happen to have a GPU. Qwen generation and transcription
are disabled in the UI and rejected by the API. All four saved examples remain
playable, including the episodes originally generated with Qwen.

## Start

Install Docker Engine with Compose v2+, or Docker Desktop using Linux containers
(Windows: WSL 2). From the repository root:

```bash
cp .env.example .env
```

In PowerShell, use `Copy-Item .env.example .env`. Edit `.env` with your own keys:

| Key | Needed for |
| --- | --- |
| `GEMINI_API_KEY` | Script generation and revisions |
| `BODHAN_TTS` | Bodhan speech synthesis |
| `BODHAN_TRANSLATION` | Indic podcasts; the repository defaults to Tamil |

English bypasses translation. Existing examples can be played without keys.
Credentials must have access to the providers/models configured in `config.yaml`.

```bash
docker compose up --build
```

Open http://localhost:8000. To keep an existing server on port 8000, add
`PODCAST_PORT=8001` to `.env` before starting Compose, then open port 8001.
The port is bound to localhost. No GPU driver/toolkit or local Python installation
is needed. Never run the native `models/download_models.py` for Lite.

The first build needs internet for Docker Hub, Debian, PyPI, the PyTorch CPU index,
Hugging Face, and ModelScope. It can take several minutes and downloads several
hundred MB of PDF models in addition to Python/system dependencies. Subsequent
builds reuse Docker's cache. PDF conversion itself then needs no model downloads;
live Gemini/Bodhan requests still need internet, quota, and valid credentials.

Use a small English source PDF first. Select English for the podcast if you only
have Gemini and Bodhan TTS keys. For Indic podcasts, configure the translation key
and choose the target language in the website.

## Platform and runtime boundaries

- The Docker base and dependency lock target Linux `amd64` and `arm64`. Runtime
  verification here covers Linux `amd64` only. Windows and macOS use Linux
  containers through Docker Desktop; ARM64, macOS, and Windows runtime behavior
  has not been verified here. No `platform: linux/amd64` override is used.
- Allocate approximately 8 GB RAM to Docker and start with at least 10 GB free
  disk for building. These are starting recommendations, not measured minimums;
  large/scanned PDFs can require more resources and take longer.
- This is a local, single-user application. One Uvicorn worker preserves its
  single active job model. It is not a multi-user/public hosting configuration.
- Website job files are temporary and cleaned by the application. Download your
  MP3 before finishing or stopping the app; jobs do not resume after a restart.
- The container runs as a non-root user. It does not bind-mount your checkout,
  local models, `Content/`, `Audio/`, or `.api_tmp/`. Changes on the host require
  a rebuild to appear in the container.
- `PODCAST_LITE=1` is set only by the image/Compose. Without it, native startup
  retains Qwen and transcription behavior. Do not turn it off inside the Lite
  image: the optional dependencies/models are deliberately absent.
- Speech feedback is not included, even on an NVIDIA machine. Typed feedback
  uses the existing revision pipeline.

## Stop, inspect, and update

```bash
docker compose ps
docker compose logs --tail=100 lite
docker compose down
```

Health checks test the HTTP process, not external credentials or provider uptime.
If generation fails, the Progress page retains the error. Check credentials,
model access, quota, internet connectivity, and the logs. An interrupted build can
be retried with `docker compose up --build`; keep TLS verification enabled.

After changing code/configuration, rebuild with `docker compose up --build`.
After changing only credentials, use `docker compose up -d --force-recreate`.
Secrets are supplied at runtime, excluded from the build context, and never
baked into the image. Avoid sharing unredacted `docker compose config` output.

To remove the built image after stopping Compose:

```bash
docker image rm podcast-generation-lite:local
```

This leaves your host models and other Docker projects alone. There are no Lite
model volumes to delete; required PDF assets live in the image.

## Verification

With the image built, verify CPU PDF conversion and OCR without any network:

```bash
docker run --rm --network none podcast-generation-lite:local python /opt/lite/smoke.py --pdf
```

With Compose running, check health, capabilities, rejection of unsupported
requests, and range playback for all four example MP3s:

```bash
docker compose exec lite python /opt/lite/smoke.py --url http://127.0.0.1:8000
```

The source regression tests make no live provider calls:

```bash
PYTHONPATH=. ~/.local/bin/pytest docker/test_lite.py -q
node web/js/regressions.test.cjs
```

The existing `tests/` suite cleans `.api_tmp/`; run it in a separate checkout if
another app instance is using your working directory.

Verification on 2026-10-27 (India time), Linux `amd64`:

- Rebuilt the current image and started an isolated Compose project; its health
  check passed. The resulting image is approximately 2.69 GB uncompressed.
- Converted native-text and scanned PDFs on CPU with `--network none` (12.4 s
  for both tiny fixtures); the image has no Qwen, Whisper, or bitsandbytes package.
- HTTP smoke checks passed for capabilities, early Qwen/STT rejection, and range
  playback of all four saved MP3s.
- All 159 Python regressions and 9 Node checks passed. Browser checks confirmed
  Lite mode controls, disabled transcription, available typed feedback, and all
  four examples playing with synchronized captions, seeking, and animation.
- Live PDF upload → Gemini actor/critic → Bodhan Tamil translation/speech → MP3
  passed through the API: two turns, 30 spoken words, 17.105 seconds of audio.
  A typed revision produced 21 words / 11.393 seconds and synthesized only turn
  `0002`; turn `0001` retained identical text and WAV bytes. Both MP3s decoded
  as non-silent audio and matched their scripts/timelines.

The live check used real configured credentials and providers. A disposable
test harness appended brevity instructions and enforced two turns / at most
50 words before synthesis; production prompts were unchanged. Python/Node
regressions mock providers; health checks alone do not establish successful
cloud generation.

ARM64 wheel resolution was checked during the earlier Lite setup, but ARM64
builds and native macOS/Windows execution have not been runtime-tested here.
GPU speech generation and native-speaker pronunciation quality are outside
these container checks.

## Dependency/model maintenance

The Python base and uv build tool are pinned to multi-platform digests. Downloads
use four concurrent connections to avoid stalling constrained networks. Lite
dependencies have a
separate universal lock; native speech dependencies live in `requirements.txt`.
PDF layout/table repositories use fixed Hugging Face commit revisions in `prefetch_models.py`;
RapidOCR 3.9.2 supplies versioned OCR model URLs. Only required PDF assets are
downloaded. Runtime Hugging Face/Transformers access is offline.

Regenerate the lock using uv 0.10.12 after deliberately updating the input:

```bash
uv pip compile docker/requirements-lite.in --universal --python-version 3.11 --index-strategy unsafe-best-match --emit-index-url --output-file docker/requirements-lite.txt
```

The two indexes are PyPI and the official PyTorch CPU index. Verify both target
architectures still have binary wheels, rebuild, and repeat the network-disabled
PDF smoke test whenever updating dependencies or model revisions. Debian system
packages receive current Bookworm updates at build time, so independent builds
are not promised to be byte-identical.

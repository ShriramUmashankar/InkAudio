# Podcast Generation Pipeline — Project Summary

## Overview
Local PDF → Markdown → LangGraph Actor-Critic script → TTS → MP3. Single-user localhost tool with FastAPI backend + vanilla JS frontend. No build step, no queue, one job at a time.

## Models & Requirements

| Component | Model | Runs | Needs |
|-----------|-------|------|-------|
| **Script LLM** (Actor + Critic) | Gemini 2.5 Flash Lite (`gemini-2.5-flash-lite`) | Cloud API | `GEMINI_API_KEY` in `.env` (10 RPM free tier; client paces at ~6s/call) |
| **TTS — Bodhan** | Indic-speak (45 Indian voices) | Cloud API | `BODHAN_API_KEY` in `config.yaml` → `tts.bodhan_api_key` |
| **TTS — Qwen Custom Voice** | Qwen3-TTS 1.7B (9 preset speakers) | **Local** (4-bit quantized) | `models/download_models.py` fetches `Qwen/Qwen3-TTS` to `models/` |
| **TTS — Qwen Voice Design** | Qwen3-TTS Voice Design 1.7B (text-to-voice) | **Local** (4-bit) | Same model dir, separate checkpoint |
| **STT** | faster-whisper (default `base`) | Local (loads on demand) | `config.yaml` → `stt:` or env `STT_MODEL/DEVICE/COMPUTE_TYPE` |

## Configuration
- `config.yaml` — all non-secret settings (LLM endpoints, TTS voices, pipeline params)
- `.env` — `GEMINI_API_KEY` (single key for both actor/critic)
- `src/tts_requirements/*.yaml` — per-mode defaults (bodhan, custom_voice, voice_design)

## Pipeline Stages (CLI)
```bash
python -m src.pipeline --pdf Content/input.pdf
# Stages: ingest → script → tts → stitch
# Flags: --skip-ingest --skip-script --skip-stitch --no-tts --force-ingest --revise --feedback <file>
```

## API (FastAPI, `uvicorn src.api.main:app`)
| Endpoint | Purpose |
|----------|---------|
| `POST /api/job/{mode}` | Start generation (`mode`: bodhan, custom_voice, voice_design) |
| `GET /api/job` | Status polling |
| `GET /api/job/events` | SSE progress stream |
| `GET /api/job/timeline` | Per-turn timestamps for sync |
| `GET /api/job/script` | Generated script JSON |
| `GET /api/job/result` | Final MP3 |
| `POST /api/job/revise` | Human feedback revision loop |
| `POST /api/job/finish` | Cleanup + model unload |
| `POST /api/job/terminate` | Cancel running job + unload |
| `POST /api/transcribe` | STT (audio → transcript) |
| `GET /api/tts/template?mode=` | Default TTS params |

## Frontend Pages (served from `/`)
- **Generate** (`/`) — PDF upload, TTS mode, voice pickers, custom dropdowns
- **Progress** (`/progress.html`) — SSE stage stepper, shimmer bar, rotating dots, localStorage restore
- **Result** (`/result.html`) — Custom audio player, synced script highlight, click-to-seek, revision UI, mic/voice feedback
- **Transcribe** (`/transcribe.html`) — File upload + mic record → transcript with copy button

## Revision Loop
1. Write notes to `Content/feedback.txt`
2. Run `python -m src.pipeline --revise`
3. Editor LLM locates turns → Critic approves → re-synthesizes changed turns only → re-stitch

**API voice feedback**: Record/upload → `POST /api/transcribe` → edit transcript → `POST /api/job/revise`

## Key Invariants
- Turn `speaker` = `"Host 1"` or `"Host 2"` exactly
- `turn_id` = zero-padded global order (`0001`…)
- Bodhan: Voice only (lang/style use template defaults)
- Qwen Custom: Speaker dropdown + instruction textarea
- Qwen Voice Design: 7-dimension guide + per-host description textarea

## Run
```bash
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY
python models/download_models.py   # fetch Qwen 1.7B checkpoints
uvicorn src.api.main:app --reload
# open http://localhost:8000
```

## Tests
```bash
~/.local/bin/pytest tests/ -q   # 61 tests, mocked LLM/TTS
```
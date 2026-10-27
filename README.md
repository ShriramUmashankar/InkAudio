# InkAudio

InkAudio turns a PDF into a two-host podcast, with a web interface and CLI. An actor-critic loop refines the script, optional Indic translation adapts the dialogue, and speech synthesis produces a downloadable MP3. Choose Docker Lite for the easiest evaluation setup, or install the full project locally to use Qwen voices and transcription.

![InkAudio pipeline flowchart: PDF ingestion, script generation and review, speech synthesis, and audio stitching](flowchart.svg)

## Docker Lite (recommended for evaluation)

Lite runs on CPU and includes PDF conversion, Bodhan speech and Indic translation,
typed feedback/revisions, and all four saved examples. **Qwen generation and
speech-to-text are disabled.** No GPU or local Python installation is needed.

Install Docker with Compose (Docker Desktop with Linux containers on Windows/macOS),
then clone and start the app:

```bash
git clone https://github.com/ShriramUmashankar/InkAudio.git
cd InkAudio
cp .env.example .env
```

Edit `.env`: set `GEMINI_API_KEY` and `BODHAN_TTS` for generation, plus
`BODHAN_TRANSLATION` for Indic podcasts. **The default language is Tamil**;
select English in the app to skip translation. Saved examples work without keys.
In Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.

```bash
docker compose up --build
```

Open http://localhost:8000. Upload a PDF on Generate, or visit Examples to play
saved episodes. The first build downloads dependencies and PDF/OCR models;
live generation requires internet and valid API credentials.

Stop with Ctrl+C, then `docker compose down`. Download your MP3 before finishing
or stopping the app; generated jobs are temporary. If port 8000 is busy, add
`PODCAST_PORT=8001` to `.env` and open http://localhost:8001.
See [Docker details and troubleshooting](docker/README.md) for resources and verification.

## Full project (native installation)

Manage Python, system dependencies, and local speech models yourself. Use Python
3.11 and install **FFmpeg and SoX** on your system (`sudo apt install ffmpeg sox`
on Ubuntu/Debian, or `brew install ffmpeg sox` on macOS). Local Qwen generation
is intended for a compatible NVIDIA/CUDA environment; see the
[native configuration and hardware notes](src/README.md#native-hardware-and-configuration).

```bash
git clone https://github.com/ShriramUmashankar/InkAudio.git
cd InkAudio
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows, create the environment with `py -3.11 -m venv .venv`, activate it with
`.venv\Scripts\Activate.ps1`, and copy the environment file with
`Copy-Item .env.example .env`.

Fill in the same API keys described above, then download the Qwen and transcription
models and start the web app:

```bash
python models/download_models.py
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and choose Bodhan, Qwen Custom Voice, or Qwen Voice Design.
Stop with Ctrl+C. The checked-in configuration defaults to Bodhan/Tamil; Qwen
uses English. See [pipeline, CLI, configuration, and development details](src/README.md)
for the CLI and optional CPU transcription settings.

# Running the Pipeline from Outside `src/`

All commands are run from the **project root** (`PodcastGeneration/`), not from inside `src/`.

```bash
python -m src.pipeline [options]
```

The `src.pipeline` module is the CLI entrypoint. It orchestrates the full pipeline: ingest → script → TTS → stitch.

---

## How to Run

### Fresh generation (all stages)

```bash
python -m src.pipeline --pdf Content/input.pdf
```

Runs: ingest → script → TTS → stitch. Outputs `Audio/final_podcast.mp3`.

### Skip stages

```bash
# Skip PDF → Markdown (use existing Content/*.md)
python -m src.pipeline --pdf Content/input.pdf --skip-ingest

# Skip script generation (re-synthesize audio for existing script.json)
python -m src.pipeline --skip-script

# Skip final MP3 stitching
python -m src.pipeline --skip-stitch

# Script only, no audio
python -m src.pipeline --no-tts

# Re-convert PDF even if Markdown already exists
python -m src.pipeline --pdf Content/input.pdf --force-ingest
```

### Revision

```bash
# Write feedback to Content/feedback.txt first, then:
python -m src.pipeline --revise

# Or specify a custom feedback file
python -m src.pipeline --revise --feedback my_notes.txt
```

Loads `script.json`, sends your notes + the full script to the revision graph, merges approved edits, re-synthesizes only changed turns, and re-stitches.

---

## Flags Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--pdf <path>` | From `config.yaml` | Input content PDF path |
| `--skip-ingest` | off | Skip PDF → Markdown conversion |
| `--skip-script` | off | Skip script generation; re-TTS existing `script.json` |
| `--skip-stitch` | off | Skip final MP3 stitching |
| `--no-tts` | off | Stop after script generation, skip TTS entirely |
| `--force-ingest` | off | Re-convert PDF even if Markdown exists |
| `--revise` | off | Run revision loop from feedback file |
| `--feedback <path>` | `Content/feedback.txt` | Path to feedback notes for `--revise` |
| `--config <path>` | `config.yaml` | Custom config YAML path |

---

## What Each Module Does

| Module | Responsibility |
|--------|---------------|
| `config.py` | `load_settings()` reads `config.yaml` + `.env` into a `Settings` dataclass. Validates that all required API keys are present. |
| `llm_client.py` | `LLMClient` — OpenAI-compatible wrapper with retry/backoff and optional conversation logging. Also provides `extract_json()` and `validate_turns()` for robust LLM output parsing. |
| `ingest.py` | `convert_pdf()` and `convert_questions_pdf()` use docling to convert PDFs to Markdown. Idempotent (skips if `.md` exists unless `--force-ingest`). |
| `graph.py` | LangGraph `StateGraph`: Actor → Critic → Router for script generation. Also `build_revision_graph()` for the Editor → Critic → Router revision loop. |
| `script_gen.py` | `generate_script()` runs the graph, re-numbers turns globally (`0001`…), writes `script.json`, then synthesizes + stitches. `revise_script()` handles the revision flow. |
| `tts.py` | `synthesize_all()` loads Qwen3-TTS (local 4-bit → HF fallback) or calls Bodhan API. Supports `custom_voice`, `voice_design`, and `bodhan` modes. Writes per-turn WAVs with deterministic seeds. |
| `stitch.py` | `stitch()` sorts WAVs by numeric `turn_id`, concatenates with `silence_ms` gaps via pydub, exports `final_podcast.mp3`. Writes `timeline.json`. |
| `evaluator.py` | Classifies questions from the questions PDF as answerable vs unanswerable against the content. |
| `pipeline.py` | CLI entrypoint. Parses arguments and dispatches stages. Also supports `--revise`. |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config.yaml` | LLM endpoints, TTS mode/voices, pipeline params (`max_loops`, `silence_ms`, etc.) |
| `.env` | `GEMINI_API_KEY`, `BODHAN_TTS` |
| `src/tts_requirements/bodhan.yaml` | Bodhan host voice names and languages |
| `src/tts_requirements/custom_voice.yaml` | Qwen speaker names and style instructions |
| `src/tts_requirements/voice_design.yaml` | Per-host natural-language voice descriptions |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes | Single key for both actor and critic LLMs |
| `BODHAN_TTS` | Only if `tts.mode: bodhan` | Bodhan TTS API key |
| `STT_DEVICE` | No | STT compute device (`cuda` / `cpu`) |
| `STT_COMPUTE_TYPE` | No | STT compute type (`float16` / `int8`) |
| `STT_MODEL` | No | STT model path (default: `small.en`) |

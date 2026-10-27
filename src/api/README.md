# Podcast HTTP API

This package connects the browser interface to the Python podcast pipeline. It
keeps one current job in process memory and puts its uploads and generated files
in the shared `.api_tmp/` directory. It has no job IDs, persistent job database,
or waiting queue.

| File | Purpose |
| --- | --- |
| [`__init__.py`](__init__.py) | Marks the API package; it performs no startup work. |
| [`main.py`](main.py) | Builds the FastAPI application, registers Lite and CORS middleware and all routers, mounts saved examples and the static website when their directories exist, and registers shutdown cleanup. |
| [`capabilities.py`](capabilities.py) | Provides `GET /api/health` and `GET /api/capabilities`. Its ASGI middleware rejects local Qwen generation and transcription POST requests when `PODCAST_LITE=1`, before FastAPI parses their upload bodies. |
| [`job_queue.py`](job_queue.py) | Owns `JobRecord`, the single current job, background worker supervision, pipeline orchestration, progress events, cancellation checkpoints, and temporary-file cleanup. |
| [`model_manager.py`](model_manager.py) | Lazily caches local Qwen TTS models by mode, unloads the previously active Qwen mode when switching modes, and clears model references and available CUDA cache on cleanup. Bodhan returns no local model. |
| [`models.py`](models.py) | Defines `RevisionRequest` with nonempty feedback text and `TranscriptResponse` with a transcript string. |
| [`routes/`](routes/README.md) | Implements upload, revision, status, streaming, retrieval, cancellation, metadata, and transcription endpoints. See the route guide for the endpoint mapping. |

## Request and worker flow

The generation route validates the TTS mode and language options, reserves a
`JobRecord`, saves the uploaded content PDF and optional questions PDF, and
schedules processing. A second generation request gets HTTP 409 while the
current record is `running`. A later generation request replaces a terminal
record after unloading its TTS mode and removing its files.

`run_job()` schedules `_run_job()`, which sends synchronous pipeline work to
`asyncio.to_thread`. The worker loads settings, directs content and audio output
to the job directory, and runs PDF ingestion, optional question evaluation,
Actor-Critic script generation, optional Bodhan translation, per-turn synthesis,
and stitching. LLM conversations go to `.api_tmp/llm_log.md`. The website uses
strict synthesis errors and passes the expected turns to stitching, so missing
turn audio fails the job. The resulting files include `script.json`, turn WAVs,
`final_podcast.mp3`, and `timeline.json`; Bodhan also retains English source and
language metadata for revision.

The worker updates the record's `stage` and `progress` and sends SSE messages to
registered listeners through their event loops. Status polling and initial and
terminal SSE snapshots read the retained record, allowing a page refresh to
recover the current lifecycle state. Completed output remains available through
the retrieval routes until finish, replacement by another job, or shutdown.
These routes check that their files exist rather than requiring completed status.

Revision reuses a completed record and its directory. It resets the record to
`running`, edits the English source using feedback, translates changed text
where needed, synthesizes changed spoken turns, and stitches the updated audio
when those turns changed. Unchanged turn audio is reused.

## Cancellation and model ownership

Finish or terminate during generation sets `cancel_requested` and returns
`cancelling`. The record stays reserved while the thread reaches a cooperative
checkpoint; an in-flight provider call may need to finish first. The supervisor
then marks the record `terminated`, unloads its TTS mode, and removes its files.
Failures similarly retain the failed record and error while cleaning their
assets. A terminal record remains visible until finish or a replacement job.
Finishing a terminal job clears the record, unloads its mode, and removes files.
Shutdown requests cancellation, clears the current record, removes the shared
temporary directory, and unloads all cached TTS models.

Qwen models belong to the shared `ModelManager`. Transcription has a separate
faster-whisper model in `routes/transcribe.py`: settings are cached, but the
model loads on demand and is released in the request's `finally` block. Saved
`podcast_examples/` assets are mounted separately and are never job cleanup
targets.

`main.py` registers fixed finish and revision routes before the dynamic
`POST /api/job/{mode}` route, and mounts the website at `/` after the API routes.
Health reports process availability without loading API credentials or models;
capabilities reports the feature set selected by the Lite environment flag.

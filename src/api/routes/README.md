# API routes

Each module exports an `APIRouter` for registration in
[`../main.py`](../main.py). Job routes operate on the same current
[`JobRecord`](../job_queue.py), so callers do not supply a job ID. The
[API package guide](../README.md) explains worker execution, shared files,
model ownership, and cleanup.

| File | Endpoints and role |
| --- | --- |
| [`__init__.py`](__init__.py) | Marks the routes package; it registers no endpoints itself. |
| [`generate.py`](generate.py) | `GET /api/tts/languages` returns language codes and the configured default. `GET /api/tts/template?mode=...` returns a supported mode's YAML voice template. `POST /api/job/{mode}` validates options, saves PDF uploads, reserves the single job, and schedules generation. |
| [`status.py`](status.py) | `GET /api/job` returns lifecycle state or `idle`. `GET /api/job/events` streams SSE updates. `GET /api/job/result`, `/api/job/script`, `/api/job/timeline`, and `/api/job/questions` return the MP3, spoken script, playback timing, and question evaluation report. |
| [`revise.py`](revise.py) | `POST /api/job/revise` accepts JSON feedback for a completed job, resets its lifecycle state, and schedules revision using its existing assets. |
| [`finish.py`](finish.py) | `POST /api/job/finish` requests cancellation for running work or releases a terminal job. `POST /api/job/terminate` requests cancellation of a running job and rejects requests without one. |
| [`transcribe.py`](transcribe.py) | `POST /api/transcribe` accepts an audio upload, loads faster-whisper on demand, joins recognized segments, and returns a transcript. Its request cleanup releases the model. |

## Endpoint relationships

Generation accepts a required multipart `content_pdf`, optional `questions_pdf`,
and optional `config` containing a JSON object. Supported modes are `bodhan`,
`custom_voice`, and `voice_design`. Options include host voice overrides,
`max_loops`, and `podcast_language`; Indic languages require Bodhan. The language
and template endpoints read configuration files without loading API credentials.
Generation returns HTTP 202 when scheduled, HTTP 409 if another job is running,
and abandons its reservation if saving uploads fails.

Poll `/api/job` or subscribe to `/api/job/events` after scheduling. Snapshots
include status, mode, language, timestamps, error, stage, progress, and the
cancellation flag. The SSE generator registers a listener for that job, emits an
initial snapshot, forwards events with keepalives, drains queued events after
termination, sends a final snapshot and `done` event, and removes the listener
when the stream closes. Snapshot and progress messages are `data:` frames whose
JSON object contains `event` and a JSON-encoded `data` string.

The retrieval routes return HTTP 404 when the current job or requested artifact
is absent. The script is the spoken script, including translated text for an
Indic podcast; timeline timings align its turns with the MP3. Questions are
available only when an evaluation report exists.

To revise, send nonempty text as `{"feedback": "..."}` to
`/api/job/revise` after completion, then use the same status and retrieval routes.
Voice feedback first goes to `/api/transcribe`; the browser lets the user edit
the returned transcript before submitting it as revision feedback. Transcription
does not itself start a revision or reserve a podcast job.

Finish and terminate return `cancelling` while a worker is still running.
Cooperative cancellation keeps the job reserved until the worker exits; terminal
errors remain visible even after their files are removed. Finish after a terminal
state clears the record and its remaining files. Finish with no job returns
`cleaned_up`.

Health and capability endpoints live in [`../capabilities.py`](../capabilities.py),
outside this directory. Its Lite middleware blocks Qwen generation and
transcription POST requests when `PODCAST_LITE=1`; Bodhan generation and typed
revision feedback remain available. The fixed finish and revise POST routes are
registered before the dynamic generation route so their names are not treated
as TTS modes.

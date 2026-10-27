/* HTTP helpers for job control, generated assets, voice configuration, and transcription. */
/** Normalize HTTP status and tolerate responses without a JSON body. */
async function _json(r) {
  const body = await r.json().catch(() => null);
  return { ok: r.ok, status: r.status, body };
}

/** Upload source PDFs and optional overrides to start the selected TTS mode. */
export async function startJob(mode, contentPdf, questionsPdf, config) {
  const fd = new FormData();
  fd.append("content_pdf", contentPdf);
  if (questionsPdf) fd.append("questions_pdf", questionsPdf);
  if (config) fd.append("config", JSON.stringify(config));
  return _json(await fetch(`/api/job/${mode}`, { method: "POST", body: fd }));
}

/** Fetch the current job lifecycle state and progress. */
export async function getJobStatus() {
  return _json(await fetch("/api/job"));
}

/** Fetch the current job’s dialogue turns. */
export async function getScript() {
  return _json(await fetch("/api/job/script"));
}

/** Fetch turn timings for synchronized playback. */
export async function getTimeline() {
  return _json(await fetch("/api/job/timeline"));
}

/** Fetch the answerable and unanswerable question report. */
export async function getQuestions() {
  return _json(await fetch("/api/job/questions"));
}

/** Fetch default host settings for a TTS engine. */
export async function getTemplate(mode) {
  return _json(await fetch(`/api/tts/template?mode=${encodeURIComponent(mode)}`));
}

/** Fetch supported podcast languages and the configured default. */
export async function getLanguages() {
  return _json(await fetch("/api/tts/languages"));
}

/** Fetch deployment-specific TTS and transcription availability. */
export async function getCapabilities() {
  return _json(await fetch("/api/capabilities"));
}

/** Submit textual feedback to revise the current podcast. */
export async function revise(feedback) {
  return _json(await fetch("/api/job/revise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  }));
}

/** Request cooperative cancellation of the active generation. */
export async function terminateJob() {
  return _json(await fetch("/api/job/terminate", { method: "POST" }));
}

/** Release the current job and clean its temporary assets. */
export async function finishJob() {
  return _json(await fetch("/api/job/finish", { method: "POST" }));
}

/** Upload an audio file for server-side speech recognition. */
export async function transcribe(file) {
  const fd = new FormData();
  fd.append("file", file);
  return _json(await fetch("/api/transcribe", { method: "POST", body: fd }));
}

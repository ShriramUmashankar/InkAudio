async function _json(r) {
  const body = await r.json().catch(() => null);
  return { ok: r.ok, status: r.status, body };
}

export async function startJob(mode, contentPdf, questionsPdf, config) {
  const fd = new FormData();
  fd.append("content_pdf", contentPdf);
  if (questionsPdf) fd.append("questions_pdf", questionsPdf);
  if (config) fd.append("config", JSON.stringify(config));
  return _json(await fetch(`/api/job/${mode}`, { method: "POST", body: fd }));
}

export async function getJobStatus() {
  return _json(await fetch("/api/job"));
}

export async function getScript() {
  return _json(await fetch("/api/job/script"));
}

export async function getTimeline() {
  return _json(await fetch("/api/job/timeline"));
}

export async function getQuestions() {
  return _json(await fetch("/api/job/questions"));
}

export async function getTemplate(mode) {
  return _json(await fetch(`/api/tts/template?mode=${encodeURIComponent(mode)}`));
}

export async function revise(feedback) {
  return _json(await fetch("/api/job/revise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  }));
}

export async function terminateJob() {
  return _json(await fetch("/api/job/terminate", { method: "POST" }));
}

export async function finishJob() {
  return _json(await fetch("/api/job/finish", { method: "POST" }));
}

export async function transcribe(file) {
  const fd = new FormData();
  fd.append("file", file);
  return _json(await fetch("/api/transcribe", { method: "POST", body: fd }));
}
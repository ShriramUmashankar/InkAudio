const N = {
  wait:      { x: 130,  y: 370, t: "WAIT / START", s: "waits for a content PDF", start: true, l: "API server idle — the start and finish of every run." },
  ingest:    { x: 370,  y: 370, t: "INGEST",      s: "PDF → Markdown", l: "The PDF is converted to clean Markdown (docling)." },
  questions: { x: 430,  y: 130, t: "QUESTIONS",   s: "optional PDF → Markdown", opt: true, l: "An optional questions PDF, parsed to Markdown. Skipped when none is uploaded." },
  evaluator: { x: 660,  y: 130, t: "EVALUATOR",   s: "answerable vs unanswerable", opt: true, l: "Splits questions into answerable vs unanswerable; only answerable ones become script context." },
  actor:     { x: 660,  y: 370, t: "ACTOR",       s: "drafts script as JSON turns", l: "The writing LLM: drafts the whole script as JSON turns, alternating Host 1 / Host 2." },
  critic:    { x: 910,  y: 370, t: "CRITIC",      s: "checks draft vs content", l: "The review LLM: checks the draft against the source content." },
  router:    { x: 660,  y: 600, t: "ROUTER",      s: "approved → next · else loop", l: "Decision point: approved → next stage, rejected → loop back to the Actor with feedback." },
  script:    { x: 1130, y: 370, t: "SCRIPT",      s: "renumber 0001… → script.json", l: "Turns are renumbered (0001…) in speaking order and saved to script.json." },
  tts:       { x: 1130, y: 600, t: "TTS",         s: "every turn → own wav", l: "Each turn is spoken by its host's voice into its own wav file." },
  stitch:    { x: 1130, y: 790, t: "STITCH",      s: "wavs joined → final MP3", l: "All wavs are glued together with short silences → final_podcast.mp3." },
  editor:    { x: 910,  y: 790, t: "EDITOR",      s: "finds turns to change", l: "Looks at your notes + the full script and decides which turns to change." },
  revcritic: { x: 660,  y: 980, t: "REV·CRITIC",  s: "original vs updated vs notes", l: "Compares original vs updated script against your notes." },
  revrouter: { x: 410,  y: 980, t: "ROUTER",      s: "approved → merge · else edit", l: "Approved → merge the edits; rejected → send the Editor back in." },
  merge:     { x: 200,  y: 790, t: "MERGE",       s: "merge · re-speak · re-stitch", l: "Edits merged, only the changed turns re-synthesized, audio re-stitched." },
};

const E = {
  wait_ingest:      "M145 370 H355",
  ingest_q:         "M372 334 C 368 280, 388 220, 405 185",
  q_eval:           "M445 130 H645",
  eval_actor:       "M660 192 V308",
  actor_critic:     "M675 370 H895",
  critic_router:    "M866 411 C 810 460, 745 520, 704 559",
  router_actor:     "M660 538 C 548 538, 548 432, 660 432",
  router_script:    "M715 575 C 880 500, 1000 410, 1076 345",
  script_tts:       "M1130 432 V538",
  tts_stitch:       "M1130 662 V728",
  stitch_editor:    "M1115 790 H925",
  editor_revcritic: "M862 827 C 800 870, 740 915, 709 943",
  revcritic_revrouter: "M645 980 H425",
  revrouter_editor: "M467 957 C 650 860, 820 830, 853 813",
  revrouter_merge:  "M366 940 C 340 905, 280 848, 250 823",
  merge_home:       "M188 758 C 175 690, 150 560, 138 430",
};

const ETYPE = { router_actor: "loop", revrouter_editor: "loop" };

const LABELS = {
  wait_ingest:      ["PDF file", 250, 376],
  ingest_q:         ["questions (optional)", 380, 235],
  actor_critic:     ["draft", 785, 376],
  script_tts:       ["turns", 1130, 485],
  tts_stitch:       ["wavs", 1130, 695],
  stitch_editor:    ["notes / feedback", 1020, 862],
  merge_home:       ["done — back to WAIT", 160, 590],
};

const ZONES = { start: "START", questions: "QUESTIONS", loop: "WRITER LOOP", write: "WRITE", audio: "AUDIO", revise: "REVISE", home: "BACK TO WAIT" };

const svg = document.getElementById("graph");
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const DEF_CAPTION = "One full generation + revision, on loop.";

function el(name, attrs, parent) {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}

function buildGraph() {
  const defs = el("defs", {}, svg);
  const gact = el("linearGradient", { id: "gact", x1: "0", y1: "0", x2: "1", y2: "0" }, defs);
  el("stop", { offset: "0", "stop-color": "#7c5cff" }, gact);
  el("stop", { offset: "1", "stop-color": "#22d3ee" }, gact);
  const gedge = el("linearGradient", { id: "gedge", x1: "0", y1: "0", x2: "1", y2: "0" }, defs);
  el("stop", { offset: "0", "stop-color": "#7c5cff" }, gedge);
  el("stop", { offset: "1", "stop-color": "#22d3ee" }, gedge);

  for (const [id, d] of Object.entries(E)) {
    el("path", { id: "e_" + id, d, class: "edge" + (ETYPE[id] ? " " + ETYPE[id] : "") }, svg);
  }
  for (const [id, [txt, x, y]] of Object.entries(LABELS)) {
    const w = txt.length * 7.5 + 20;
    const g = el("g", { class: "elabel" }, svg);
    el("rect", { class: "elabel-bg", x: x - w / 2, y: y - 14, width: w, height: 28, rx: 14 }, g);
    el("text", { class: "elabel-txt", x, y: y + 5, "text-anchor": "middle" }, g).textContent = txt;
  }
  for (const [id, n] of Object.entries(N)) {
    const g = el("g", { id: "n_" + id, class: "node" + (n.opt ? " optional" : "") + (n.start ? " start" : "") }, svg);
    el("circle", { class: "box", cx: n.x, cy: n.y, r: 62 }, g);
    el("text", { class: "t-title", x: n.x, y: n.y - 6, "text-anchor": "middle" }, g).textContent = n.t;
    el("text", { class: "t-sub", x: n.x, y: n.y + 22, "text-anchor": "middle" }, g).textContent = n.s;
    el("title", {}, g).textContent = n.t + " — " + n.l;
  }
  el("circle", { id: "packet", class: "packet hide", r: 6 }, svg);
  const bg = el("g", { id: "loopbadge", class: "hide" }, svg);
  el("rect", { id: "lbx", class: "lbx", x: 0, y: 0, width: 10, height: 28, rx: 14 }, bg);
  el("text", { id: "lbt", class: "lbt", x: 5, y: 19, "text-anchor": "middle" }, bg).textContent = "";
  const index = $("index");
  for (const [id, n] of Object.entries(N)) {
    const card = document.createElement("div");
    card.className = "card";
    const p = document.createElement("p");
    p.innerHTML = `<strong>${n.t}</strong>${n.opt ? " <em class='muted'>(optional)</em>" : ""} — ${n.l}`;
    card.appendChild(p);
    index.appendChild(card);
  }
  start();
}

function mkBeats() {
  const b = [];
  const P = (from, to, edge, text, zone, dur = 1300, badge = null) => b.push({ from, to, edge, text, zone, dur, type: "pass", badge });
  const R = (from, to, edge, text, zone, badge) => b.push({ from, to, edge, text, zone, dur: 1000, type: "reject", badge });

  P("wait", "ingest", "wait_ingest", "PDF applied — pipeline starts", "start", 1300);
  P("ingest", "questions", "ingest_q", "questions PDF → Markdown", "questions", 1600);
  P("questions", "evaluator", "q_eval", "splitting answerable vs unanswerable", "questions", 1600);
  P("evaluator", "actor", "eval_actor", "answerable questions → writer context", "questions", 1300);
  P("actor", "critic", "actor_critic", "draft n°1 — turns as JSON (Host 1 ⇄ Host 2)", "loop", 1300);
  R("critic", "router", "critic_router", "critic rejected it", "loop", { x: 780, y: 480, kind: "reject", txt: "rejected 1/3" });
  P("router", "actor", "router_actor", "feedback → draft n°2", "loop", 1200, { x: 780, y: 480, kind: "reject", txt: "rejected 1/3" });
  P("actor", "critic", "actor_critic", "critic re-checks draft n°2", "loop", 1300);
  R("critic", "router", "critic_router", "still not approved", "loop", { x: 780, y: 480, kind: "reject", txt: "rejected 2/3" });
  P("router", "actor", "router_actor", "feedback → draft n°3", "loop", 1200, { x: 780, y: 480, kind: "reject", txt: "rejected 2/3" });
  P("actor", "critic", "actor_critic", "critic re-checks draft n°3", "loop", 1300);
  P("critic", "router", "critic_router", "critic approves — router passes it on", "loop", 800, { x: 780, y: 480, kind: "ok", txt: "approved 3/3" });
  P("router", "script", "router_script", "renumber turns → script.json", "write", 1200);
  P("script", "tts", "script_tts", "every turn → its own wav", "audio", 1500);
  P("tts", "stitch", "tts_stitch", "wavs joined in order → final MP3", "audio", 1500);
  P("stitch", "editor", "stitch_editor", "your notes on the episode", "revise", 1300);
  P("editor", "revcritic", "editor_revcritic", "locating which turns to change", "revise", 1200);
  R("revcritic", "revrouter", "revcritic_revrouter", "rejected — needs a second pass", "revise", { x: 660, y: 892, kind: "reject", txt: "rejected 1/2" });
  P("revrouter", "editor", "revrouter_editor", "notes → edits v2", "revise", 1200, { x: 660, y: 892, kind: "reject", txt: "rejected 1/2" });
  P("editor", "revcritic", "editor_revcritic", "re-checking revised turns", "revise", 1200);
  P("revcritic", "revrouter", "revcritic_revrouter", "critic approves — merging", "revise", 1100, { x: 660, y: 892, kind: "ok", txt: "approved 2/2" });
  P("revrouter", "merge", "revrouter_merge", "merge · re-speak changed turns · re-stitch", "revise", 1300);
  P("merge", "wait", "merge_home", "revised episode ready — back to WAIT", "home", 2200);
  return b;
}

let beats = [];
let starts = [];
let totalMs = 1;
let elapsed = 0;
let speed = 1;
let playing = true;
let finished = false;
let finishedAt = 0;
let lastT = null;

const playBtn = $("play"), prevBtn = $("prev"), nextBtn = $("next"), restartBtn = $("restart");
const speedSel = $("speed"), scrub = $("scrub"), caption = $("caption");

function restart() {
  beats = mkBeats();
  starts = [];
  let acc = 0;
  for (const b of beats) { starts.push(acc); acc += b.dur; }
  totalMs = acc;
  elapsed = 0;
  finished = false;
  playing = true;
  scrub.max = Math.round(totalMs);
  scrub.value = 0;
  caption.innerHTML = `<span class="zone">READY</span> ${DEF_CAPTION}`;
}

function resolve(e) {
  if (e < starts[0]) return { idx: -1, prog: 0 };
  for (let i = 0; i < beats.length; i++) {
    if (e < starts[i] + beats[i].dur) return { idx: i, prog: Math.min(1, (e - starts[i]) / beats[i].dur) };
  }
  return { idx: beats.length - 1, prog: 1 };
}

const ease = (p) => p * p * (3 - 2 * p);

function draw() {
  const { idx, prog } = resolve(elapsed);
  const done = new Set();
  for (let i = 0; i < beats.length; i++) {
    const b = beats[i];
    if (b.type !== "reject" && (i < idx || (i === idx && prog >= 1))) done.add(b.to);
  }
  let active = null, rejecting = null;
  if (idx >= 0 && prog < 1) {
    const b = beats[idx];
    if (b.type === "reject") rejecting = b.to; else active = b.to;
  }
  for (const id of Object.keys(N)) {
    const g = $("n_" + id);
    g.classList.toggle("done", done.has(id));
    g.classList.toggle("active", id === active);
    g.classList.toggle("rejected", id === rejecting);
  }

  svg.querySelectorAll(".edge").forEach((p) => p.classList.remove("travel"));
  const dot = $("packet");
  if (idx >= 0 && prog < 1) {
    const b = beats[idx];
    const p = $("e_" + b.edge);
    if (p) {
      p.classList.add("travel");
      const pt = p.getPointAtLength(p.getTotalLength() * ease(prog));
      dot.setAttribute("cx", pt.x);
      dot.setAttribute("cy", pt.y);
      dot.classList.remove("hide");
    }
  } else {
    dot.classList.add("hide");
  }

  const bg = $("loopbadge"), bx = $("lbx"), bt = $("lbt");
  const bd = idx >= 0 && prog < 1 ? beats[idx].badge : null;
  if (bd) {
    bt.textContent = bd.txt;
    const w = bd.txt.length * 8 + 26;
    bx.setAttribute("width", w);
    bt.setAttribute("x", w / 2);
    bg.setAttribute("transform", `translate(${bd.x - w / 2}, ${bd.y - 14})`);
    bg.classList.toggle("ok", bd.kind === "ok");
    bg.classList.toggle("reject", bd.kind === "reject");
    bg.classList.remove("hide");
  } else {
    bg.classList.add("hide");
  }

  if (idx >= 0 && prog < 1) {
    const b = beats[idx];
    caption.innerHTML = `<span class="zone">${ZONES[b.zone]}</span> ${b.text}`;
  } else if (finished) {
    caption.innerHTML = `<span class="zone">DONE</span> Full pipeline complete — replaying in a moment…`;
  }
  scrub.value = Math.round(elapsed);
  playBtn.textContent = playing ? "Pause" : "Play";
}

function frame(now) {
  if (lastT == null) lastT = now;
  const dt = (now - lastT) / 1000;
  lastT = now;
  if (playing && !finished) {
    elapsed += dt * 1000 * speed;
    if (elapsed >= totalMs) {
      elapsed = totalMs;
      finished = true;
      finishedAt = now;
    }
  }
  if (finished && now - finishedAt > 3500) restart();
  draw();
  requestAnimationFrame(frame);
}

function start() {
  restart();
  playBtn.addEventListener("click", () => { playing = !playing; });
  prevBtn.addEventListener("click", () => {
    const { idx } = resolve(elapsed);
    elapsed = Math.max(0, starts[Math.max(0, idx - 1)]);
  });
  nextBtn.addEventListener("click", () => {
    if (finished) { restart(); return; }
    const { idx } = resolve(elapsed);
    elapsed = idx < beats.length - 1 ? starts[idx + 1] : totalMs;
  });
  restartBtn.addEventListener("click", () => restart());
  speedSel.addEventListener("change", () => { speed = parseFloat(speedSel.value); });
  scrub.addEventListener("input", () => { elapsed = Math.min(totalMs, parseFloat(scrub.value)); });
  requestAnimationFrame(frame);

  if (new URLSearchParams(location.search).has("selftest")) selftest();
}

function selftest() {
  const fail = (msg) => { throw new Error("selftest: " + msg); };
  for (const [id2, n] of Object.entries(N)) {
    if (typeof n.x !== "number" || typeof n.y !== "number") fail("bad node " + id2);
  }
  const bb = mkBeats();
  let acc = 0;
  for (let i = 0; i < bb.length; i++) {
    const b = bb[i];
    if (!N[b.from] || !N[b.to]) fail("beat node unknown: " + b.text);
    if (!E[b.edge]) fail("beat edge missing: " + b.edge);
    if (!ZONES[b.zone]) fail("beat zone unknown: " + b.text);
    if (i && acc === starts[i]) fail("zero-duration beat");
    if (b.badge && (!b.badge.x || !b.badge.y || b.badge.kind !== "ok" && b.badge.kind !== "reject" || !b.badge.txt)) fail("bad badge: " + b.text);
    acc += b.dur;
  }
  const uniq = [...new Set(bb.filter((b) => b.badge).map((b) => b.badge.txt))];
  const want = ["rejected 1/3", "rejected 2/3", "approved 3/3", "rejected 1/2", "approved 2/2"];
  if (JSON.stringify(uniq) !== JSON.stringify(want)) fail("badge sequence wrong: " + JSON.stringify(uniq));
  console.log(`selftest ok — ${bb.length} beats, badges ${uniq.join(", ")}, ~${Math.round(acc / 1000)}s @1×`);
}

export { buildGraph };
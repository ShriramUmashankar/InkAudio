/* Shared file-drop, microphone recording, and custom voice-selector controls. */
/** Keep a file-drop hint and drag styling aligned with the native input. */
export function wireDrop(input, hint, prompt) {
  // Display the selected filename chip or restore the empty-input prompt.
  const show = () => {
    if (input.files[0]) {
      hint.replaceChildren();
      const chip = document.createElement("span");
      chip.className = "drop-chip";
      chip.textContent = input.files[0].name;
      hint.appendChild(chip);
    } else {
      hint.textContent = prompt;
    }
  };
  input.addEventListener("change", show);
  // Maintain drag highlighting and refresh the filename after a drop.
  input.addEventListener("dragenter", () => input.classList.add("drag"));
  input.addEventListener("dragleave", () => input.classList.remove("drag"));
  input.addEventListener("drop", () => { input.classList.remove("drag"); show(); });
  show();
}

/** Acquire microphone audio and expose controls for stopping and collecting a recording. */
export async function startRecording(onState) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream);
  const chunks = [];
  // Collect recorder chunks and resolve completion only after its stop event.
  rec.ondataavailable = (e) => chunks.push(e.data);
  onState?.("recording");
  const done = new Promise((r) => { rec.onstop = r; });
  rec.start();
  return {
    // Request recording completion; file() waits until the final chunks are available.
    stop: () => rec.stop(),
    // Wait for recording completion, release microphone tracks, and return an audio File.
    file: async () => {
      await done;
      stream.getTracks().forEach((t) => t.stop());
      const type = rec.mimeType || "audio/webm";
      return new File([new Blob(chunks, { type })], "recording.webm", { type });
    },
  };
}

const CHEVRON = '<svg viewBox="0 0 12 8" width="12" height="8" aria-hidden="true"><path d="M1 1l5 5 5-5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';

/** Build a styled option menu backed by a hidden input for form-value collection. */
export function customSelect({ id, options, value, placeholder = "Select…" }) {
  let sel = options.find((o) => String(o.value) === String(value));
  let all = options;
  if (!sel && value !== "" && value != null) {
    sel = { value, label: value };
    all = [sel, ...options];
  }

  const input = document.createElement("input");
  input.type = "hidden";
  input.id = id;
  input.value = sel ? sel.value : "";

  const wrap = document.createElement("div");
  wrap.className = "cs";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "cs-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  const valSpan = document.createElement("span");
  valSpan.className = "cs-value" + (sel && sel.value !== "" ? "" : " placeholder");
  valSpan.textContent = sel && sel.value !== "" ? sel.label : placeholder;
  const chev = document.createElement("span");
  chev.className = "cs-chevron";
  chev.innerHTML = CHEVRON;
  trigger.append(valSpan, chev);

  const menu = document.createElement("ul");
  menu.className = "cs-menu";
  menu.setAttribute("role", "listbox");

  const items = [];
  // Apply a chosen value to the hidden input, label, and selection styling.
  const render = (o) => {
    input.value = o.value;
    valSpan.textContent = o.label;
    valSpan.classList.remove("placeholder");
    items.forEach((i) => i.classList.toggle("selected", String(i.dataset.value) === String(o.value)));
  };

  // Create options and prevent focus changes while applying a mousedown selection.
  all.forEach((o) => {
    const li = document.createElement("li");
    li.className = "cs-opt" + (sel && String(o.value) === String(sel.value) ? " selected" : "");
    li.dataset.value = o.value;
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", li.classList.contains("selected") ? "true" : "false");
    li.textContent = o.label;
    li.addEventListener("mousedown", (e) => { e.preventDefault(); render(o); close(); });
    menu.appendChild(li);
    items.push(li);
  });

  // Show the menu and expose its expanded state to assistive technology.
  const open = () => {
    wrap.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
  };
  // Hide the menu and reset its expanded state.
  const close = () => {
    wrap.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
  };
  // Toggle the menu from its trigger and dismiss it on Escape or outside clicks.
  trigger.addEventListener("click", () => (wrap.classList.contains("open") ? close() : open()));
  wrap.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.addEventListener("mousedown", (e) => { if (!wrap.contains(e.target)) close(); });

  wrap.append(trigger, menu, input);
  return wrap;
}
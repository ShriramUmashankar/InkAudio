import { getCapabilities } from "./api.js";

export async function applyCapabilities() {
  const response = await getCapabilities();
  if (!response.ok) throw new Error("Could not load available features.");
  const { lite, tts_modes, stt_enabled } = response.body;
  document.querySelectorAll('input[name="mode"]').forEach(input => {
    input.disabled = !tts_modes.includes(input.value);
    if (input.disabled && input.checked) {
      const bodhan = document.querySelector('input[name="mode"][value="bodhan"]');
      bodhan.checked = true;
      bodhan.dispatchEvent(new Event("change"));
    }
  });
  document.querySelectorAll("[data-stt-control]").forEach(control => {
    if (!stt_enabled) {
      control.dataset.liteDisabled = "true";
      control.disabled = true;
    }
  });
  document.querySelectorAll("[data-lite-notice]").forEach(notice => {
    notice.hidden = !lite;
  });
}

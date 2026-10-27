/* Apply server feature availability to generation and speech controls across pages. */
import { getCapabilities } from "./api.js";

/** Disable unsupported controls while preserving existing in-flight disabled states. */
export async function applyCapabilities() {
  const response = await getCapabilities();
  if (!response.ok) throw new Error("Could not load available features.");
  const { lite, tts_modes, stt_enabled } = response.body;
  // Fall back to Bodhan if the selected local TTS engine is unavailable.
  document.querySelectorAll('input[name="mode"]').forEach(input => {
    input.disabled = !tts_modes.includes(input.value);
    if (input.disabled && input.checked) {
      const bodhan = document.querySelector('input[name="mode"][value="bodhan"]');
      bodhan.checked = true;
      bodhan.dispatchEvent(new Event("change"));
    }
  });
  // Mark unavailable speech controls so request completion cannot re-enable them.
  document.querySelectorAll("[data-stt-control]").forEach(control => {
    if (!stt_enabled) {
      control.dataset.liteDisabled = "true";
      control.disabled = true;
    }
  });
  // Show deployment limitations only when the server reports Lite mode.
  document.querySelectorAll("[data-lite-notice]").forEach(notice => {
    notice.hidden = !lite;
  });
}

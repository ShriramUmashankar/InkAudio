/* Render shared page navigation and initialize server-dependent feature controls. */
import { applyCapabilities } from "./capabilities.js";

/** Build shared navigation, mark the active page, and apply server capabilities. */
export function renderNav(active) {
  const nav = document.getElementById("nav");
  if (!nav) return;
  const pages = [
    ["how.html", "How it works"],
    ["index.html", "Generate"],
    ["progress.html", "Progress"],
    ["result.html", "Result"],
    ["examples.html", "Examples"],
    ["transcribe.html", "Transcribe"],
  ];
  // Render each route with its active-state class alongside the shared brand.
  nav.innerHTML = `
  <div class="brand">
    <svg class="brand-mark" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
      <rect x="3" y="9" width="3" height="6" rx="1.4" fill="#7c5cff"/>
      <rect x="8" y="6" width="3" height="12" rx="1.4" fill="#8b6bff"/>
      <rect x="13" y="4" width="3" height="16" rx="1.4" fill="#3ddc97"/>
      <rect x="18" y="7" width="3" height="10" rx="1.4" fill="#22d3ee"/>
    </svg>
    <span class="brand-text">Podcast <em>Studio</em></span>
  </div>
  <nav class="links">${pages.map(([href, label]) =>
    `<a href="${href}" class="${href === active ? "active" : ""}">${label}</a>`
  ).join("")}</nav>`;
  // Keep navigation usable if feature discovery fails, while logging its cause.
  applyCapabilities().catch(error => console.warn(error.message));
}

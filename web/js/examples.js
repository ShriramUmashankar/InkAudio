import { renderNav } from './nav.js';

renderNav('examples.html');
const $ = (id) => document.getElementById(id);
const audio = $('example-audio');
const play = $('play-example');
const seek = $('example-seek');
const studio = document.querySelector('.studio');
const hosts = [$('host-one'), $('host-two')];
const canvas = $('spectrum');
const ctx = canvas.getContext('2d');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const episodes = {
  magnetism: {
    title: 'Magnetism-Tamil', folder: 'Magnetism-Tamil', language: 'ta',
    tag: 'FEATURED EPISODE · SCIENCE · CLASS 6 · தமிழ்', hosts: ['Arun', 'Anitha'],
    description: 'Invisible forces. A conversation that pulls you in.',
    introduction: 'A compass, two curious minds, and the invisible world of magnets.',
  },
  changes: {
    title: 'changes-around-us - Hindi', folder: 'Chemistry-Hindi', language: 'hi',
    tag: 'FEATURED EPISODE · SCIENCE · CLASS 7 · हिन्दी', hosts: ['Amit', 'Raagini'],
    description: 'From melting ice to blooming flowers. Discover the changes around us.',
    introduction: 'Two curious minds explore physical and chemical changes in everyday life.',
  },
};
let episode = episodes.magnetism;
let loadVersion = 0;
let turns = [];
let current = null;
let audioContext;
let analyser;
let bins;
let frame = 0;
let ready = false;

// Inline SVG keeps the host illustrations crisp at every screen size.
function portrait(female, color) {
  return `<svg viewBox="0 0 220 230" aria-hidden="true">
    <circle cx="110" cy="109" r="83" fill="${color}" opacity=".055"/>
    <circle cx="110" cy="109" r="82" fill="none" stroke="${color}" stroke-opacity=".18" stroke-dasharray="3 7"/>
    <path d="M43 215c2-42 25-60 67-60s65 18 67 60" fill="${female ? '#274752' : '#3e345d'}"/>
    <path d="M91 149v23q19 18 38 0v-23" fill="#bd896c"/>
    ${female ? '<path d="M64 117V87q0-57 46-57t46 57v80l-29-12-35 6-30 6z" fill="#252032"/>' : ''}
    <ellipse cx="110" cy="105" rx="39" ry="51" fill="#dca885"/>
    <ellipse cx="70" cy="111" rx="7" ry="12" fill="#dca885"/><ellipse cx="150" cy="111" rx="7" ry="12" fill="#dca885"/>
    ${female ? '<path d="M71 97q-9-63 39-63 47 0 42 64-19-9-33-38-17 26-48 37" fill="#252032"/>' : '<path d="M70 86q-4-49 40-49 46 0 42 50l-14-20q-30 11-50-1z" fill="#282638"/>'}
    <path d="M86 101q7-4 14 0m20 0q7-4 14 0" fill="none" stroke="#654c44" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="94" cy="110" rx="2.5" ry="3" fill="#302936"/><ellipse cx="127" cy="110" rx="2.5" ry="3" fill="#302936"/>
    <path d="M109 112l-3 12h7" fill="none" stroke="#b67d60" stroke-width="2" stroke-linecap="round"/>
    <path d="M100 135q11 8 22-1" fill="none" stroke="#80564b" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M62 107V89q0-53 48-53t48 53v18" fill="none" stroke="#101522" stroke-width="11"/>
    <path d="M63 88q0-51 47-51t47 51" fill="none" stroke="${color}" stroke-width="3" opacity=".7"/>
    <rect x="56" y="91" width="16" height="35" rx="7" fill="#161c2c" stroke="${color}" stroke-opacity=".55" stroke-width="2"/>
    <rect x="149" y="91" width="16" height="35" rx="7" fill="#161c2c" stroke="${color}" stroke-opacity=".55" stroke-width="2"/>
    <path d="M157 122q0 22-26 22" fill="none" stroke="#748199" stroke-width="3"/><rect x="123" y="140" width="12" height="6" rx="3" fill="${color}"/>
    <path d="M86 174l24 18 24-18" fill="none" stroke="${color}" stroke-opacity=".3" stroke-width="2"/>
    <path d="M172 217v-25m-12 25h25" stroke="#68758f" stroke-width="3" stroke-linecap="round"/>
    <rect x="162" y="163" width="20" height="34" rx="10" fill="#1b2233" stroke="#68758f" stroke-width="2"/>
    <path d="M167 172h10m-10 6h10m-10 6h10" stroke="${color}" stroke-opacity=".5" stroke-width="2"/>
  </svg>`;
}
hosts.forEach((host, i) => { host.querySelector('.portrait').innerHTML = portrait(i === 1, i ? '#5dd9df' : '#a68aff'); });

function fmt(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
function showError(message) {
  $('example-error').textContent = message;
  $('example-error').hidden = false;
}
function drawSpectrum(active = false) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (active && analyser) analyser.getByteFrequencyData(bins);
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
  gradient.addColorStop(0, '#a68aff'); gradient.addColorStop(1, '#5dd9df');
  ctx.fillStyle = gradient;
  for (let i = 0; i < 48; i++) {
    // Mirror low frequencies at the center so speech fills both sides equally.
    const band = i < 24 ? 23 - i : i - 24;
    const value = active && analyser ? bins[2 + band * 3] / 255 : 0;
    const height = 4 + value * 135;
    ctx.globalAlpha = active ? .45 + value * .55 : .25;
    ctx.fillRect(i * 10 + 2.5, (160 - height) / 2, 5, height);
  }
  ctx.globalAlpha = 1;
}
function setCaption(turn, animate) {
  if (animate && !reducedMotion.matches) {
    document.querySelector('.caption-ghost')?.remove();
    const ghost = $('caption').cloneNode(true);
    ghost.removeAttribute('id');
    ghost.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'));
    ghost.className = 'caption-ghost';
    ghost.setAttribute('aria-hidden', 'true');
    $('caption-area').appendChild(ghost);
    ghost.addEventListener('animationend', () => ghost.remove(), { once: true });
    $('caption').classList.remove('caption-enter');
    void $('caption').offsetWidth;
    $('caption').classList.add('caption-enter');
  } else {
    document.querySelector('.caption-ghost')?.remove();
    $('caption').classList.remove('caption-enter');
  }
  $('caption-speaker').textContent = `${episode.hosts[turn.speaker === 'Host 1' ? 0 : 1].toUpperCase()} / ${turn.speaker.toUpperCase()} · ${String(turn.turn_id).padStart(2, '0')} OF ${turns.length}`;
  $('caption-text').textContent = turn.text;
  $('caption-text').lang = episode.language;
  $('caption-area').dataset.speaker = turn.speaker;
}
function sync(animate = true) {
  const ms = audio.currentTime * 1000;
  const speaking = turns.find((turn) => ms >= turn.start_ms && ms < turn.end_ms);
  const caption = speaking || turns.findLast((turn) => ms >= turn.start_ms);
  if (caption && caption !== current) {
    setCaption(caption, animate && current !== null);
    current = caption;
  }
  hosts.forEach((host, i) => host.classList.toggle('speaking', !audio.paused && !audio.ended && speaking?.speaker === `Host ${i + 1}`));
  seek.value = audio.currentTime;
  seek.setAttribute('aria-valuetext', `${fmt(audio.currentTime)} of ${fmt(audio.duration)}`);
  $('current-time').textContent = fmt(audio.currentTime);
}
function tick() {
  sync();
  drawSpectrum(!reducedMotion.matches);
  frame = requestAnimationFrame(tick);
}
function syncPlayback() {
  cancelAnimationFrame(frame);
  const playing = !audio.paused && !audio.ended;
  studio.classList.toggle('is-playing', playing);
  play.setAttribute('aria-label', `${playing ? 'Pause' : 'Play'} ${episode.title}`);
  play.innerHTML = playing ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zm8 0h4v14h-4z" fill="currentColor"/></svg>' : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>';
  $('studio-status').textContent = audio.ended ? 'Episode complete' : playing ? 'Now playing' : 'Ready to listen';
  $('frequency-note').textContent = playing ? 'A conversation in motion.' : 'Two voices. One discovery.';
  sync(false);
  if (playing) tick(); else drawSpectrum();
}
async function startPlayback() {
  if (!ready) return;
  const version = loadVersion;
  try {
    if (!audioContext) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioContext = new AudioContext();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = .8;
        bins = new Uint8Array(analyser.frequencyBinCount);
        audioContext.createMediaElementSource(audio).connect(analyser);
        analyser.connect(audioContext.destination);
      }
    }
    if (audioContext?.state === 'suspended') await audioContext.resume();
    if (version !== loadVersion) return;
    await audio.play();
    if (version !== loadVersion) return;
    $('example-error').hidden = true;
  } catch {
    if (version !== loadVersion) return;
    showError('Playback could not start. Please press Play to try again.');
    syncPlayback();
  }
}
play.addEventListener('click', () => audio.paused ? startPlayback() : audio.pause());
document.querySelectorAll('[data-example]').forEach((card) => {
  card.addEventListener('click', async () => {
    const key = card.dataset.example;
    if (episode !== episodes[key] || !ready) {
      if (!await loadEpisode(key)) return;
    }
    studio.scrollIntoView({ behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'center' });
    startPlayback();
  });
});
seek.addEventListener('input', () => { audio.currentTime = Number(seek.value); sync(false); });
audio.addEventListener('seeked', () => sync(false));
audio.addEventListener('timeupdate', () => sync(!audio.seeking));
['play', 'pause', 'ended'].forEach((event) => audio.addEventListener(event, syncPlayback));
audio.addEventListener('waiting', () => { $('studio-status').textContent = 'Buffering'; });
audio.addEventListener('playing', syncPlayback);
audio.addEventListener('error', () => {
  audio.pause();
  showError('The recording could not be loaded. Reload the page to try again.');
  $('studio-status').textContent = 'Audio unavailable';
});
function metadata() {
  if (!Number.isFinite(audio.duration)) return;
  seek.max = audio.duration;
  $('duration').textContent = fmt(Math.ceil(audio.duration));
}
audio.addEventListener('loadedmetadata', metadata);
metadata();
drawSpectrum();
async function loadEpisode(key) {
  const version = ++loadVersion;
  ready = false;
  audio.pause();
  cancelAnimationFrame(frame);
  episode = episodes[key];
  current = null;
  turns = [];
  play.disabled = true;
  seek.disabled = true;
  seek.value = 0;
  seek.max = 0;
  $('current-time').textContent = '0:00';
  $('duration').textContent = '—';
  $('example-error').hidden = true;
  document.querySelector('.caption-ghost')?.remove();
  $('caption').classList.remove('caption-enter');
  $('caption-speaker').textContent = 'THE CONVERSATION STARTS HERE';
  $('caption-text').textContent = episode.introduction;
  $('caption-text').lang = 'en';
  delete $('caption-area').dataset.speaker;
  $('episode-title').textContent = episode.title;
  $('episode-tag').textContent = episode.tag;
  $('episode-description').textContent = episode.description;
  hosts.forEach((host, i) => { host.querySelector('.host-label strong').textContent = episode.hosts[i]; });
  studio.setAttribute('aria-label', `${episode.title} podcast player`);
  play.setAttribute('aria-label', `Play ${episode.title}`);
  seek.setAttribute('aria-label', `Seek through ${episode.title}`);
  document.querySelectorAll('[data-example]').forEach((card) => {
    const selected = card.dataset.example === key;
    card.classList.toggle('selected', selected);
    card.setAttribute('aria-pressed', String(selected));
  });
  syncPlayback();
  $('studio-status').textContent = 'Loading episode';
  // Clear the previous source so its metadata cannot update the new episode.
  audio.removeAttribute('src');
  audio.load();
  const base = `/podcast_examples/${episode.folder}/`;
  try {
    const responses = await Promise.all(['script.json', 'timeline.json'].map((file) => fetch(base + file)));
    if (responses.some((response) => !response.ok)) throw new Error('Missing episode assets');
    const [script, timeline] = await Promise.all(responses.map((response) => response.json()));
    if (version !== loadVersion) return false;
    if (!Array.isArray(script) || !Array.isArray(timeline) || !timeline.length) throw new Error('Invalid episode assets');
    turns = timeline.map((time) => {
      const dialogue = script.find((turn) => Number(turn.turn_id) === Number(time.turn_id));
      if (!dialogue || dialogue.speaker !== time.speaker || !dialogue.text?.trim() || !['Host 1', 'Host 2'].includes(time.speaker) || !(time.end_ms > time.start_ms)) throw new Error('Invalid episode turn');
      return { ...dialogue, ...time };
    }).sort((a, b) => a.start_ms - b.start_ms);
    audio.src = base + 'final_podcast.mp3';
    seek.max = turns.at(-1).end_ms / 1000;
    $('duration').textContent = fmt(Math.ceil(Number(seek.max)));
    ready = true;
    play.disabled = false;
    seek.disabled = false;
    syncPlayback();
    return true;
  } catch {
    if (version !== loadVersion) return false;
    showError('The episode captions could not be loaded. Select the episode to try again.');
    $('studio-status').textContent = 'Episode unavailable';
    return false;
  }
}
loadEpisode('magnetism');

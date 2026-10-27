/* Node regression checks for browser capabilities, playback, captions, and progress restoration. */
// Run with: node web/js/regressions.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const web = path.resolve(__dirname, '..');

// Exercise feature gating in both Lite and full deployments using isolated DOM stubs.
for (const lite of [true, false]) {
  test(`capabilities ${lite ? 'disable only unsupported Lite controls' : 'preserve normal controls'}`, async () => {
    const modes = ['bodhan', 'custom_voice', 'voice_design'].map(value => ({ value, disabled: false }));
    // A request may already be in flight when capabilities finish loading.
    const speech = [{ disabled: true, dataset: {} }, { disabled: false, dataset: {} }];
    const notices = [{ hidden: true }];
    const context = {
      // Return deterministic feature availability without contacting a server.
      getCapabilities: async () => ({ ok: true, body: {
        lite, tts_modes: lite ? ['bodhan'] : modes.map(m => m.value), stt_enabled: !lite,
      } }),
      // Route capability selectors to the test’s mode, speech, and notice controls.
      document: { querySelectorAll(selector) {
        if (selector === 'input[name="mode"]') return modes;
        if (selector === '[data-stt-control]') return speech;
        if (selector === '[data-lite-notice]') return notices;
        return [];
      } },
    };
    const source = fs.readFileSync(path.join(__dirname, 'capabilities.js'), 'utf8')
      .replace(/^import .*;\s*$/gm, '').replace('export async function', 'async function');
    vm.runInNewContext(source + '\nglobalThis.ready = applyCapabilities();', context);
    await context.ready;
    assert.equal(modes[0].disabled, false);
    assert.equal(modes[1].disabled, lite);
    assert.equal(modes[2].disabled, lite);
    assert.equal(speech[0].disabled, true);
    assert.equal(speech[1].disabled, lite);
    assert.equal(notices[0].hidden, !lite);
  });
}

// Reproduce a transcription response racing with Lite capability initialization.
test('a transcription finishing during Lite initialization cannot re-enable its button', async () => {
  const html = fs.readFileSync(path.join(web, 'transcribe.html'), 'utf8');
  const source = html.slice(html.indexOf('async function runTranscribe('), html.indexOf('goBtn.addEventListener('));
  const context = {
    goBtn: { disabled: true, dataset: { liteDisabled: 'true' } },
    errorEl: {}, statusEl: {},
    // Simulate a server that rejects transcription in Lite mode.
    transcribe: async () => ({ ok: false, status: 403, body: { detail: 'Unavailable in Lite' } }),
  };
  vm.runInNewContext(source + '\nglobalThis.ready = runTranscribe({});', context);
  await context.ready;
  assert.equal(context.goBtn.disabled, true);
});

// Verify low-frequency energy produces equal mirrored bars on both canvas halves.
test('audio frequency energy is mirrored around the canvas center', () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const draw = source.slice(source.indexOf('function drawSpectrum('), source.indexOf('function setCaption('));
  const bars = [];
  const bins = Uint8Array.from({ length: 256 }, (_, i) => i < 40 ? 230 : 0);
  const context = { canvas: { width: 480, height: 160 }, bins,
    // Keep the supplied frequency bins unchanged during spectrum drawing.
    analyser: { getByteFrequencyData() { /* Retain the fixture’s precomputed frequency bins. */ } },
    // Stub canvas painting and capture bar geometry for balance and reflection assertions.
    ctx: { clearRect() { /* Canvas clearing does not affect the captured bar geometry. */ }, createLinearGradient() { /* Supply the gradient surface consumed by drawSpectrum. */ return { addColorStop() { /* Color stops do not affect bar geometry. */ } }; }, fillRect(x, y, w, h) { /* Capture each frequency bar for symmetry assertions. */ bars.push({ x, y, w, h }); } } };
  vm.runInNewContext(draw + '\ndrawSpectrum(true);', context);
  const left = bars.filter(b => b.x < 240).reduce((sum, b) => sum + b.h, 0);
  const right = bars.filter(b => b.x >= 240).reduce((sum, b) => sum + b.h, 0);
  assert.ok(Math.abs(left - right) < .01, `unbalanced energy: ${left} vs ${right}`);
  for (const bar of bars) assert.ok(bars.some(other => Math.abs(other.x - (480 - bar.x - bar.w)) < .01 && other.h === bar.h));
});

// Execute the real inline progress module against a supplied server snapshot and DOM stubs.
async function progressPage(status) {
  const elements = new Map();
  // Create and cache just the DOM surface exercised by the progress page.
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: { width: '0%' }, hidden: false, disabled: false, textContent: '', classList: { toggle() { /* Ignore stage styling while testing progress state. */ } }, addEventListener() { /* User interactions are outside snapshot restoration tests. */ }, querySelectorAll() { /* Stage decoration is not needed for percentage assertions. */ return []; }, querySelector() { /* Return the optional translation stage visibility target. */ return element('translation'); } });
    return elements.get(id);
  };
  let events;
  const context = { document: { getElementById: element }, window: { location: { href: '' } },
    // Supply stale browser progress to ensure restoration uses the server snapshot.
    localStorage: { /* Return a stale previous-run snapshot. */ getItem: () => JSON.stringify({ progress: 85, stage: 'stitch' }), setItem() { /* Avoid persisting test browser state. */ }, removeItem() { /* Storage cleanup has no external effect in this fixture. */ } },
    // Stub navigation and return deterministic job and termination responses.
    renderNav() { /* Navigation is independent of progress restoration. */ }, /* Return the snapshot selected by the calling test. */ getJobStatus: async () => ({ ok: true, body: status }), /* Accept cancellation without a worker. */ terminateJob: async () => ({ ok: true }),
    // Capture stream handlers for tests while disabling connection and timer side effects.
    streamEvents(handlers) { /* Expose the page’s subscriptions for direct event injection. */ events = handlers; return { close() { /* No live connection is opened by the fixture. */ } }; }, /* Supply a timer handle without scheduling background work. */ setInterval: () => 1, clearInterval() { /* No fixture timer needs cancellation. */ } };
  const html = fs.readFileSync(path.join(web, 'progress.html'), 'utf8');
  const script = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/^import .*;\s*$/gm, '');
  vm.runInNewContext(script, context);
  await new Promise(resolve => setImmediate(resolve));
  return { elements, context, events };
}

// Verify a completed snapshot opens Result without waiting for live events.
test('completed progress page navigates directly to the result', async () => {
  const { context } = await progressPage({ status: 'completed' });
  assert.equal(context.window.location.href, 'result.html');
});

// Verify a fresh run starts at server progress despite stale local storage.
test('a new generation uses server progress instead of stale browser storage', async () => {
  const { elements, events } = await progressPage({ status: 'running', stage: 'ingest', progress: 0 });
  events.stage_start({ stage: 'ingest', progress: 0 });
  assert.equal(elements.get('pct').textContent, '0%');
});

// Verify refresh restores the in-progress server percentage.
test('refreshed running generation restores current server progress', async () => {
  const { elements } = await progressPage({ status: 'running', stage: 'tts', progress: 62 });
  assert.equal(elements.get('pct').textContent, '62%');
});

// Verify caption speaker labels and language follow the selected Hindi episode.
test('Hindi example captions use its selected host names and language', () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const caption = source.slice(source.indexOf('function setCaption('), source.indexOf('function sync('));
  const elements = new Map();
  // Create minimal caption elements without a browser DOM.
  const $ = id => {
    if (!elements.has(id)) elements.set(id, { textContent: '', lang: '', dataset: {}, classList: { remove() { /* Caption animation is disabled for this test. */ } } });
    return elements.get(id);
  };
  const context = { $, episode: { hosts: ['Amit', 'Raagini'], language: 'hi' }, turns: Array(32),
    // Disable caption animation and provide no outgoing ghost element.
    reducedMotion: { matches: true }, document: { querySelector() { /* Report that no outgoing caption ghost exists. */ return null; } } };
  vm.runInNewContext(caption + '\nsetCaption({speaker:"Host 2",turn_id:2,text:"हमेशा।"},false);', context);
  assert.match($('caption-speaker').textContent, /^RAAGINI \/ HOST 2/);
  assert.equal($('caption-text').lang, 'hi');
});

// Verify a rejected play promise from a superseded episode cannot display a stale error.
test('aborted playback from a previous episode does not show a stale error', async () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const playback = source.slice(source.indexOf('async function startPlayback('), source.indexOf("play.addEventListener('click'"));
  let rejectPlayback;
  const errors = [];
  const context = { ready: true, loadVersion: 1, audioContext: { state: 'running' },
    // Keep playback pending until the test replaces the selected episode and rejects it.
    audio: { /* Expose a controllable pending media play request. */ play: () => new Promise((resolve, reject) => { rejectPlayback = reject; }) },
    // Stub error visibility and capture displayed errors without updating playback UI.
    /* Supply the error element consulted after playback. */ $: () => ({ hidden: false }), /* Record stale playback errors for the final assertion. */ showError: message => errors.push(message), syncPlayback() { /* Transport rendering is unrelated to stale error suppression. */ } };
  vm.runInNewContext(playback + '\nglobalThis.pending = startPlayback();', context);
  context.loadVersion = 2;
  rejectPlayback(new Error('Playback aborted by new episode'));
  await context.pending;
  assert.deepEqual(errors, []);
});

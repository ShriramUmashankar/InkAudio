// Run with: node web/js/regressions.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const web = path.resolve(__dirname, '..');

test('audio frequency energy is mirrored around the canvas center', () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const draw = source.slice(source.indexOf('function drawSpectrum('), source.indexOf('function setCaption('));
  const bars = [];
  const bins = Uint8Array.from({ length: 256 }, (_, i) => i < 40 ? 230 : 0);
  const context = { canvas: { width: 480, height: 160 }, bins,
    analyser: { getByteFrequencyData() {} },
    ctx: { clearRect() {}, createLinearGradient() { return { addColorStop() {} }; }, fillRect(x, y, w, h) { bars.push({ x, y, w, h }); } } };
  vm.runInNewContext(draw + '\ndrawSpectrum(true);', context);
  const left = bars.filter(b => b.x < 240).reduce((sum, b) => sum + b.h, 0);
  const right = bars.filter(b => b.x >= 240).reduce((sum, b) => sum + b.h, 0);
  assert.ok(Math.abs(left - right) < .01, `unbalanced energy: ${left} vs ${right}`);
  for (const bar of bars) assert.ok(bars.some(other => Math.abs(other.x - (480 - bar.x - bar.w)) < .01 && other.h === bar.h));
});

async function progressPage(status) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: { width: '0%' }, hidden: false, disabled: false, textContent: '', classList: { toggle() {} }, addEventListener() {}, querySelectorAll() { return []; }, querySelector() { return element('translation'); } });
    return elements.get(id);
  };
  let events;
  const context = { document: { getElementById: element }, window: { location: { href: '' } },
    localStorage: { getItem: () => JSON.stringify({ progress: 85, stage: 'stitch' }), setItem() {}, removeItem() {} },
    renderNav() {}, getJobStatus: async () => ({ ok: true, body: status }), terminateJob: async () => ({ ok: true }),
    streamEvents(handlers) { events = handlers; return { close() {} }; }, setInterval: () => 1, clearInterval() {} };
  const html = fs.readFileSync(path.join(web, 'progress.html'), 'utf8');
  const script = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/^import .*;\s*$/gm, '');
  vm.runInNewContext(script, context);
  await new Promise(resolve => setImmediate(resolve));
  return { elements, context, events };
}

test('completed progress page navigates directly to the result', async () => {
  const { context } = await progressPage({ status: 'completed' });
  assert.equal(context.window.location.href, 'result.html');
});

test('a new generation uses server progress instead of stale browser storage', async () => {
  const { elements, events } = await progressPage({ status: 'running', stage: 'ingest', progress: 0 });
  events.stage_start({ stage: 'ingest', progress: 0 });
  assert.equal(elements.get('pct').textContent, '0%');
});

test('refreshed running generation restores current server progress', async () => {
  const { elements } = await progressPage({ status: 'running', stage: 'tts', progress: 62 });
  assert.equal(elements.get('pct').textContent, '62%');
});

test('Hindi example captions use its selected host names and language', () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const caption = source.slice(source.indexOf('function setCaption('), source.indexOf('function sync('));
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, { textContent: '', lang: '', dataset: {}, classList: { remove() {} } });
    return elements.get(id);
  };
  const context = { $, episode: { hosts: ['Amit', 'Raagini'], language: 'hi' }, turns: Array(32),
    reducedMotion: { matches: true }, document: { querySelector() { return null; } } };
  vm.runInNewContext(caption + '\nsetCaption({speaker:"Host 2",turn_id:2,text:"हमेशा।"},false);', context);
  assert.match($('caption-speaker').textContent, /^RAAGINI \/ HOST 2/);
  assert.equal($('caption-text').lang, 'hi');
});

test('aborted playback from a previous episode does not show a stale error', async () => {
  const source = fs.readFileSync(path.join(__dirname, 'examples.js'), 'utf8');
  const playback = source.slice(source.indexOf('async function startPlayback('), source.indexOf("play.addEventListener('click'"));
  let rejectPlayback;
  const errors = [];
  const context = { ready: true, loadVersion: 1, audioContext: { state: 'running' },
    audio: { play: () => new Promise((resolve, reject) => { rejectPlayback = reject; }) },
    $: () => ({ hidden: false }), showError: message => errors.push(message), syncPlayback() {} };
  vm.runInNewContext(playback + '\nglobalThis.pending = startPlayback();', context);
  context.loadVersion = 2;
  rejectPlayback(new Error('Playback aborted by new episode'));
  await context.pending;
  assert.deepEqual(errors, []);
});

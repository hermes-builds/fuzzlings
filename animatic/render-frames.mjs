/*
 * Renders animatic/scene.html to a PNG frame sequence with Playwright.
 *
 *   node render-frames.mjs --out /tmp/fz-frames            # full 120 s @ 20 fps
 *   node render-frames.mjs --out /tmp/fz-preview --preview # one still per beat
 *   node render-frames.mjs --out /tmp/x --from 25 --to 32   # a single beat range
 *
 * Needs a Chromium build: PLAYWRIGHT_BROWSERS_PATH must point at one
 * (on this box: /tmp/pw/browsers). Playwright itself is imported by absolute
 * path because NODE_PATH is ignored by ESM resolution.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PW = process.env.PLAYWRIGHT_PKG || '/tmp/pw/node_modules/playwright/index.js';

function arg(name, dflt) {
  const i = process.argv.indexOf('--' + name);
  if (i === -1) return dflt;
  const v = process.argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
}

const out = String(arg('out', '/tmp/fz-frames'));
const preview = Boolean(arg('preview', false));
const FPS = Number(arg('fps', 20));

const mod = await import(PW);
const chromium = mod.chromium ?? mod.default?.chromium;

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => { console.error('PAGE ERROR:', e.message); process.exitCode = 1; });
await page.goto('file://' + path.join(HERE, 'scene.html'));

const meta = await page.evaluate(() => ({
  fps: window.FZ.FPS, dur: window.FZ.DUR,
  beats: window.FZ.BEATS.map((b) => [b.start, b.end]),
}));

let shots = [];
if (preview) {
  // mid-beat still for every beat, plus the logo card
  meta.beats.forEach(([s, e], k) => shots.push({ i: Math.round(((s + e) / 2) * meta.fps), label: `beat${String(k + 1).padStart(2, '0')}` }));
  for (const sec of [118.6, 119.4, 116.2]) shots.push({ i: Math.round(sec * meta.fps), label: `logo_${sec}` });
} else {
  const from = Number(arg('from', 0));
  const to = Number(arg('to', meta.dur));
  for (let i = Math.round(from * FPS); i < Math.round(to * FPS); i++) {
    shots.push({ i, label: String(i).padStart(5, '0') });
  }
}

const t0 = Date.now();
let beatsSeen = new Set();
for (let k = 0; k < shots.length; k++) {
  const { i, label } = shots[k];
  const beatNo = await page.evaluate((j) => window.renderFrame(j), i);
  beatsSeen.add(beatNo);
  await page.screenshot({ path: path.join(out, `${label}.png`), type: 'png' });
  if (!preview && k % 200 === 0) {
    const pct = ((k / shots.length) * 100).toFixed(1);
    console.log(`${pct}% (${k}/${shots.length}) beat ${beatNo} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
}
await browser.close();
console.log(`done: ${shots.length} frames -> ${out} in ${((Date.now() - t0) / 1000).toFixed(1)}s; beats rendered: ${[...beatsSeen].sort((a, b) => a - b).join(',')}`);

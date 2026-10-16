/**
 * Verifieringsharness för pitchsajten.
 *
 * Kontrollerar acceptanskriterierna A3-A6 i en headless Chromium:
 *   - alla sex innehållssektioner finns (A3)
 *   - ingen horisontell overflow vid 375px (A4), kontrolleras även vid 320px
 *   - inga console-errors eller oupptäckta JS-fel (A5)
 *   - sidan är deklarerad på svenska (A6)
 *
 * Playwright är avsiktligt INTE ett repo-beroende (sajten har inget build-steg).
 * Kör med en extern installation. OBS: NODE_PATH ignoreras av ESM-importer,
 * så peka ut paketet med PLAYWRIGHT_PKG:
 *   PLAYWRIGHT_PKG=/tmp/pw/node_modules/playwright/index.js \
 *   PLAYWRIGHT_BROWSERS_PATH=/tmp/pw/browsers \
 *     node tools/check-site.mjs [url]
 *
 * Utan url-argument testas ./index.html lokalt.
 */
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const pkg = process.env.PLAYWRIGHT_PKG || 'playwright';
const mod = await import(
  pkg.startsWith('.') || pkg.startsWith('/') ? pathToFileURL(resolve(pkg)).href : pkg
);
// Playwrights entrypoint är CJS: via dynamic import hamnar exporterna
// ibland under .default beroende på hur paketet pekas ut.
const chromium = mod.chromium ?? mod.default?.chromium;
if (!chromium) throw new Error(`Kunde inte hitta chromium i ${pkg}`);

const REQUIRED_SECTIONS = [
  ['#hero', 'Hero'],
  ['#karaktarer', 'Karaktärer'],
  ['#manus', 'Pilotmanus'],
  ['#storyboard', 'Storyboard'],
  ['#produktion', 'Produktionsplan'],
  ['#research', 'Marknadsresearch'],
];

const VIEWPORTS = [375, 320];

const target =
  process.argv[2] || pathToFileURL(resolve('index.html')).href;

const failures = [];
const notes = [];

const browser = await chromium.launch();
try {
  for (const width of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width, height: 740 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();

    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`));
    page.on('requestfailed', (req) =>
      consoleErrors.push(`requestfailed: ${req.url()} ${req.failure()?.errorText ?? ''}`)
    );

    const response = await page.goto(target, { waitUntil: 'load' });
    if (response && !response.ok() && response.status() !== 0) {
      failures.push(`[${width}px] HTTP ${response.status()} för ${target}`);
    }
    await page.waitForTimeout(400);

    // A6: språk
    const lang = await page.getAttribute('html', 'lang');
    if (lang !== 'sv') failures.push(`[${width}px] html lang="${lang}" (väntade "sv")`);

    // A3: sektioner
    for (const [selector, label] of REQUIRED_SECTIONS) {
      const count = await page.locator(selector).count();
      if (count !== 1) {
        failures.push(`[${width}px] sektion ${label} (${selector}) hittades ${count} gånger`);
        continue;
      }
      const text = (await page.locator(selector).innerText()).trim();
      if (text.length < 40) {
        failures.push(`[${width}px] sektion ${label} har bara ${text.length} tecken text`);
      }
    }

    // A4: ingen horisontell overflow på dokumentnivå
    const overflow = await page.evaluate(() => {
      const de = document.documentElement;
      return {
        scrollWidth: de.scrollWidth,
        clientWidth: de.clientWidth,
        bodyScrollWidth: document.body.scrollWidth,
      };
    });
    if (overflow.scrollWidth > overflow.clientWidth) {
      failures.push(
        `[${width}px] dokumentet scrollar horisontellt: scrollWidth ${overflow.scrollWidth} > clientWidth ${overflow.clientWidth}`
      );
    }
    if (overflow.bodyScrollWidth > overflow.clientWidth) {
      failures.push(
        `[${width}px] body scrollar horisontellt: ${overflow.bodyScrollWidth} > ${overflow.clientWidth}`
      );
    }

    // A4 (skarpare): inget element får sticka ut utanför viewporten.
    // Element med avsiktlig egen horisontell scroll (opt-in via data-hscroll)
    // får vara bredare än sin box, men boxen själv måste passa.
    const strays = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const out = [];
      for (const el of document.querySelectorAll('body *')) {
        const style = getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        if (style.position === 'fixed') continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.right > vw + 1 || r.left < -1) {
          out.push({
            tag: el.tagName.toLowerCase(),
            cls: el.className?.toString().slice(0, 60) ?? '',
            left: Math.round(r.left),
            right: Math.round(r.right),
          });
        }
      }
      return out.slice(0, 12);
    });
    if (strays.length) {
      failures.push(
        `[${width}px] ${strays.length} element utanför viewporten: ` +
          strays.map((s) => `${s.tag}.${s.cls} [${s.left}..${s.right}]`).join(' | ')
      );
    }

    // Ordmärket måste rymmas på EN rad — annars hamnar ett ensamt "S"
    // på rad två, vilket ser trasigt ut på mobil.
    const markLines = await page.evaluate(() => {
      const el = document.querySelector('.wordmark');
      if (!el) return null;
      const cs = getComputedStyle(el);
      let lh = parseFloat(cs.lineHeight);
      if (!Number.isFinite(lh)) lh = parseFloat(cs.fontSize) * 1.2;
      return Math.round(el.getBoundingClientRect().height / lh);
    });
    if (markLines === null) {
      failures.push(`[${width}px] .wordmark saknas`);
    } else if (markLines > 1) {
      failures.push(`[${width}px] .wordmark radbryts över ${markLines} rader (ska vara 1)`);
    } else {
      notes.push(`[${width}px] ordmärket på 1 rad`);
    }

    // A3 (skarpare): karaktärernas namn och epitet måste återges ORDAGRANT
    // som i källdokumentet — även där källsträngen ser trasig ut. Att
    // "städa" källan är en innehållsändring, inte ett designval.
    const SOURCE_EPITHETS = [
      ['Zyp', 'Den nyfikna'],
      ['Dolm', 'Den försiktiga'],
      ['Bix', 'Translation äxlaren'],
    ];
    const chrText = await page.locator('#karaktarer').innerText();
    for (const [name, epithet] of SOURCE_EPITHETS) {
      if (!chrText.includes(name)) failures.push(`[${width}px] karaktären ${name} saknas`);
      if (!chrText.includes(epithet)) {
        failures.push(`[${width}px] ${name}: epitetet "${epithet}" saknas (källans ordalydelse)`);
      }
    }

    // A5: console
    if (consoleErrors.length) {
      failures.push(`[${width}px] console-fel: ${consoleErrors.join(' | ')}`);
    } else {
      notes.push(`[${width}px] 0 console-fel`);
    }

    // Läsbarhet: brödtext ska inte vara pytteliten på mobil.
    const bodyFontPx = await page.evaluate(() =>
      parseFloat(getComputedStyle(document.body).fontSize)
    );
    if (bodyFontPx < 16) {
      failures.push(`[${width}px] body font-size ${bodyFontPx}px < 16px`);
    } else {
      notes.push(`[${width}px] body font-size ${bodyFontPx}px`);
    }

    notes.push(`[${width}px] dokumenthöjd ${await page.evaluate(() => document.documentElement.scrollHeight)}px`);
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(`MÅL: ${target}`);
for (const n of notes) console.log(`  info  ${n}`);
if (failures.length) {
  console.log(`\nFAIL (${failures.length}):`);
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
console.log('\nPASS: alla kontroller gröna (A3, A4, A5, A6).');

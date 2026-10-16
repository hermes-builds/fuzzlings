# FUZZLINGS — pitchsajt

Statisk, mobile-first pitchsajt för seriekonceptet **Fuzzlings**: dialogfri
fysisk komedi i mikroformat för 4–7 år.

Live: <https://hermes-builds.github.io/fuzzlings/>

## Innehåll

Sajten är en enda sida med sex sektioner:

| Sektion | Ankare | Innehåll |
|---|---|---|
| Konceptet | `#hero` | Namn, logline, målgrupp, format, miljön Kosmoland |
| Karaktärer | `#karaktarer` | Zyp (orange), Dolm (blågrå), Bix (magenta) |
| Pilotmanus | `#manus` | ”Studsfällan”, scen för scen 0:00–2:00 |
| Storyboard | `#storyboard` | 15 beats som kort, ett per bild |
| Produktion | `#produktion` | Teknik/stil, tid per avsnitt, skalning |
| Marknad | `#research` | Mönster, luckor och varför konceptet funkar |

Allt textinnehåll är hämtat ur två källdokument (pilotavsnittet och
marknadsresearchen) och ska inte ändras utan att källan ändras först.

## Teknik

Vanilla HTML, CSS och ca 50 rader JavaScript. **Inget build-steg, inga
beroenden, ingen pipeline** — `index.html`, `styles.css` och `script.js`
servas precis som de ligger.

- `index.html` — all text och struktur
- `styles.css` — mobile-first; brytpunkter vid 560px och 900px
- `script.js` — markerar aktiv sektion i navigeringen under scroll.
  Ren progressiv förbättring: utan JS fungerar sidan oförändrat.
- `.nojekyll` — hoppar över Jekyll-bygget på GitHub Pages

Layouten stackas alltid vertikalt. Ingen horisontell scrollyta används
någonstans, vilket är själva garantin mot sidoscroll på små skärmar.

## Kör lokalt

```sh
python3 -m http.server 8000
# öppna http://localhost:8000
```

Eller öppna `index.html` direkt i webbläsaren — sajten har inga
fetch-anrop och fungerar även över `file://`.

## Verifiering

`tools/check-site.mjs` kontrollerar i headless Chromium att:

- alla sex sektioner finns och har innehåll
- ingen horisontell overflow uppstår vid 375px **och** 320px — varken på
  dokumentnivå eller för något enskilt element
- ordmärket ”FUZZLINGS” ryms på en rad
- inga console-fel, JS-fel eller misslyckade requests
- `<html lang="sv">` och brödtext ≥ 16px

Playwright är avsiktligt inget repo-beroende. Peka ut en extern
installation — notera att `NODE_PATH` ignoreras av ESM-importer, därav
`PLAYWRIGHT_PKG`:

```sh
PLAYWRIGHT_PKG=/tmp/pw/node_modules/playwright/index.js \
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw/browsers \
  node tools/check-site.mjs
```

Skriptet tar en valfri URL som argument (annars testas `./index.html`), så
samma kontroll kan köras mot den publicerade sajten:

```sh
… node tools/check-site.mjs https://hermes-builds.github.io/fuzzlings/
```

Exit 0 = allt grönt, exit 1 = lista med avvikelser.

## Publicering

GitHub Pages servar `main` från repo-roten. Push till `main` räcker; ingen
workflow behövs.

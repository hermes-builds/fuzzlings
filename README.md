# FUZZLINGS — pitchsajt

Statisk, mobile-first pitchsajt för seriekonceptet **Fuzzlings**: dialogfri
fysisk komedi i mikroformat för 4–7 år.

Live: <https://hermes-builds.github.io/fuzzlings/>

## Innehåll

Sajten är en enda sida med sju sektioner:

| Sektion | Ankare | Innehåll |
|---|---|---|
| Konceptet | `#hero` | Namn, logline, målgrupp, format, miljön Kosmoland |
| Animatic | `#animatic` | Inbäddad 2-minuters animatic av piloten |
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

## Animaticen

`media/animatic.mp4` (1920×1080, H.264+AAC, 2:00) byggs från källorna i
`animatic/`. Videon är en commitad artefakt — Pages har inget build-steg —
men den kan reproduceras helt:

```sh
cd animatic

# 1. ljudeffekter (ElevenLabs sound-effects; nyckeln läses ur miljön)
export ELEVENLABS_API_KEY=...        # aldrig i repot
python3 make-sfx.py --out sfx        # faller tillbaka på ffmpeg-syntes vid fel
                                     # provenance per cue: sfx/provenance.json

# 2. bildrutor (2400 PNG @ 20 fps ur scene.html)
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw/browsers \
  node render-frames.mjs --out /tmp/fz-frames
#   --preview ger i stället en stillbild per beat, bra för snabb granskning

# 3. mixa + koda
./build-video.sh /tmp/fz-frames ../media/animatic.mp4
```

| Fil | Roll |
|---|---|
| `animatic/scene.html` | all bild: karaktärer, Kosmoland och alla 15 beats som deterministisk `renderFrame(i)` |
| `animatic/render-frames.mjs` | kör `renderFrame` i headless Chromium → PNG-sekvens |
| `animatic/sfx.json` | cue-lista: tidkod, gain och ljudprompt per effekt |
| `animatic/make-sfx.py` | hämtar varje cue från ElevenLabs, annars lokal syntes |
| `animatic/mix-audio.py` | lägger cues på en 120 s-bädd, mixar och limitar |
| `animatic/build-video.sh` | PNG + ljud → MP4 och posterbild |
| `animatic/verify-video.py` | granskar den färdiga filen (se nedan) |

`scene.html` är helt deterministisk: ingen `Math.random`, ingen väggklocka.
All variation kommer ur `mulberry32` med fasta seeds, så samma bildruta ger
alltid samma pixlar — vilket är det som gör rutjämförelsen i
`verify-video.py` meningsfull.

`sfx/` (ljudfilerna) ligger utanför repot via `.gitignore`: de kan
återskapas från `sfx.json` och deras provenance loggas lokalt.

## Verifiering

`tools/check-site.mjs` kontrollerar i headless Chromium att:

- alla sju sektioner finns och har innehåll
- animatic-sektionen har en `<video>` med `controls`, `playsinline` och
  poster, och att både MP4:en och posterbilden faktiskt svarar/finns
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

`animatic/verify-video.py` granskar den **kodade** MP4:en — inget tas på
förtroende:

```sh
python3 animatic/verify-video.py media/animatic.mp4 --frames /tmp/fz-frames
```

- codec, upplösning, pix_fmt, längd (115–125 s) och filstorlek
- alla 15 beats i rätt ordning: varje beats mittruta plockas ur videon och
  matchas mot referensrutan för samma tidkod. En beat är grön bara om dess
  **egen** referens är närmast av alla 15 — en omkastad eller tappad beat
  blir röd även om varje enskild bild ser rimlig ut.
- ljudet: varje cue-fönster måste ligga tydligt över ambiensgolvet, och
  nivåerna måste skilja sig åt (annars är det samma ljud om och om igen)

Exit 0 = allt grönt, exit 1 = lista med avvikelser.

## Publicering

GitHub Pages servar `main` från repo-roten. Push till `main` räcker; ingen
workflow behövs.

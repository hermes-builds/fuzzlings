# Fuzzlings — kanoniska kommandon.
#
# Sajten har inget build-steg: index.html/styles.css/script.js servas som de
# ligger. Det här är därför bara verifiering och ombyggnad av animaticen.
#
#   make verify     allt nedan (detta är kommandot att köra)
#   make site       pitchsajten i headless Chromium
#   make video      den kodade MP4:en (codec, längd, 15 beats, ljudcues)
#   make refs       de 15 referensrutor `video` jämför mot (~8 s)
#   make animatic   bygg om videon från grunden (~15 min)
#
# Playwright är avsiktligt inget repo-beroende. Peka ut en extern
# installation; NODE_PATH ignoreras av ESM-importer, därav PLAYWRIGHT_PKG.

PW       ?= /tmp/pw/node_modules/playwright/index.js
BROWSERS ?= /tmp/pw/browsers
URL      ?= index.html
FRAMES   ?= /tmp/fz-refs
MP4      ?= media/animatic.mp4

PWENV = PLAYWRIGHT_PKG=$(PW) PLAYWRIGHT_BROWSERS_PATH=$(BROWSERS)

.PHONY: verify site video refs animatic

verify: site video

# URL=https://hermes-builds.github.io/fuzzlings/ kör samma kontroll mot Pages.
site:
	$(PWENV) node tools/check-site.mjs $(URL)

video: $(FRAMES)
	python3 animatic/verify-video.py $(MP4) --frames $(FRAMES)

refs $(FRAMES):
	$(PWENV) node animatic/render-frames.mjs --out $(FRAMES) --refs

# Kräver ELEVENLABS_API_KEY i miljön för riktiga ljudeffekter; utan nyckel
# faller make-sfx.py tillbaka på lokal ffmpeg-syntes och loggar det.
animatic:
	cd animatic && python3 make-sfx.py --out sfx
	$(PWENV) node animatic/render-frames.mjs --out /tmp/fz-frames
	cd animatic && ./build-video.sh /tmp/fz-frames ../$(MP4)

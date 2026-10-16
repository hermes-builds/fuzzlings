#!/usr/bin/env python3
"""Generate the animatic's sound effects from animatic/sfx.json.

Primary path: the ElevenLabs sound-effects API (POST /v1/sound-generation).
The API key is read from the environment only (ELEVENLABS_API_KEY) and is
never written to disk or into any generated file.

Fallback path: if the API errors out (quota, network, auth), the cue is
synthesised locally with ffmpeg so the build still produces audio. Every
cue's provenance is recorded in <outdir>/provenance.json so the summary can
state honestly which sounds came from where.

    python3 make-sfx.py --out sfx            # generate missing cues
    python3 make-sfx.py --out sfx --force    # regenerate everything
"""
import argparse
import json
import os
import pathlib
import random
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.elevenlabs.io/v1/sound-generation"
HERE = pathlib.Path(__file__).resolve().parent


def elevenlabs(prompt: str, seconds: float, dest: pathlib.Path, key: str) -> None:
    body = json.dumps({
        "text": prompt,
        "duration_seconds": max(0.5, min(22.0, float(seconds))),
        "prompt_influence": 0.6,
        "output_format": "mp3_44100_128",
    }).encode()
    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    if len(data) < 2000:
        raise RuntimeError(f"suspiciously small payload: {len(data)} bytes")
    dest.write_bytes(data)


def synth(cue: dict, dest: pathlib.Path) -> None:
    """Local ffmpeg fallback: a tone/noise sketch shaped by the cue name."""
    name, dur = cue["name"], float(cue["dur"])
    rnd = random.Random(name)
    if "floinng" in name or "boing" in name:
        src = (f"sine=frequency=160:duration={dur},"
               f"vibrato=f=7:d=0.9,asetrate=44100*1.3,aresample=44100")
    elif "hiss" in name or "ffshh" in name:
        src = f"anoisesrc=color=white:duration={dur}:amplitude=0.35,highpass=f=1200"
    elif "beep" in name or "viip" in name or "ping" in name or "pip" in name:
        src = f"sine=frequency={700 + rnd.randint(0, 400)}:duration={dur},tremolo=f=6:d=0.9"
    elif "amb" in name:
        src = f"anoisesrc=color=brown:duration={dur}:amplitude=0.2,lowpass=f=900"
    elif "pop" in name:
        src = f"sine=frequency=900:duration={min(dur, 0.3)},aeval=val(0)*exp(-t*30)"
    else:
        src = f"anoisesrc=color=pink:duration={dur}:amplitude=0.3,lowpass=f=2500"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src,
           "-af", "afade=t=in:d=0.05,afade=t=out:st=%.2f:d=0.2" % max(0.1, dur - 0.25),
           "-c:a", "libmp3lame", "-b:a", "128k", str(dest)]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sfx")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true", help="skip the API, synthesise everything")
    args = ap.parse_args()

    out = (HERE / args.out) if not os.path.isabs(args.out) else pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cues = json.loads((HERE / "sfx.json").read_text())["cues"]
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key and not args.offline:
        print("ELEVENLABS_API_KEY not in environment -> falling back to local synthesis",
              file=sys.stderr)

    prov_path = out / "provenance.json"
    prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}

    for cue in cues:
        dest = out / f"{cue['name']}.mp3"
        if dest.exists() and not args.force:
            print(f"  keep   {dest.name} ({prov.get(cue['name'], {}).get('source', '?')})")
            continue
        src = "elevenlabs"
        if key and not args.offline:
            try:
                elevenlabs(cue["prompt"], cue["dur"], dest, key)
            except Exception as exc:  # noqa: BLE001 - any failure must degrade, not abort
                detail = ""
                if isinstance(exc, urllib.error.HTTPError):
                    try:
                        detail = exc.read().decode()[:200]
                    except Exception:  # noqa: BLE001
                        detail = ""
                print(f"  ! API failed for {cue['name']}: {exc} {detail}", file=sys.stderr)
                synth(cue, dest)
                src = "ffmpeg-synth"
        else:
            synth(cue, dest)
            src = "ffmpeg-synth"
        prov[cue["name"]] = {"source": src, "bytes": dest.stat().st_size}
        print(f"  {'OK   ' if src == 'elevenlabs' else 'SYNTH'} {dest.name} "
              f"{dest.stat().st_size} bytes [{src}]")

    prov_path.write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
    counts = {}
    for v in prov.values():
        counts[v["source"]] = counts.get(v["source"], 0) + 1
    print("provenance:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

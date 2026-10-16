#!/usr/bin/env python3
"""Lay the SFX cues from sfx.json onto a single 120 s stereo track.

Every cue is delayed to its storyboard timestamp, gain-staged, and mixed with
amix (normalize=0 so the levels stay as authored), then limited so the mix
never clips. The ambience cue is looped for the whole duration.

    python3 mix-audio.py --sfx sfx --out /tmp/audio.m4a
"""
import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DURATION = 120.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx", default="sfx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sfx_dir = pathlib.Path(args.sfx)
    if not sfx_dir.is_absolute():
        sfx_dir = HERE / sfx_dir
    cues = json.loads((HERE / "sfx.json").read_text())["cues"]

    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
    chains = []
    labels = []
    idx = 0
    missing = []
    for cue in cues:
        path = sfx_dir / f"{cue['name']}.mp3"
        if not path.exists():
            missing.append(cue["name"])
            continue
        if cue.get("loop_until"):
            cmd += ["-stream_loop", "-1", "-t", str(DURATION), "-i", str(path)]
        else:
            cmd += ["-i", str(path)]
        delay = int(round(float(cue["at"]) * 1000))
        gain = float(cue.get("gain", 0))
        lbl = f"a{idx}"
        chains.append(
            f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
            f"volume={gain}dB,adelay={delay}|{delay}[{lbl}]"
        )
        labels.append(f"[{lbl}]")
        idx += 1

    if missing:
        print(f"WARNING: missing sfx files: {', '.join(missing)}", file=sys.stderr)
    if not labels:
        print("no sfx inputs found", file=sys.stderr)
        return 1

    graph = ";".join(chains) + ";" + "".join(labels) + (
        f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.94:level=disabled,"
        f"atrim=0:{DURATION}[out]"
    )
    cmd += ["-filter_complex", graph, "-map", "[out]",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-t", str(DURATION), args.out]

    print(f"mixing {len(labels)} cues -> {args.out}")
    if args.dry_run:
        print(" ".join(cmd))
        return 0
    subprocess.run(cmd, check=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", args.out],
        capture_output=True, text=True, check=True)
    print(f"audio duration: {probe.stdout.strip()} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

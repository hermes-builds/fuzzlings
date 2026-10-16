#!/usr/bin/env python3
"""Verify the finished animatic against the task's acceptance criteria.

Checks, all from the encoded MP4 itself (nothing is taken on trust):

  A2  container/codecs/resolution/duration/file size
  A3  all 15 storyboard beats present, in order, at the right timestamps.
      Each beat's mid-frame is pulled out of the ENCODED video and matched
      against the reference frame rendered for that same timestamp. A beat
      passes only if its own reference is the closest of all 15 -- so a
      shuffled or dropped beat fails even if every frame looks plausible.
  A5  audio: every SFX cue window must stand clearly above the ambience
      floor, and the cue windows must not all be identical (distinctness).

    python3 verify-video.py ../media/animatic.mp4 --frames /tmp/fz-frames

Exit code 0 = all green, 1 = at least one failure.
"""
import argparse
import array
import json
import math
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC_FPS = 20                      # frame sequence fps (render-frames.mjs)
# storyboard beats: (number, start, end) in seconds
BEATS = [
    (1, 0, 5), (2, 5, 10), (3, 10, 18), (4, 18, 25), (5, 25, 32),
    (6, 32, 40), (7, 40, 50), (8, 50, 55), (9, 55, 70), (10, 70, 80),
    (11, 80, 90), (12, 90, 100), (13, 100, 108), (14, 108, 115), (15, 115, 120),
]
GW, GH = 64, 36                   # comparison grid


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def gray_grid(path_or_video, at=None):
    """Return a GWxGH grayscale byte vector for an image or a video timestamp."""
    cmd = ["ffmpeg", "-v", "error"]
    if at is not None:
        cmd += ["-ss", f"{at:.3f}"]
    cmd += ["-i", str(path_or_video), "-frames:v", "1",
            "-vf", f"scale={GW}:{GH}", "-pix_fmt", "gray",
            "-f", "rawvideo", "-"]
    out = run(cmd).stdout
    if len(out) < GW * GH:
        raise RuntimeError(f"short frame from {path_or_video} @ {at}: {len(out)} bytes")
    return array.array("B", out[: GW * GH])


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def audio_rms(video, step=0.25):
    """Decode the whole audio track to 8 kHz mono and return per-window RMS."""
    raw = run(["ffmpeg", "-v", "error", "-i", str(video), "-vn",
               "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    win = int(8000 * step)
    rms = []
    for i in range(0, len(samples) - win, win):
        s = 0
        for v in samples[i:i + win]:
            s += v * v
        rms.append(math.sqrt(s / win))
    return rms, step


def db(x):
    return 20 * math.log10(max(x, 1e-6) / 32768.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--frames", default="/tmp/fz-frames",
                    help="reference PNG sequence from render-frames.mjs")
    ap.add_argument("--max-mb", type=float, default=60.0)
    args = ap.parse_args()

    video = pathlib.Path(args.video).resolve()
    frames = pathlib.Path(args.frames)
    fails, info = [], []

    if not video.exists():
        print(f"FAIL: {video} does not exist")
        return 1

    # ---------- A2: container, codecs, geometry, duration, size ----------
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_format",
                            "-show_streams", "-of", "json", str(video)]).stdout)
    streams = probe["streams"]
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    dur = float(probe["format"]["duration"])
    size_mb = int(probe["format"]["size"]) / 1e6

    if v is None:
        fails.append("no video stream")
    else:
        if v["codec_name"] != "h264":
            fails.append(f"video codec is {v['codec_name']}, expected h264")
        if (v["width"], v["height"]) != (1920, 1080):
            fails.append(f"resolution {v['width']}x{v['height']}, expected 1920x1080")
        if v.get("pix_fmt") != "yuv420p":
            fails.append(f"pix_fmt {v.get('pix_fmt')}, expected yuv420p")
        info.append(f"video {v['codec_name']} {v['width']}x{v['height']} "
                    f"{v.get('pix_fmt')} {v.get('r_frame_rate')}")
    if a is None:
        fails.append("no audio stream (A5 needs an audio track)")
    else:
        if a["codec_name"] != "aac":
            fails.append(f"audio codec is {a['codec_name']}, expected aac")
        info.append(f"audio {a['codec_name']} {a.get('sample_rate')}Hz {a.get('channels')}ch")
    if not (115.0 <= dur <= 125.0):
        fails.append(f"duration {dur:.2f}s outside 115-125s")
    else:
        info.append(f"duration {dur:.2f}s")
    if size_mb > args.max_mb:
        fails.append(f"file size {size_mb:.1f} MB exceeds {args.max_mb} MB")
    else:
        info.append(f"size {size_mb:.1f} MB")

    # ---------- A3: 15 beats, in order, on time ----------
    if not frames.is_dir():
        fails.append(f"reference frames dir missing: {frames} (A3 unverified)")
    else:
        refs = {}
        for num, s, e in BEATS:
            mid = (s + e) / 2
            idx = round(mid * SRC_FPS)
            p = frames / f"{idx:05d}.png"
            if not p.exists():
                fails.append(f"beat {num}: reference frame {p.name} missing")
                continue
            refs[num] = (mid, gray_grid(p))
        for num, s, e in BEATS:
            if num not in refs:
                continue
            mid, own = refs[num]
            try:
                got = gray_grid(video, at=mid)
            except Exception as exc:  # noqa: BLE001
                fails.append(f"beat {num}: could not read video @ {mid}s: {exc}")
                continue
            scored = sorted(((dist(got, g), n) for n, (_, g) in refs.items()))
            best_d, best_n = scored[0]
            own_d = dist(got, own)
            if best_n != num:
                fails.append(
                    f"beat {num} @ {mid}s: frame matches beat {best_n} better "
                    f"(d={best_d:.1f} vs own d={own_d:.1f}) -> wrong beat on screen")
            else:
                runner = scored[1][0] if len(scored) > 1 else float("inf")
                info.append(f"beat {num:2d} @ {mid:5.1f}s ok (d={own_d:.1f}, "
                            f"next best {runner:.1f})")

    # ---------- A5: distinct SFX on key beats ----------
    if a is not None:
        rms, step = audio_rms(video)
        if not rms:
            fails.append("audio track decoded to nothing")
        else:
            nz = sorted(r for r in rms if r > 0)
            floor = nz[len(nz) // 10] if nz else 0.0     # 10th percentile = ambience
            info.append(f"audio floor {db(floor):.1f} dBFS over {len(rms)} windows")
            cues = json.loads((HERE / "sfx.json").read_text())["cues"]
            peaks = {}
            for cue in cues:
                if cue.get("loop_until"):
                    continue                              # ambience bed, not a hit
                at = float(cue["at"])
                lo = max(0, int((at - 0.2) / step))
                hi = min(len(rms), int((at + min(float(cue["dur"]), 4.0)) / step))
                if hi <= lo:
                    continue
                peak = max(rms[lo:hi])
                peaks[cue["name"]] = peak
                if peak < floor * 2.0:
                    fails.append(f"cue {cue['name']} @ {at}s: peak {db(peak):.1f} dBFS "
                                 f"is not clearly above the floor {db(floor):.1f} dBFS")
            if peaks:
                distinct = len({round(db(p), 1) for p in peaks.values()})
                info.append(f"{len(peaks)} sfx cues audible, {distinct} distinct peak levels "
                            f"({db(min(peaks.values())):.1f}..{db(max(peaks.values())):.1f} dBFS)")
                if distinct < 5:
                    fails.append(f"only {distinct} distinct cue levels — sounds may be identical")

    print(f"VIDEO: {video}")
    for line in info:
        print(f"  info  {line}")
    if fails:
        print(f"\nFAIL ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nPASS: A2 (codecs/duration/size), A3 (15 beats in order), A5 (audio cues).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

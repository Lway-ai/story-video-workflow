#!/usr/bin/env python3
"""Render the narration lines from a shot table with a TTS tool.

Usage:
    python3 tts-narration.py <shots-table.csv> <out-dir> [--speed 125] [--voice VOICE]

- Reads the narration column (default: 浓缩旁白) from the shot-table CSV.
- Renders one WAV per shot: NN-<SHOT>.wav (NN = shot index from 01).
- Strips the ID3v2 tag the TTS tool prepends to its WAV output before probing.
- Prints each line's duration and flags lines over 8.8 s (the per-shot limit
  for a 9 s shot with a 0.2 s lead-in). Re-render flagged lines faster
  (--speed 150, then 175) until they fit; if a line still does not fit,
  split it at punctuation and join the parts with 0.25 s gaps, keeping every word.
- TTS is deterministic for the same text + speed.

The TTS command is taken from $TTS_CMD (default: `tts`); adapt it to your
setup. The example production used:
    tts speak --text <text> --voice <voice> --language zh --format wav \
        --speed <speed> --output <file>
with a single male narration voice for the whole film. Pass the voice with
--voice or $TTS_VOICE. Speed range 1-200, default 100; base speed 125 in the
example production (about 5.30 chars/s, but per-line variance is large —
always measure, never estimate from character count).
"""
import argparse
import csv
import json
import os
import subprocess
import sys

LIMIT = 8.8  # seconds; a 9 s shot leaves 0.2 s lead-in


def strip_id3(path):
    """TTS prepends an ID3v2 tag to the WAV; remove it so ffprobe can read it."""
    with open(path, "rb") as f:
        head = f.read(10)
    if head[:3] != b"ID3":
        return
    size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) \
        | ((head[8] & 0x7F) << 7) | (head[9] & 0x7F)
    total = 10 + size
    if head[5] & 0x10:  # footer present
        total += 10
    with open(path, "rb") as f:
        data = f.read()
    with open(path, "wb") as f:
        f.write(data[total:])


def duration(path):
    p = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_format", path], capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", help="shot-table CSV (UTF-8-SIG)")
    ap.add_argument("outdir", help="directory for NN-<SHOT>.wav files")
    ap.add_argument("--speed", default="125", help="base TTS speed (default 125)")
    ap.add_argument("--voice", default=os.environ.get("TTS_VOICE", ""),
                    help="narration voice id (or $TTS_VOICE)")
    ap.add_argument("--column", default="浓缩旁白", help="narration column name")
    ap.add_argument("--only", default="", help="comma-separated shot ids to render")
    args = ap.parse_args()
    if not args.voice:
        raise SystemExit("no voice: pass --voice or set $TTS_VOICE")
    tts = os.environ.get("TTS_CMD", "tts")
    os.makedirs(args.outdir, exist_ok=True)

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    only = set(args.only.split(",")) if args.only else None
    over = []
    total = 0.0
    for i, r in enumerate(rows, 1):
        sid = r["镜号"]
        if only and sid not in only:
            continue
        out = os.path.join(args.outdir, f"{i:02d}-{sid}.wav")
        res = subprocess.run([tts, "speak",
                              "--text", r[args.column],
                              "--voice", args.voice,
                              "--language", "zh",
                              "--format", "wav",
                              "--speed", args.speed,
                              "--output", out],
                             capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{sid}: TTS FAILED rc={res.returncode} "
                  f"{res.stderr.strip()[:200]}", flush=True)
            continue
        strip_id3(out)
        d = duration(out)
        total += d
        flag = "  <-- OVER 8.8s" if d > LIMIT else ""
        if flag:
            over.append((sid, d))
        print(f"{i:02d} {sid}: {d:.2f}s{flag}", flush=True)

    print(f"total narration: {total:.3f}s over {len(rows)} lines")
    print("OVER:", over)
    if over:
        print("Re-render these at --speed 150, then 175; "
              "if still over, split at punctuation and join with 0.25s gaps.")


if __name__ == "__main__":
    main()

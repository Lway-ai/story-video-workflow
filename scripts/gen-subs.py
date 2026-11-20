#!/usr/bin/env python3
"""Generate assembly inputs from the shot table + measured narration WAVs:
- subs.srt (one entry per shot; start = shot start + 0.2s, length = narration duration)
- shot-map.txt (one line per shot: SHOT <video file>; missing shots = BLACK)

Usage:
    python3 gen-subs.py <shots-table.csv> <narration-dir> <subs-out.srt> <map-out.txt>
        [--top-shot S804] [--video-prefix shots/] [--missing S307]

The shot map is read by build-segments.sh. A shot listed in --missing (repeat
the flag for several) gets a BLACK entry: its 9 s slot is kept as black video
with narration, never filled with another shot's footage.
"""
import argparse
import csv
import json
import os
import subprocess


def duration(path):
    p = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_format", path], capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", help="shot-table CSV (UTF-8-SIG)")
    ap.add_argument("narration_dir", help="directory of NN-<SHOT>.wav files")
    ap.add_argument("subs_out", help="SRT output path")
    ap.add_argument("map_out", help="shot-map output path")
    ap.add_argument("--top-shot", action="append", default=[],
                    help="shot whose subtitle is top-aligned ({\\an8}); repeatable")
    ap.add_argument("--video-prefix", default="",
                    help="prefix for video paths in the map (e.g. shots/)")
    ap.add_argument("--missing", action="append", default=[],
                    help="shot id with no video (BLACK entry); repeatable")
    ap.add_argument("--column", default="浓缩旁白", help="narration column name")
    ap.add_argument("--start-column", default="开始秒", help="shot-start column name")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    srt_lines = []
    map_lines = []
    total_nar = 0.0
    for i, r in enumerate(rows, 1):
        sid = r["镜号"]
        start = float(r[args.start_column])
        nar = os.path.join(args.narration_dir, f"{i:02d}-{sid}.wav")
        d = duration(nar)
        total_nar += d
        srt_lines.append(str(i))
        srt_lines.append(f"{ts(start + 0.2)} --> {ts(start + 0.2 + d)}")
        text = r[args.column]
        if sid in args.top_shot:
            text = "{\\an8}" + text
        srt_lines.append(text)
        srt_lines.append("")
        src = "BLACK" if sid in args.missing else f"{args.video_prefix}{sid}.mp4"
        map_lines.append(f"{sid} {src}")

    with open(args.subs_out, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    with open(args.map_out, "w", encoding="utf-8") as f:
        f.write("\n".join(map_lines) + "\n")
    print(f"SRT entries: {len(rows)} | map lines: {len(map_lines)}")
    print(f"total narration: {total_nar:.3f}s")


if __name__ == "__main__":
    main()

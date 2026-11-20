#!/usr/bin/env python3
"""Call a chat LLM twice to write a novel from a research brief.

- Call 1: Part 1 - the distress arc (departure -> worsening environment ->
  last message -> loss of contact). ~5000 chars.
- Call 2: Part 2 - the search arc, with Part 1 passed as context, ending at
  the find (clothes and distant covering only). ~4000 chars.

Usage:
    DEEPSEEK_API_KEY=... python3 call-deepseek-novel.py <brief.md> <novel-out.md>

The API key is read ONLY from the DEEPSEEK_API_KEY environment variable
(supplied transiently for this one run). It is never written to any file.
The combined output is a RAW draft: it MUST be proofread (see
proofread-fix.py) before it is used for a shot table.

The part prompts below describe the example film's two arcs. Adapt the
--part1/--part2 descriptions to your own story; keep the split (one call per
arc, second call sees the first part) so the two halves stay consistent.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


def call_llm(messages, tag):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY not set in environment")
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 1.0,
        "max_tokens": 8192,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        print(f"[{tag}] HTTP {e.code}: {err[:500]}", file=sys.stderr)
        raise SystemExit(f"[{tag}] LLM call failed with HTTP {e.code}")
    except Exception as e:
        print(f"[{tag}] request error: {e}", file=sys.stderr)
        raise SystemExit(f"[{tag}] LLM call failed: {e}")
    choices = body.get("choices") or []
    if not choices:
        raise SystemExit(f"[{tag}] no choices in response: {str(body)[:500]}")
    text = choices[0]["message"]["content"]
    finish = choices[0].get("finish_reason")
    print(f"[{tag}] chars={len(text)} finish_reason={finish}")
    if finish == "length":
        print(f"[{tag}] WARNING: output was truncated at max_tokens; "
              "raise max_tokens or split the part", file=sys.stderr)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief", help="research brief markdown (see templates/brief-template.md)")
    ap.add_argument("output", help="where to save the raw draft novel")
    ap.add_argument("--part1", default=(
        "请写第一部分：遇险——从出发，到环境一步步恶化，到最后一条消息、失联为止。"
        "约5000字，只写这一部分，不要写搜寻部分。直接输出小说正文。"),
        help="instruction for part 1 (default: distress arc)")
    ap.add_argument("--part2", default=(
        "请接着写第二部分：搜寻——救援如何展开、如何找到，收在找到的那一刻，"
        "只写衣物和远景覆盖。约4000字。风格、人物、衣着与第一部分保持一致。"
        "直接输出小说正文。"),
        help="instruction for part 2 (default: search arc)")
    ap.add_argument("--title", default="小说初稿（未校对）",
                    help="title written into the output file header")
    args = ap.parse_args()

    with open(args.brief, "r", encoding="utf-8") as f:
        brief = f.read()

    system = ("你是一位擅长写悬疑纪实风格小说的中文作家。只输出小说正文，"
              "不要加任何解释、前言或总结。")

    part1 = call_llm(
        [{"role": "system", "content": system},
         {"role": "user", "content": brief + "\n\n" + args.part1}],
        "part1")

    part2 = call_llm(
        [{"role": "system", "content": system},
         {"role": "user", "content": brief + "\n\n第一部分已写好如下：\n" + part1
          + "\n\n" + args.part2}],
        "part2")

    header = (
        f"# {args.title}\n\n"
        "> 由小说模型按简报写成，分两次调用。未经通读校对，底线核查待做。人物一律化名。\n\n"
    )
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("## 第一部分\n\n")
        f.write(part1)
        f.write("\n\n## 第二部分\n\n")
        f.write(part2)
        f.write("\n")
    total = len(part1) + len(part2)
    print(f"DONE part1={len(part1)} part2={len(part2)} total={total}")
    print(f"saved to {args.output} (RAW DRAFT - proofread before use)")


if __name__ == "__main__":
    main()

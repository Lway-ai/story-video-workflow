#!/usr/bin/env python3
"""Scripted proofread-fix pass for an LLM-written novel draft.

The model WILL write things that contradict the facts, the timeline, the
character lock, or the bottom lines. Read the whole draft first, collect the
fixes, then encode them here so the pass is reproducible and auditable:

- SINGLES: (old, new, expected_count). Each replacement is asserted to occur
  exactly `expected_count` times (usually 1) before it is applied. If the
  count differs, the script FAILS instead of silently doing the wrong edit.
- GLOBALS: (old, new). Replace every occurrence; must occur at least once.
- CUT: a structural cut — delete a whole passage (e.g. a return-home scene
  that contradicts the facts) and insert a compliant ending instead.
  The cut is located by exact start/end marker strings.
- FORBIDDEN: strings that must be absent after all fixes (bottom-line
  violations, wrong names, removed elements). Any hit FAILS the pass.
- REQUIRED: strings that must be present after all fixes (time anchors,
  pseudonyms, character-lock items). Any miss FAILS the pass.

Usage:
    python3 proofread-fix.py <novel.md>

Appends a "校对改动" footer listing what was changed and why (edit FOOTER
for your own fixes). The file is edited in place; keep a copy of the raw
draft first.

The entries below are EXAMPLES in the shape of real fixes from the example
production — replace them with the fixes YOUR draft needs. Do not run this
script with the example entries on your own novel: the assertions will (and
should) fail.
"""
import sys

# ---- EXAMPLE entries (replace with your own) -------------------------------
# Each entry shows one KIND of fix. The strings below are self-describing
# placeholders — replace each with the exact sentence from YOUR draft.
# The script asserts counts, so a placeholder that does not occur in your file
# will (correctly) fail instead of silently doing nothing.
SINGLES = [
    # (old, new, expected_count)
    # Kind 1: a wrong time anchor for a key message.
    ("把这里换成稿子里写错时间的原句", "把这里换成改对时间的句子", 1),
    # Kind 2: a person written with the wrong identity.
    ("把这里换成稿子里写错身份的原句", "把这里换成改对身份的句子", 1),
    # Kind 3: an item colour not matching the character lock.
    ("把这里换成稿子里颜色写错的原句", "把这里换成按人物锁定改对的句子", 1),
    # Kind 4: a leftover-items passage that is logically impossible
    # (worn clothes and the power bank cannot be left at the homestay).
    ("把这里换成稿子里遗留物品写错的原句",
     "把这里换成改写后的句子：旅行包里的换洗衣服和充电线；手机和充电宝随主角上山。", 1),
    # Kind 5: the find scene describing remains detail — remove it.
    ("把这里换成稿子里越线的发现场景原句",
     "把这里换成改写后的句子：只留屏幕上的一小块颜色。", 1),
]

GLOBALS = [
    # Kind 6: unify a person's name to the chosen pseudonym.
    ("把这里换成稿子里出现的真名或错名", "把这里换成化名"),
]

# Structural cut: (start marker, end marker, replacement).
# Kind 7: a passage where the protagonist returns home alive, contradicting
# the facts and the second part. Cut from CUT_START through CUT_END inclusive.
CUT_START = "把这里换成应删段落的第一句话"
CUT_END = "把这里换成应删段落的最后一句话"
CUT_REPLACEMENT = (
    "此后没有任何记录。没有目击者，没有通话，没有监控。"
    "公开报道从未还原她下撤的这段路。"
)

# Must be absent after all fixes (bottom-line violations, wrong names, etc.).
FORBIDDEN = [
    "把这里换成应删的错误人名",
    "把这里换成应删的遗体细节词",
    "把这里换成用户已定不写的元素",
]
# Must be present after all fixes (anchors, pseudonyms, character lock).
REQUIRED = [
    "把这里换成关键消息的正确时间",
    "把这里换成最后一条消息的正确时间",
    "把这里换成化名 A", "把这里换成化名 B",
    "把这里换成人物锁定的背包颜色", "把这里换成人物锁定的鞋子",
]

FOOTER = """
---

## 校对改动（通读校对）

1. 结构性矛盾：第一部分写主角下撤后活着回到民宿，与事实和第二部分自相矛盾。
   整段删掉，改为下撤入雾、失联、此后无记录的收束。
2. 时间锚点：关键消息的时间改回正确值；上午时间线相应后移；最后一条消息的时间不动。
3. 人物身份：民宿主人改回正确人选；删掉用户已定不写的动物。
4. 人物锁定：背包、鞋子颜色按锁定统一；补发型等锁定特征。
5. 遗留物品：穿戴衣物和充电宝不可能留在民宿，改写为旅行包里的换洗衣服和充电线。
6. 人名：救援队人名统一为化名。
7. 发现场景：删掉遗体姿态描写，只留无人机屏幕上的一小块颜色。
8. 地点推测：搜救会上提及某地点方向时，写明只是推测，不能当路线用。
"""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        raise SystemExit("usage: python3 proofread-fix.py <novel.md>")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    for old, new, expected in SINGLES:
        n = text.count(old)
        if n != expected:
            print(f"FAIL: expected {expected}x {old[:40]!r}, found {n}x")
            sys.exit(1)
        text = text.replace(old, new)
        print(f"ok single: {old[:30]}...")

    for old, new in GLOBALS:
        n = text.count(old)
        if n < 1:
            print(f"FAIL: global {old!r} not found")
            sys.exit(1)
        text = text.replace(old, new)
        print(f"ok global: {old!r} x{n} -> {new!r}")

    if CUT_START:
        si = text.find(CUT_START)
        ei = text.find(CUT_END)
        if si < 0 or ei < 0 or ei <= si:
            print(f"FAIL: cut markers not found (start={si}, end={ei})")
            sys.exit(1)
        ei += len(CUT_END)
        text = text[:si] + CUT_REPLACEMENT + text[ei:]
        print("ok structural cut applied")

    for bad in FORBIDDEN:
        if bad in text:
            print(f"FAIL: forbidden string still present: {bad!r}")
            sys.exit(1)
    for good in REQUIRED:
        if good not in text:
            print(f"FAIL: required string missing: {good!r}")
            sys.exit(1)
    print("ok forbidden/required checks passed")

    if "校对改动" not in text:
        text = text.rstrip("\n") + "\n" + FOOTER
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"DONE fixed novel chars={len(text)} saved to {path}")


if __name__ == "__main__":
    main()

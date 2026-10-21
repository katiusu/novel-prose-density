#!/usr/bin/env python3
"""亲密场景用词自查（v2.1.0）：只管 18+ 特有问题，风格项归 story-prose-dense。

1. 强禁（HARD）：代称 / 雅称 / 隐喻代称 / 昵称，命中即违规。
2. 软禁（HARD_RE）：缝隙／皱褶／丘陵／山谷／口子／嫩肉／领地，同行没有解剖实名时才判违规。
3. 语境代称（CTX）：那处／那里／底下／它／它们，同行出现解剖实名或手／指／唇等动作词时才判违规。
4. 弱提示（TIP）：快感／感觉／刺激／某种，只提示。

用法: check_intimacy.py 正文/第001章.md [...]
退出码：有强禁或语境代称时 1，否则 0。
"""
import re
import sys


# 白名单雅称（作者批准，不判违规）：花穴 蜜穴 花蜜 蜜液 爱液 银丝
HARD = [
    # 指示性代称
    "私处", "要害", "关键部位", "敏感的地方", "敏感处", "那一带", "某处", "某个地方",
    "那东西", "那玩意儿", "那一团", "那点液体", "一股温", "一股热",
    # 位置隐喻
    "三角地带", "那片领地", "丘陵", "山谷", "花园", "最私密的地方", "腿间那一小块",
    # 形态隐喻
    "那道缝隙", "那道口子", "那道皱褶",
    # 通道隐喻
    "甬道", "腔道", "通道",
    # 昵称化
    "小豆豆", "小核", "那粒宝贝",
    # 雅化借代（白名单外）
    "幽谷", "桃源", "玉门", "玉茎", "甘露", "情潮", "春潮", "欲火",
    # 体液代称
    "分泌物", "湿意", "晶莹的液体", "透明的液体",
    # 模糊动词
    "要了她", "进入了她", "弄了弄", "开始动作",
]
# 隐喻软词：单独出现即代称，但同行有解剖实名时放行（"花瓣般娇嫩的阴唇"合法）
HARD_RE = ["缝隙", "皱褶", "丘陵", "山谷", "口子", "嫩肉", "领地"]
CTX = ["那处", "那里", "这边", "底下", "下面", "上头", "那一层", "它", "它们"]
TIP = ["快感", "感觉", "刺激", "某种"]

EXPLICIT = [
    "阴唇", "阴蒂", "阴核", "小穴", "穴口", "阴道", "内壁", "子宫", "肛门",
    "乳头", "乳尖", "淫水", "潮吹", "黏液", "精液", "尿道",
    "抽送", "抽出来", "插进去", "送进去", "指入", "舔阴", "含住", "舔到",
]
# 身体动作词：出现时，「它/它们」大概率指部位而非物件
BODY = re.compile(r"(手指|指腹|指尖|食指|中指|无名指|拇指|手掌|掌心|舌头|舌尖|嘴唇|双腿|大腿)")
# 「底下/下面/上头」前面接实物或身体部位时是空间用法，放行
NEAR = r"(被子|床单|床|桌|台|石|太阳|窗|柜|袖|树|伞|山|水|裙|枕|毯|地|冰|帽|纸|画|灯|台阶|脚|手|身|膝盖|指腹|指尖|手指|掌心|手掌|拇指|皮|舌|唇|耳|尾|胯|腰)"
SPATIAL_TAIL = ("底下", "下面", "上头")

def judge(line):
    hard = [w for w in HARD if w in line]
    line_explicit = any(e in line for e in EXPLICIT)
    if not line_explicit:
        hard += [w for w in HARD_RE if w in line]
    explicit = line_explicit or bool(BODY.search(line))
    ctx = []
    for w in CTX:
        if w not in line:
            continue
        if w in SPATIAL_TAIL and re.search(NEAR + r"\s*" + w, line):
            continue
        if explicit:
            ctx.append(w)
    tip = [w for w in TIP if w in line]
    return hard, ctx, tip


def scan(path):
    raw = open(path, encoding="utf-8").read()
    body = re.sub(r"\s", "", raw)
    lines = raw.split("\n")
    bad, tips = [], []
    for no, line in enumerate(lines, 1):
        hard, ctx, tip = judge(line)
        for w in hard:
            bad.append((no, "强禁", w, line.strip()[:70]))
        for w in ctx:
            bad.append((no, "语境", w, line.strip()[:70]))
        if tip and (hard or ctx):
            tips.append(no)
    return bad, tips


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: check_intimacy.py <文件...>")
        sys.exit(2)
    total = 0
    for p in sys.argv[1:]:
        bad, tips = scan(p)
        total += len(bad)
        print(f"== {p}  {'OK' if not bad else str(len(bad)) + ' 处'}")
        for no, kind, w, ctx in bad:
            print(f"  {no:>4} [{kind}] {w} · {ctx}")
        if tips:
            print(f"   提示：第 {','.join(map(str, tips))} 行含概括句信号（快感/感觉/刺激），人工看一眼")
    print(f"\n合计违规 {total} 处")
    sys.exit(1 if total else 0)

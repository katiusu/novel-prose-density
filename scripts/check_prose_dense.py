#!/usr/bin/env python3
"""通用浓稠叙述自查（非 18+ 版，v1.0）。

1. 强禁：句末单字（按 jieba 真实词边界；成词、副词+单字、四字词语放行）。
2. 配额提示：充满 / 如同·仿佛 / 我能清晰地 / 才 / 无谓距离刻度。
3. 密度提示：逗号 2.5–4.5/百字（超出只提示，不阻断）。
4. R18 检测：输出 `R18: yes|no`，供 run_gates.sh 决定要不要叠加露骨层。

用法: check_prose_dense.py <文件...> [--r18-only]
退出码：句末单字命中时 1，否则 0。
"""
import re
import sys

try:                                        # 有 jieba 就按真实词边界判，没有就用白名单兜底
    import io as _io, contextlib as _ctx, warnings as _w
    with _ctx.redirect_stderr(_io.StringIO()), _w.catch_warnings():
        _w.simplefilter("ignore")
        import jieba as _jieba
        _jieba.setLogLevel(60)
        _jieba.initialize()
except Exception:
    _jieba = None

SINGLE_TAIL = set("红橙黄绿青蓝紫黑白灰粉金银棕褐腥膻臊臭香酸甜苦咸淡浓湿潮干燥润滑腻涩黏稠稀薄厚烫凉冷热温寒冰灼痒疼痛麻胀肿木僵硬软紧松挺塌瘪鼓亮暗沉明耀辉胖瘦高矮长短粗细深浅宽窄快慢累乏困倦晕飘轻重漉")
TAIL_WORDS = set("""潮湿 干燥 湿润 干涩 湿滑 湿漉 湿黏 黏滑 黏腻 滑腻 细腻 粗糙 毛糙 光滑 粘稠 黏稠 稠密 稀薄 柔软 绵软 坚硬 僵硬 紧实 绷紧 松垮 松软 绵密 饱满 丰满 鼓胀 肿胀 胀痛 酸痛 酸软 酸胀 钝痛 隐痛 抽痛 麻痒 酥麻 发痒 发酸 发烫 发热 发冷 发白 发黑 发红 发亮 发暗 发麻 发胀 发软 发硬 发紧 发甜 发苦 发涩 发咸 红晕 绯红 通红 潮红 鲜红 嫩红 淡红 浅红 深红 猩红 桃红 粉红 惨白 苍白 煞白 雪白 灰白 乌黑 漆黑 金黄 青紫 淤青 腥气 膻气 骚气 甜腻 苦涩 腥涩 甜津 滚烫 烫手 灼热 炽热 火热 燥热 湿热 温热 微热 微凉 冰凉 寒凉 严寒 酷热 浅淡 深浓 更浓 更淡 更深 更浅 更亮 更暗 更长 更短 更快 更慢 更紧 更松 更硬 更软 更烫 更凉 更干 更湿 沉重 沉甸 轻飘 轻快 迟缓 急迫 眩晕 晕眩 疲倦 困倦 闷热 闷胀 闷痛 潮热 潮润 干爽 干硬 干瘪 湿冷 温凉 凉薄 单薄 轻薄 厚重 浓酽 淡薄 绵长 悠长 漫长 深长 修长 细长 短小 矮小 细小 瘦小 宽厚 窄小 粗壮 细窄 涨红 羞红 燥红 热红 青白 泛白 发青 发紫 发黄 发灰 生疼 抽疼""".split())
TAIL_PREFIX = set("发很挺太更最变显颇极已全都半略微稍比较相当格外愈加")

QUOTA = [
    ("充满-定语模具", r"充满(了)?", 3, 1000),
    ("明喻 如同/仿佛", r"(如同|仿佛)", 1, 300),
    ("感知动词开句", r"我能清晰地", 2, 1000),
    ("才-虚词模具", r"才", 1, 1000),
    ("无谓距离刻度", r"[半一两几]\s*[寸分厘毫尺]", 1, 600),
]
R18_WORDS = ("小穴", "穴口", "阴唇", "阴蒂", "阴道", "内壁", "子宫", "肛门", "乳头", "乳尖",
             "淫水", "精液", "阴茎", "肉棒", "射精", "高潮", "抽送", "插进去", "指入", "潮吹",
             "自慰", "舔阴", "尿道", "铃口")


def endings(body_segments):
    hits = []
    for seg in body_segments:
        seg = seg.strip()
        if not seg or seg[-1] not in SINGLE_TAIL:
            continue
        if len(seg) >= 4 and _jieba is not None and _jieba.dt.FREQ.get(seg[-4:], 0) > 0:
            continue                            # 四字词语整体放行
        if _jieba is not None:
            toks = [t for t in _jieba.lcut(seg) if t.strip()]
            if not toks or len(toks[-1]) != 1:
                continue
            prev = toks[-2] if len(toks) >= 2 else ""
            if prev and (prev + toks[-1]) in TAIL_WORDS:
                continue
            if prev in TAIL_PREFIX:
                continue
        else:
            if len(seg) >= 2 and (seg[-2:] in TAIL_WORDS or seg[-2] in TAIL_PREFIX):
                continue
        hits.append(seg[-1])
    return hits


def scan(path):
    raw = open(path, encoding="utf-8").read()
    body = re.sub(r"\s", "", raw)
    bare = re.sub(r"“[^”]*”", "", raw)          # 台词引号内不查句末单字
    segs = [re.sub(r"[，、；：）”]+$", "", s.strip()) for s in re.split(r"[。！？]", bare)]
    bad = endings(segs)
    quota = []
    n = max(len(body), 1)
    for name, pat, per, window in QUOTA:
        hits = len(re.findall(pat, body))
        allowed = max(per, round(n / window * per))
        if hits > allowed:
            quota.append(f"{name} {hits} 次（{window} 字内上限 {per}，全文 {n} 字允许 {allowed}）")
    commas = raw.count("，")
    density = commas * 100 / n
    r18 = any(w in body for w in R18_WORDS)
    return bad, quota, density, r18, n


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = "--r18-only" in sys.argv
    if not args:
        print("用法: check_prose_dense.py <文件...> [--r18-only]")
        sys.exit(2)
    total = 0
    for p in args:
        bad, quota, density, r18, n = scan(p)
        if only:
            print(f"R18: {'yes' if r18 else 'no'}\t{p}")
            continue
        total += len(bad)
        print(f"== {p}  {'OK' if not bad else str(len(bad)) + ' 处'}")
        for ch in bad:
            print(f"   [强禁] 句末单字:{ch}（换成词语，不改句式）")
        for q in quota:
            print(f"   配额提示：{q}")
        if density > 4.5:
            print(f"   密度提示：逗号 {density:.2f}/百字，超出 2.5–4.5（{n} 字）")
        print(f"   R18: {'yes' if r18 else 'no'}")
    if not only:
        sys.exit(1 if total else 0)

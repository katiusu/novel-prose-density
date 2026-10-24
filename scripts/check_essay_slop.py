#!/usr/bin/env python3
"""作文/现代文套话检测 —— 议论文、说明文、散文里的 AI 腔套语。

为什么单独一层：
  句式模板层查「句子骨架复读」，词表模具层查小说向禁词；
  但作文类 AI 味的最大来源是**篇章套话**——「综上所述」「具有重要意义」「在当今这个……的时代」。
  这类套话句子本身不长也不短，句法模板看不出来，小说禁词表也不收，必须单独列。

词表两档（关键：人类也用「首先/总之」，所以不能出现即判违规）：
  强套  几乎只在套话文里成串出现：综上所述 / 由此可见 / 不可否认 / 在当今…时代 /
        随着…发展 / 具有重要意义 / 发挥重要作用 / 注入动力 / 谱写…篇章 / 时代浪潮 /
        值得我们深思 / 让我们…吧
  弱套  人类也会用，AI 的问题是**密度**：首先/其次/最后 / 总之 / 更重要的是 /
        与此同时 / 不可或缺 / 博大精深

判据（密度为主，绝对数为辅）：
  强套 ≥2 处，或强套密度 > 0.8 处/千字   → 作文套话过多，按替换方向改写
  强套 = 1 处，或弱套密度 > 1.5 处/千字  → 提示
  其余                                    → 干净

实测校准：AI 味议论文 7 处强套 / 371 字 = 18.9 处/千字（判 bad）；
汪曾祺散文 0 处强套 / 11.8 万字 = 0（判干净）——弱套「首先/总之」在人类文本里正常。

用法:
  check_essay_slop.py <文件...> [--json] [--quiet]

退出码：0 永远（advisory 层，不阻断交付）。
"""
import argparse, json, re, sys

STRONG = {
    '篇章强套': [
        r'综上所述', r'总而言之', r'由此可见', r'众所周知', r'毋庸置疑', r'不可否认',
        r'在当今.{0,12}的时代', r'随着.{2,20}的(发展|推进|进步)', r'从.{2,12}的角度(来)?(看|说)',
        r'在.{2,20}的背景下',
    ],
    '空泛褒义': [
        r'具有(重要|重大|深远)意义', r'具有深远影响', r'发挥着?(重要|积极)作用', r'发挥了?(重要|积极)作用',
        r'起到了?积极作用', r'奠定(了)?坚实基础', r'注入(了)?(强大|强劲)?(动力|动能)',
        r'谱写.{0,6}篇章', r'书写.{0,8}(人生|篇章)', r'时代浪潮', r'蓬勃发展', r'日益凸显',
        r'砥砺前行', r'行稳致远', r'大有可为', r'前景广阔', r'日新月异',
    ],
}
WEAK = {
    '过渡弱套': [r'首先[，,]?', r'其次[，,]?', r'再次[，,]?', r'最后[，,]', r'总之[，,]',
                 r'更重要的是', r'更为关键的是', r'与此同时', r'不仅如此', r'换句话说', r'换言之'],
    '常见褒词': [r'不可或缺', r'博大精深', r'源远流长', r'历久弥新', r'薪火相传', r'任重道远', r'内生动力'],
}
ADVICE = {
    '篇章强套': '删掉总结语和时代背景铺垫，直接把观点或事实摆出来；段落之间用内容承接',
    '空泛褒义': '把评价换成可验证的事实或具体后果（谁受益、变了多少、哪一步起作用）',
    '过渡弱套': '过渡词一多就是套话；保留一两个，其余改成内容衔接',
    '常见褒词': '这些词人类也用，但一段里出现两次就腻；换成具体的景象或动作',
}


def scan(text):
    hits = []
    for cat, pats in list(STRONG.items()) + list(WEAK.items()):
        for p in pats:
            for m in re.finditer(p, text):
                s0 = max(0, m.start() - 12)
                ctx = text[s0:m.end() + 18].replace('\n', ' ')
                hits.append({'cat': cat, 'match': m.group(0), 'pos': m.start(), 'ctx': ctx,
                             'strong': cat in STRONG})
    hits.sort(key=lambda h: h['pos'])
    return hits


def main():
    ap = argparse.ArgumentParser(description='作文/现代文套话检测')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    out = {'files': []}
    for path in a.files:
        try:
            text = open(path, encoding='utf-8').read()
        except OSError as e:
            print('skip %s: %s' % (path, e), file=sys.stderr)
            continue
        hits = scan(text)
        hanzi = len(re.findall(r'[\u4e00-\u9fff]', text))
        strong = [h for h in hits if h['strong']]
        weak = [h for h in hits if not h['strong']]
        k = max(hanzi / 1000.0, 0.15)
        if len(strong) / k > 0.8:
            level = 'bad'
        elif len(strong) / k > 0.3 or len(weak) / k > 1.5:
            level = 'mild'
        else:
            level = 'ok'
        by_cat = {}
        for h in hits:
            by_cat[h['cat']] = by_cat.get(h['cat'], 0) + 1
        out['files'].append({'file': path, 'hanzi': hanzi, 'hits': hits, 'strong': len(strong),
                             'weak': len(weak), 'by_cat': by_cat, 'level': level,
                             'strong_per_k': round(len(strong) / k, 2)})

        if not a.json and not a.quiet:
            verdict = {'ok': '干净', 'mild': '提示', 'bad': '作文套话过多'}[level]
            print('[作文套话] %s：%s（强套 %d 处 = %.1f 处/千字，弱套 %d 处）'
                  % (path, verdict, len(strong), len(strong) / k, len(weak)))
            for h in hits[:12]:
                print('  %s%-16s %-10s %s' % ('!' if h['strong'] else ' ', h['cat'], h['match'], h['ctx'][:52]))
            for cat in by_cat:
                print('  改法·%s：%s' % (cat, ADVICE.get(cat, '换具体说法')))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())

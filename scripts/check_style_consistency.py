#!/usr/bin/env python3
"""文风一致性检测 —— 本章与同项目基线（前文章节）的风格偏离度。

为什么需要这一层：
  句式模板层（check_syntax_tpl.py）判的是「这一章像不像模板化文本」，看的是绝对水平；
  但写作里更常见的问题是**漂移**：同一本书第 3 章和第 30 章读起来不像一个人写的。
  漂移在绝对值上可能完全正常，只有跟自己的前文比才看得出来。

度量（每项都在基线的每个文件上算一遍，得到基线分布）：
  句长        汉字/句
  句长CV      句长标准差 ÷ 句长均值（节奏起伏）
  短句占比     ≤12 汉字的句子比例
  逗号密度     逗号数 / 百汉字
  段长        汉字/段
  对话占比     引号内汉字 / 全部汉字
  模板覆盖     目标句 5-gram 落在基线高频模板集（top 20%）里的比例，均值

判据（稳健 z：0.6745 × (x − 中位数) ÷ MAD）：
  |z| ≤ 2    一致
  2 < |z| ≤ 3   轻微漂移（提示，不阻断）
  |z| > 3    明显漂移（advisory 标红）
  整体：漂移项 ≥3 或任一 |z|>5 → 【明显漂移】

用法:
  check_style_consistency.py <目标文件> [--ref 文件/目录 ...] [--json] [--quiet]
  缺省基线 = 目标文件同目录下的其他 .md/.txt（排除目标自身）。

退出码：0 永远（advisory 层，不阻断交付）。
"""
import argparse, json, os, re, sys

try:
    import jieba, jieba.posseg as pseg
    jieba.setLogLevel(60)
    _HAS = True
except Exception:
    _HAS = False

M = {'n': 'N', 'nr': 'N', 'ns': 'N', 'nt': 'N', 'nz': 'N', 'ng': 'N', 'vn': 'N', 'an': 'N',
     'v': 'V', 'vd': 'V', 'vg': 'V', 'a': 'A', 'ad': 'A', 'ag': 'A',
     'd': 'D', 'df': 'D', 'u': 'U', 'uj': 'U', 'ul': 'U', 'uv': 'U', 'uz': 'U', 'ud': 'U', 'ug': 'U', 'ui': 'U',
     'p': 'P', 'c': 'C', 'r': 'R', 'rr': 'R', 'rz': 'R', 'm': 'M', 'q': 'Q', 't': 'T', 'f': 'F',
     's': 'S', 'b': 'B', 'z': 'Z', 'i': 'I', 'l': 'I'}
DROP = set('w x') | set('，、；：。！？…—')
TOP_PCT = 0.2
NGRAM = 5
HAN = re.compile(r'[\u4e00-\u9fff]')
QUOTE = re.compile(r'[“"「『](.*?)[”"」』]', re.S)

METRICS = [
    ('sent_len', '句长', '汉字/句'),
    ('sent_len_cv', '句长CV', '句长标准差÷均值'),
    ('short_sent', '短句占比', '≤12 汉字的句子比例'),
    ('comma_density', '逗号密度', '逗号/百汉字'),
    ('para_len', '段长', '汉字/段'),
    ('dialogue', '对话占比', '引号内汉字/全部汉字'),
    ('tpl_cov', '模板覆盖', '落在基线高频模板集里的 5-gram 比例'),
]


def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def split_sents(text):
    return [s.strip() for s in re.split(r'[。！？\n]+', text) if s.strip()]


def han_count(s):
    return len(HAN.findall(s))


def pos_seq(sent):
    return [M.get(f, 'X') for w, f in pseg.cut(sent)
            if w.strip() and f not in DROP and w not in '，、；：。！？']


def grams_of(sent):
    seq = pos_seq(sent)
    return [''.join(seq[i:i + NGRAM]) for i in range(len(seq) - NGRAM + 1)]


def raw_metrics(text):
    """与基线无关的六项（模板覆盖要基线，单独算）。"""
    sents = split_sents(text)
    lens = [han_count(s) for s in sents] or [0]
    total_han = sum(lens)
    total_chars = sum(len(s) for s in sents)
    paras = [p for p in text.split('\n') if p.strip()]
    comma = text.count('，') + text.count(',')
    dlg = sum(han_count(m) for m in QUOTE.findall(text))
    mean_len = total_han / max(1, len(sents))
    var = sum((x - mean_len) ** 2 for x in lens) / max(1, len(lens))
    return {
        'sent_len': round(mean_len, 2),
        'sent_len_cv': round((var ** 0.5) / mean_len, 3) if mean_len else 0.0,
        'short_sent': round(sum(1 for x in lens if 0 < x <= 12) / max(1, len(sents)), 3),
        'comma_density': round(comma / max(1, total_han) * 100, 2),
        'para_len': round(total_han / max(1, len(paras)), 1),
        'dialogue': round(dlg / max(1, total_han), 3),
    }


def build_tpl_set(texts):
    allg = []
    for t in texts:
        for s in split_sents(t):
            allg.extend(grams_of(s))
    if not allg:
        return set()
    freq = {}
    for g in allg:
        freq[g] = freq.get(g, 0) + 1
    top = sorted(freq.items(), key=lambda kv: -kv[1])[:max(1, int(len(freq) * TOP_PCT))]
    return {k for k, _ in top}


def tpl_cov(text, tpl_set):
    sents = split_sents(text)
    vals = []
    for s in sents:
        gs = grams_of(s)
        if gs:
            vals.append(sum(1 for g in gs if g in tpl_set) / len(gs))
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def mad(xs, med):
    return median([abs(x - med) for x in xs]) if xs else 0.0


def zscore(x, med, m):
    if m <= 1e-9:
        return 0.0 if abs(x - med) <= 1e-9 else 9.99
    return 0.6745 * (x - med) / m


def main():
    ap = argparse.ArgumentParser(description='文风一致性检测（本章 vs 前文基线）')
    ap.add_argument('file', help='目标文件（本章正文）')
    ap.add_argument('--ref', action='append', nargs='+', default=None,
                    help='基线文件或目录，可一次给多个路径、也可重复写；缺省用目标同目录下其他 .md/.txt')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    if not _HAS:
        print('[文风一致性] jieba 未安装，跳过（pip install jieba）')
        return 0
    if not os.path.isfile(a.file):
        print('no such file: ' + a.file, file=sys.stderr)
        return 2

    target = os.path.abspath(a.file)
    refs = []
    if a.ref:
        flat = [x for group in a.ref for x in group]
        for r in flat:
            if os.path.isdir(r):
                refs.extend(os.path.join(r, f) for f in sorted(os.listdir(r))
                            if f.endswith(('.md', '.txt')))
            elif os.path.isfile(r):
                refs.append(r)
    else:
        d = os.path.dirname(target)
        refs = [os.path.join(d, f) for f in sorted(os.listdir(d))
                if f.endswith(('.md', '.txt')) and os.path.abspath(os.path.join(d, f)) != target]
    refs = [r for r in refs if os.path.abspath(r) != target]
    if not refs:
        print('[文风一致性] 没有基线文件（同目录下需要其他章节），跳过')
        return 0

    tgt_text = load(target)
    ref_texts = [(os.path.basename(r), load(r)) for r in refs]
    tpl_set = build_tpl_set([t for _, t in ref_texts])

    tgt = raw_metrics(tgt_text)
    tgt['tpl_cov'] = tpl_cov(tgt_text, tpl_set)

    base = {}
    for _, t in ref_texts:
        m = raw_metrics(t)
        m['tpl_cov'] = tpl_cov(t, tpl_set)
        for k in m:
            base.setdefault(k, []).append(m[k])

    rows, drifted, severe = [], [], []
    for key, label, desc in METRICS:
        xs = base[key]
        med = median(xs)
        m = mad(xs, med)
        # MAD 下限：同一本书相邻章节常常高度一致，MAD≈0 会让 z 爆炸成假警报
        m = max(m, 0.12 * abs(med), 1e-6)
        z = zscore(tgt[key], med, m)
        if key == 'tpl_cov':
            # 模板覆盖对剧情变化敏感（换场景换人物，模板组合自然换），用相对差不看 z
            diff = abs(tgt[key] - med) / max(abs(med), 1e-6)
            level = 'ok' if diff <= 0.35 else ('mild' if diff <= 0.6 else 'bad')
        else:
            level = 'ok' if abs(z) <= 2 else ('mild' if abs(z) <= 3 else 'bad')
        rows.append({'key': key, 'label': label, 'desc': desc, 'target': tgt[key],
                     'base_med': round(med, 3), 'base_mad': round(m, 3), 'z': round(z, 2), 'level': level})
        if level == 'bad':
            drifted.append(label)
        elif level == 'mild':
            drifted.append(label + '(轻)')
        if abs(z) > 5 and key != 'tpl_cov':
            severe.append(label)

    verdict = '一致'
    if drifted:
        verdict = '轻微漂移' if len(drifted) <= 2 and not severe else '明显漂移'

    if a.json:
        print(json.dumps({'file': target, 'refs': [os.path.basename(r) for r in refs],
                          'verdict': verdict, 'drifted': drifted, 'metrics': rows},
                         ensure_ascii=False, indent=1))
        return 0

    if not a.quiet:
        print('[文风一致性] %s vs 基线 %d 篇：%s' % (os.path.basename(target), len(refs), verdict))
        print('  %-10s %8s %10s %10s %6s' % ('指标', '本章', '基线中位', 'MAD', 'z'))
        for r in rows:
            mark = {'ok': '  ', 'mild': '⚠ ', 'bad': '✗ '}[r['level']]
            print('  %s%-8s %8.2f %10.2f %10.2f %+6.1f  %s'
                  % (mark, r['label'], r['target'], r['base_med'], r['base_mad'], r['z'], r['desc']))
        if drifted:
            print('  漂移项：' + '、'.join(drifted))
            print('  改法：先看漂移项是方向性问题（句长变短/对话变多）还是密度性问题（逗号、短句），'
                  '按本章要讲的情节定主次，不要为拉平指标改掉该有的节奏。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""句式模板检测：POS 5-gram 自基线浓度（对应论文 2407.00211 的句法模板重复度）。

判据（句级浓度）：
  把每个句子转成粗词性序列（12 类），取 5-gram；
  本文件/本项目中出现频次最高的 top 20% 模板记作「高频模板」；
  句级浓度 = 该句 5-gram 落在高频模板中的比例。
  >=0.5 强提示（复读句），0.3-0.5 弱提示，<0.3 正常。

n 的选择有实测依据（人类 20 句 vs 模板化 20 句，Δ浓度）：
  n=3 +0.09 / n=4 +0.17 / n=5 +0.21 / n=6 +0.18 / n=7 +0.10  → 默认 n=5。

用法:
  check_syntax_tpl.py <文件...> [--baseline 目录或文件] [--json] [--n 5] [--quiet]

baseline：可选的其他文本（如同一项目的其他章节）。默认每文件自基线。
退出码：0 永远（advisory 层，不阻断）。
"""
import argparse, collections, json, os, re, sys

try:
    import jieba.posseg as pseg
    import jieba
    jieba.setLogLevel(60)
    _HAS = True
except Exception:
    _HAS = False

# jieba 词性 → 12 类粗标签（与实验口径一致，勿随意改）
M = {'n': 'N', 'nr': 'N', 'ns': 'N', 'nt': 'N', 'nz': 'N', 'ng': 'N', 'vn': 'N', 'an': 'N',
     'v': 'V', 'vd': 'V', 'vg': 'V', 'a': 'A', 'ad': 'A', 'ag': 'A',
     'd': 'D', 'df': 'D', 'u': 'U', 'uj': 'U', 'ul': 'U', 'uv': 'U', 'uz': 'U', 'ud': 'U', 'ug': 'U', 'ui': 'U',
     'p': 'P', 'c': 'C', 'r': 'R', 'rr': 'R', 'rz': 'R', 'm': 'M', 'q': 'Q', 't': 'T', 'f': 'F',
     's': 'S', 'b': 'B', 'z': 'Z', 'i': 'I', 'l': 'I'}
DROP = set('w x') | set('，、；：。！？…—')
TOP_PCT = 0.2


def split_sents(text):
    return [s.strip() for s in re.split(r'[。！？\n]+', text) if s.strip()]


def pos_seq(sent):
    return [M.get(f, 'X') for w, f in pseg.cut(sent)
            if w.strip() and f not in DROP and w not in '，、；：。！？']


def ngrams(seq, n):
    return [''.join(seq[i:i + n]) for i in range(len(seq) - n + 1)]


def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--baseline', default=None, help='额外基线文本（文件或目录），默认每文件自基线')
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    if not _HAS:
        print('[syntax_tpl] 未安装 jieba，跳过（pip install jieba）')
        return 0

    base_text = None
    if a.baseline:
        if os.path.isdir(a.baseline):
            parts = [load(os.path.join(a.baseline, f)) for f in sorted(os.listdir(a.baseline)) if f.endswith(('.md', '.txt'))]
            base_text = '\n'.join(parts)
        else:
            base_text = load(a.baseline)

    report = {'n': a.n, 'top_pct': TOP_PCT, 'files': []}
    for path in a.files:
        sents = split_sents(load(path))
        seqs = [pos_seq(s) for s in sents]
        rows = [ngrams(sq, a.n) for sq in seqs]
        # 基线：优先外部基线，否则合并本文件全部句子
        if base_text is not None:
            bsegs = [ngrams(pos_seq(s), a.n) for s in split_sents(base_text)]
        else:
            bsegs = rows
        allg = [g for r in bsegs for g in r]
        cnt = collections.Counter(allg)
        if not cnt:
            continue
        k = max(1, int(len(cnt) * TOP_PCT))
        topK = {t for t, _ in cnt.most_common(k)}
        ratios = [sum(1 for x in r if x in topK) / len(r) if r else 0.0 for r in rows]
        strong = [i for i, r in enumerate(ratios) if r >= 0.5]
        weak = [i for i, r in enumerate(ratios) if 0.3 <= r < 0.5]
        mean = sum(ratios) / len(ratios) if ratios else 0.0
        probs = [v / len(allg) for v in collections.Counter(allg).values()]
        import math
        H = -sum(p * math.log(p, 2) for p in probs) / math.log(len(cnt), 2) if len(cnt) > 1 else 0.0
        cov = sum(v for t, v in collections.Counter(allg).items() if t in topK) / len(allg)

        entry = {'file': path, 'sentences': len(sents), 'templates': len(cnt),
                 'dtr': round(len(cnt) / len(sents), 2), 'cov': round(cov, 2), 'H': round(H, 2),
                 'mean_conc': round(mean, 3), 'strong': len(strong), 'weak': len(weak),
                 'notes': [{'idx': i + 1, 'conc': round(ratios[i], 2), 'sent': sents[i][:40],
                            'tpl': [t for t in rows[i] if t in topK][:3]} for i in strong]}
        report['files'].append(entry)

        if not a.quiet:
            print(f"\n[句式模板] {path}")
            print(f"  句={len(sents)} 模板={len(cnt)} DTR={entry['dtr']} COV={entry['cov']} H={entry['H']} 句级浓度均值={entry['mean_conc']}")
            print(f"  强提示(>=0.5)={len(strong)}/{len(sents)}  弱提示(0.3-0.5)={len(weak)}")
            for n_ in entry['notes']:
                print(f"    句{n_['idx']:>2} 浓度{n_['conc']:.2f} {n_['sent']}")
                print(f"        高频模板: {', '.join(n_['tpl'])}")
            if len(strong) / max(1, len(sents)) >= 0.3:
                print("  提示：复读句占比偏高（>=30%），可对强提示句换句式骨架（主谓→主谓补/状语前置），不必整段重写。")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

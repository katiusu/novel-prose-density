#!/usr/bin/env python3
"""句式模板检测 v2.0 —— 依据 arXiv 2407.00211 的句法模板方法（本地落地版）。

论文口径的四个指标（全部输出）：
  N    不同模板数（每个句子取 POS 5-gram 模板）
  DTR  = N / 句数，不同模板率，越高说明越少重复
  COV  = 高频模板（top 20%）占全部 n-gram 的比例，越高越模板化
  H    = 模板分布熵，越低越集中
  CDR  = 本章去重模板中能在人类基线里找到的比例（论文「交叉文档复用」的本地近似）

判据（句级浓度）：
  某句 5-gram 落在高频模板中的比例。>=0.5 强提示（复读句），0.3-0.5 弱提示。

n 实测（人类 20 句 vs 模板化 20 句，Δ浓度）：
  n=3 +0.09 / n=4 +0.17 / n=5 +0.21 / n=6 +0.18 / n=7 +0.10 → 默认 5。

用法:
  check_syntax_tpl.py <文件...> [--baseline 文件或目录] [--n 5] [--json] [--quiet]
  --baseline 缺省指向本报仓库 corpus/human_baseline.md（人类基线）。

退出码：0 永远（advisory 层，不阻断交付）。
"""
import argparse, collections, json, math, os, re, sys

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
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE = os.path.normpath(os.path.join(HERE, '..', 'corpus', 'human_baseline.md'))


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


def read_baseline(path):
    if not path:
        return None, 'none'
    if os.path.isdir(path):
        parts = [load(os.path.join(path, f)) for f in sorted(os.listdir(path))
                 if f.endswith(('.md', '.txt'))]
        return '\n'.join(parts), path
    if os.path.exists(path):
        return load(path), path
    return None, 'missing'


def advice(tpls, n):
    """按命中模板的形态给改写建议（不是硬规则，是改写入口）。"""
    out = []
    if not tpls:
        return out
    firsts = {t[0] for t in tpls}
    if 'R' in firsts:
        out.append('句首代词开场：删代词，直接上施动者或动作')
    if any(t.count('U') >= 2 for t in tpls):
        out.append('助词链过密：拆句或删「的/地/得」')
    if firsts & {'A', 'D'}:
        out.append('句首形容词/副词先落地：删修饰，让动词先出现')
    if any('AV' in t for t in tpls):
        out.append('抽象形容词+动词：换具体动作或实体')
    if any(t.count('N') >= 3 for t in tpls):
        out.append('名词块堆叠：改成「施动者+动词+对象」')
    return out[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--baseline', default=None,
                    help='基线文本（文件或目录）；缺省用 corpus/human_baseline.md，传 none 关闭 CDR')
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    if not _HAS:
        print('[syntax_tpl] 未安装 jieba，跳过（pip install jieba）')
        return 0

    bpath = a.baseline
    if bpath is None:
        bpath = DEFAULT_BASELINE
    base_text, base_src = read_baseline(bpath)
    if a.baseline == 'none':
        base_text, base_src = None, 'none'

    base_tpls = set()
    if base_text:
        for s in split_sents(base_text):
            base_tpls.update(ngrams(pos_seq(s), a.n))

    report = {'n': a.n, 'top_pct': TOP_PCT, 'baseline': base_src, 'files': []}
    for path in a.files:
        sents = split_sents(load(path))
        rows = [ngrams(pos_seq(s), a.n) for s in sents]
        allg = [g for r in rows for g in r]
        cnt = collections.Counter(allg)
        if not cnt:
            continue
        k = max(1, int(len(cnt) * TOP_PCT))
        topK = {t for t, _ in cnt.most_common(k)}
        ratios = [sum(1 for x in r if x in topK) / len(r) if r else 0.0 for r in rows]
        probs = [v / len(allg) for v in cnt.values()]
        H = -sum(p * math.log(p, 2) for p in probs) / math.log(len(cnt), 2) if len(cnt) > 1 else 0.0
        cov = sum(v for t, v in cnt.items() if t in topK) / len(allg)
        cdr = (len(set(allg) & base_tpls) / len(set(allg))) if base_tpls else None

        strong = [i for i, r in enumerate(ratios) if r >= 0.5]
        weak = [i for i, r in enumerate(ratios) if 0.3 <= r < 0.5]
        mean = sum(ratios) / len(ratios) if ratios else 0.0

        entry = {
            'file': path, 'sentences': len(sents), 'templates': len(cnt),
            'dtr': round(len(cnt) / len(sents), 2), 'cov': round(cov, 2), 'H': round(H, 2),
            'cdr': None if cdr is None else round(cdr, 2),
            'mean_conc': round(mean, 3), 'strong': len(strong), 'weak': len(weak),
            'notes': [{'idx': i + 1, 'conc': round(ratios[i], 2), 'sent': sents[i][:40],
                       'tpl': [t for t in rows[i] if t in topK][:3],
                       'advice': advice([t for t in rows[i] if t in topK], a.n)} for i in strong],
        }
        report['files'].append(entry)

        if not a.quiet:
            print(f"\n[句式模板] {path}")
            cdr_s = f" CDR={entry['cdr']}" if entry['cdr'] is not None else ""
            print(f"  句={len(sents)} 模板={len(cnt)} DTR={entry['dtr']} COV={entry['cov']} H={entry['H']}{cdr_s}")
            print(f"  句级浓度均值={entry['mean_conc']}  强提示(>=0.5)={len(strong)}/{len(sents)}  弱提示(0.3-0.5)={len(weak)}")
            for n_ in entry['notes']:
                print(f"    句{n_['idx']:>2} 浓度{n_['conc']:.2f} {n_['sent']}")
                print(f"        高频模板: {', '.join(n_['tpl'])}")
                if n_['advice']:
                    print(f"        修法: {'；'.join(n_['advice'])}")
            if len(strong) / max(1, len(sents)) >= 0.3:
                print("  提示：复读句占比 >=30%。只对强提示句换骨架（主谓→主谓补／状语前置／拆两句），不要整段重写。")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

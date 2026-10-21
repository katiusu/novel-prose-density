#!/usr/bin/env python3
"""English AI-slop gate — implements the stop-slop rule set (hardikpandya/stop-slop, MIT).

This is an independent implementation of the checklist, not a copy of upstream code.
It reports findings only; it never rewrites text.

Layers
  blocking : em/en dash, "not X, but Y", throat-clearing openers, meta-joiners,
             vague declaratives, emphasis crutches
  advisory : -ly adverbs, passive voice, three-item lists, Wh- sentence openers,
             paragraph-final punchline, nominalisation

Exit: 0 = clean, 1 = blocking finding, 2 = usage error.
"""
import re
import sys

BLOCKING = "blocking"
ADVISORY = "advisory"

EM_DASH = re.compile(r"[—–]")
NOT_X_BUT_Y = re.compile(
    r"\bnot\s+(?:just|only|merely|simply)?\s*[^,.;]{2,60}?,\s*(?:but|it'?s|it is|rather)\b",
    re.I,
)
THROAT = re.compile(
    r"\b(?:here'?s (?:what|the thing|how)|it'?s (?:important|worth) (?:to note|noting)|"
    r"needless to say|in today'?s \w+|let'?s dive (?:in|into)|it goes without saying)\b",
    re.I,
)
META = re.compile(
    r"\b(?:in this (?:essay|article|post|section|chapter)|the rest of this|"
    r"as (?:we'?ll|we will) see|as mentioned (?:above|earlier)|to sum up|in conclusion)\b",
    re.I,
)
VAGUE = re.compile(
    r"\b(?:the (?:reasons|implications|stakes|consequences) (?:are|is) \w+|"
    r"there are (?:several|many|a number of) (?:factors|reasons|ways)|"
    r"this (?:is|was) (?:significant|important|crucial)|"
    r"a (?:wide|broad) range of)\b",
    re.I,
)
EMPHASIS = re.compile(
    r"\b(?:very|really|quite|extremely|incredibly|absolutely|truly|utterly|"
    r"remarkably|genuinely|literally)\b",
    re.I,
)
ADVERB = re.compile(r"\b([A-Za-z]{4,}ly)\b")
ADVERB_OK = {
    "only", "early", "daily", "weekly", "monthly", "yearly", "family", "reply",
    "apply", "supply", "rely", "holy", "silly", "lively", "lovely", "friendly",
    "likely", "unlikely", "quality", "reality", "italy", "july", "assembly",
    "anomaly", "melancholy", "ally", "rally", "belly", "jelly", "fly", "fully",
}
PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|am)\s+(?:\w+(?:ed|en)|shown|given|taken|"
    r"made|done|known|seen|held|built|sent|told|found|kept|left|brought|thought|"
    r"written|driven|gone|come|run)\b",
    re.I,
)
THREE_ITEM = re.compile(
    r"\b([A-Za-z][\w'-]+),\s+([A-Za-z][\w'-]+),?\s+and\s+([A-Za-z][\w'-]+)\b"
)
WH_OPEN = re.compile(
    r"(?:^|(?<=[.!?]\s))(?:\"')?(What|Why|How|When|Where|Who|Whom|Whose|Which)\b"
)
NOMINAL = re.compile(
    r"\b(?:the (?:implementation|utilisation|utilization|optimisation|optimization|"
    r"facilitation|realisation|realization) of)\b",
    re.I,
)


def strip_code(text: str) -> str:
    """Blank out fenced code and inline code so prose rules never fire on them."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"`[^`\n]*`", " ", text)


def sentences(text: str):
    for line_no, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"[^.!?\n]+[.!?]?", line):
            s = m.group(0).strip()
            if s:
                yield line_no, m.start() + 1, s


def find(pattern, text, kind, label, note, hits, limit=400):
    for m in pattern.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
        hits.append((kind, label, line, col, m.group(0).strip()[:60], note))
        if len(hits) > limit:
            return


def paragraph_punchlines(text):
    """段落最后一句很短（<=7 词）且自带收尾腔 => 提示。"""
    out = []
    for para in re.split(r"\n\s*\n", text):
        sents = [s for s in re.split(r"(?<=[.!?])\s+", para.strip()) if s.strip()]
        if len(sents) >= 2:
            last = sents[-1]
            if len(last.split()) <= 7 and not last.endswith('"'):
                out.append(last.strip()[:60])
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        print(f"[usage] cannot read {path}: {exc}")
        return 2

    text = strip_code(raw)
    hits = []
    find(EM_DASH, text, BLOCKING, "em-dash", "delete it, use a comma or a full stop", hits)
    find(NOT_X_BUT_Y, text, BLOCKING, "not-X-but-Y", "state Y directly", hits)
    find(THROAT, text, BLOCKING, "throat-clearing", "cut to the point", hits)
    find(META, text, BLOCKING, "meta-joiner", "delete, let the text move", hits)
    find(VAGUE, text, BLOCKING, "vague-declarative", "name the specific thing", hits)
    find(EMPHASIS, text, BLOCKING, "emphasis-crutch", "cut the intensifier", hits)

    for m in ADVERB.finditer(text):
        if m.group(1).lower() in ADVERB_OK:
            continue
        line = text.count("\n", 0, m.start()) + 1
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
        hits.append((ADVISORY, "-ly adverb", line, col, m.group(1), "replace with a fact"))
    find(PASSIVE, text, ADVISORY, "passive voice", "find the actor, make them the subject", hits)
    find(THREE_ITEM, text, ADVISORY, "three-item list", "two items beat three", hits)
    find(NOMINAL, text, ADVISORY, "nominalisation", "use the verb", hits)

    for line_no, col, s in sentences(text):
        m = WH_OPEN.match(s)
        if m:
            hits.append((ADVISORY, "Wh- opener", line_no, col, s[:50], "restructure the sentence"))
    for last in paragraph_punchlines(text):
        hits.append((ADVISORY, "paragraph punchline", 0, 0, last, "vary the ending"))

    blocking = [h for h in hits if h[0] == BLOCKING]
    advisory = [h for h in hits if h[0] == ADVISORY]

    print(f"=== stop-slop (EN) :: {path} ===")
    print(f"words={len(text.split())}  blocking={len(blocking)}  advisory={len(advisory)}")
    for kind, label, line, col, frag, note in hits[:40]:
        where = f"{line}:{col}" if line else "-"
        print(f"{path}:{where}: [{kind}] {label}: {frag!r} -> {note}")
    if len(hits) > 40:
        print(f"... {len(hits) - 40} more")
    if blocking:
        print(f"VERDICT: FAIL ({len(blocking)} blocking)")
        return 1
    print("VERDICT: PASS" + (" (advisory only)" if advisory else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

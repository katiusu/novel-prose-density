#!/usr/bin/env bash
# 写后门禁包装：跑 run_gates，落一条 receipt，末行输出单行回执。
#   postwrite.sh <正文文件> [--essay] [--intimacy] [--zhuque] [--quiet]
#   --essay：作文/议论文/说明文模式，跳过网文专属三闸
# 回执默认写到 $DESLOP_LOG（缺省 ~/.deslop-receipts.log）。
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FILE="${1:?用法: postwrite.sh <正文文件> [--essay] [--intimacy] [--zhuque]}"
shift || true
OUT=$("$HERE/run_gates.sh" "$FILE" "$@" 2>&1); RC=$?
STAMP=$(date '+%F %T')
LOG="${DESLOP_LOG:-$HOME/.deslop-receipts.log}"
printf '%s\t%s\trc=%s\n' "$STAMP" "$FILE" "$RC" >> "$LOG"
printf '%s\n' "$OUT"
V=$(printf '%s\n' "$OUT" | grep -E 'VERDICT' | sed 's/\x1b\[[0-9;]*m//g' | head -1)
echo "RECEIPT: $(basename "$FILE") rc=$RC ${V} @ $STAMP"
exit $RC

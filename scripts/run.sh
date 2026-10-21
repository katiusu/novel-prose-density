#!/usr/bin/env bash
# 文风门禁：先跑通用层；正文命中 R18 词表时自动追加用词层。
#   run.sh <文件> [--intimacy] [--quiet]
# 退出码：0 通过 / 1 有强禁 / 2 用法错误
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY=python3
FILE=""; FORCE=0
for a in "$@"; do
  case "$a" in
    --intimacy|--erotica) FORCE=1 ;;
    -* ) ;;
    *) FILE="$a" ;;
  esac
done
[ -z "$FILE" ] && { echo "usage: $0 <file> [--intimacy]" >&2; exit 2; }
[ -f "$FILE" ] || { echo "no such file: $FILE" >&2; exit 2; }

out=$("$PY" "$DIR/check_prose_dense.py" "$FILE" 2>&1); rc1=$?
r18=$(printf '%s\n' "$out" | grep -oE 'R18: (yes|no)' | head -1 | awk '{print $2}')
printf '%s\n' "$out"
if [ "$FORCE" -eq 1 ] || [ "$r18" = yes ]; then
  out2=$("$PY" "$DIR/check_intimacy.py" "$FILE" 2>&1); rc2=$?
  printf '%s\n' "$out2"
  [ $rc2 -ne 0 ] && rc1=1
fi
[ $rc1 -eq 0 ] && echo "VERDICT: PASS" || echo "VERDICT: FAIL"
exit $rc1

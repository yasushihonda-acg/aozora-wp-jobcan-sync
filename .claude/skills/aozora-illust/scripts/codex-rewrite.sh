#!/usr/bin/env bash
# codex-rewrite.sh — SCENE 文字列を Codex (GPT-5.5) で ChatGPT UI 風に rewrite
# usage:
#   codex-rewrite.sh "<原文 SCENE>"
# 標準出力: 最適化済 SCENE 文字列 (1 行以上)
# エラー時: stderr にメッセージ出力、exit 非 0
set -u

if [ $# -lt 1 ]; then
  echo "ERROR: SCENE 文字列を引数で渡してください" >&2
  echo "usage: codex-rewrite.sh \"<scene>\"" >&2
  exit 2
fi

INPUT_SCENE="$1"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$SKILL_DIR/prompts/codex-rewrite-template.txt"

[ -f "$TEMPLATE" ] || { echo "ERROR: template missing: $TEMPLATE" >&2; exit 3; }
command -v codex >/dev/null 2>&1 || { echo "ERROR: codex CLI not installed" >&2; exit 4; }

# テンプレートに INPUT_SCENE を埋め込み (sed の区切り衝突回避で python を使う)
PROMPT=$(python3 -c '
import sys
template = open(sys.argv[1]).read()
scene = sys.argv[2]
print(template.replace("__INPUT_SCENE__", scene))
' "$TEMPLATE" "$INPUT_SCENE")

# Codex 呼出 (sandbox=read-only, effort=high)
RAW=$(codex exec --sandbox read-only --strict-config -c model_reasoning_effort=high --cd . "$PROMPT" 2>&1)
EXIT=$?

if [ $EXIT -ne 0 ]; then
  echo "ERROR: codex exec failed (exit=$EXIT)" >&2
  echo "$RAW" | tail -30 >&2
  exit 5
fi

# marker 間を抽出 (最後の出現を取る — codex 出力には prompt echo が含まれるため)
EXTRACTED=$(echo "$RAW" | awk '
  /<<<CODEX_SCENE_START>>>/ { capturing=1; buf=""; next }
  /<<<CODEX_SCENE_END>>>/   { if (capturing) { last=buf; capturing=0 } }
  capturing                 { buf = buf (length(buf) ? "\n" : "") $0 }
  END { print last }
')

if [ -z "$EXTRACTED" ]; then
  echo "ERROR: marker '<<<CODEX_SCENE_START>>> ... <<<CODEX_SCENE_END>>>' が見つかりません" >&2
  echo "--- codex raw output (last 50 lines) ---" >&2
  echo "$RAW" | tail -50 >&2
  exit 6
fi

# テンプレート例文 (記号 __INPUT_SCENE__ 等) が混入していたら警告
if echo "$EXTRACTED" | grep -q "__INPUT_SCENE__"; then
  echo "WARN: placeholder text remained in extracted SCENE" >&2
fi

printf '%s\n' "$EXTRACTED"

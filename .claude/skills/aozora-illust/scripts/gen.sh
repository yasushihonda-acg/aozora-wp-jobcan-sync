#!/usr/bin/env bash
# aozora-illust: メインキャラ厳密再現で画像生成
# usage:
#   gen.sh --mode=single --category=<key> --scene="<英語シーン記述>" [--outfit="<override>"] [--ref-mode=both|face-only] [--codex-rewrite=on|off]
#   gen.sh --mode=sheet [--scene="<6 パネル指定>"] [--ref-mode=both|face-only] [--codex-rewrite=on|off]
#
# --ref-mode:
#   both (default) — baseline (full scene) + close-up を両方 reference に渡す。
#                    キャラ同一性は最強だが、reference の構図 (タブレット相談等) を強く継承する。
#   face-only      — close-up (顔のみ) だけを渡す。構図は prompt のシーン記述で自由制御可。
#                    職種別シーン差別化が必要なときに使う (実証 2026-06-30)。
#
# --codex-rewrite:
#   on (default)  — SCENE 文字列を Codex (GPT-5.5) で ChatGPT UI 風に rewrite してから生成。
#                   ChatGPT UI 並のクオリティが得られる (実証 2026-06-30、PR #43)。
#                   コスト: Codex 1 call (~10s, ~¢ オーダー) + 通常の画像生成。
#   off           — Claude (呼出元) が書いた SCENE をそのまま使う (従来動作)。
#                   sheet モード時 / SCENE 既に最適化済 / Codex 障害時の fallback で使用。
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SKILL_DIR="$REPO_ROOT/.claude/skills/aozora-illust"
PROMPTS_DIR="$SKILL_DIR/prompts"

REF_FULL="$REPO_ROOT/.claude/memory/illustration-baseline.png"
REF_FACE="$REPO_ROOT/.claude/memory/illustration-baseline-character-closeup.png"
OUT_DIR="$REPO_ROOT/generated-images"

[ -f "$REF_FULL" ] || { echo "ERROR: baseline missing: $REF_FULL" >&2; exit 1; }
[ -f "$REF_FACE" ] || { echo "ERROR: close-up missing: $REF_FACE" >&2; exit 1; }
mkdir -p "$OUT_DIR"

MODE="single"
CATEGORY=""
SCENE=""
OUTFIT_OVERRIDE=""
REF_MODE="both"
CODEX_REWRITE="on"
for arg in "$@"; do
  case "$arg" in
    --mode=*)          MODE="${arg#--mode=}" ;;
    --category=*)      CATEGORY="${arg#--category=}" ;;
    --scene=*)         SCENE="${arg#--scene=}" ;;
    --outfit=*)        OUTFIT_OVERRIDE="${arg#--outfit=}" ;;
    --ref-mode=*)      REF_MODE="${arg#--ref-mode=}" ;;
    --codex-rewrite=*) CODEX_REWRITE="${arg#--codex-rewrite=}" ;;
    -h|--help)
      sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown arg: $arg" >&2; exit 2 ;;
  esac
done

case "$REF_MODE" in
  both|face-only) ;;
  *) echo "ERROR: --ref-mode must be 'both' or 'face-only' (got: $REF_MODE)" >&2; exit 2 ;;
esac

case "$CODEX_REWRITE" in
  on|off) ;;
  *) echo "ERROR: --codex-rewrite must be 'on' or 'off' (got: $CODEX_REWRITE)" >&2; exit 2 ;;
esac

# sheet モードは構図厳密指定 (6 パネル割付) のため Codex rewrite を強制 OFF
if [ "$MODE" = "sheet" ] && [ "$CODEX_REWRITE" = "on" ]; then
  echo "[gen.sh] sheet mode detected — disabling codex-rewrite (panel layout must stay literal)"
  CODEX_REWRITE="off"
fi

FACE_SPEC="$(cat "$PROMPTS_DIR/face-spec.txt")"
STYLE_SPEC="$(cat "$PROMPTS_DIR/style-spec.txt")"
OUTFIT_SPEC="${OUTFIT_OVERRIDE:-$(cat "$PROMPTS_DIR/outfit-spec.txt")}"

TS=$(date +%Y%m%d-%H%M%S)

if [ "$MODE" = "sheet" ]; then
  [ -z "$SCENE" ] && SCENE="LAYOUT: Character model sheet (turnaround + expression chart), 2 rows x 3 columns, 6 panels total, equal panel sizes, thin pale gray border between panels, clean uniform pale ivory background, ABSOLUTELY NO TEXT anywhere.

Row 1 ANGLE TURNAROUND (neutral composed expression, mouth gently closed):
- Panel 1 (top-left): Front view (0 degrees), bust shot.
- Panel 2 (top-center): Three-quarter view (45 degrees), bust shot.
- Panel 3 (top-right): Profile view (90 degrees), bust shot.

Row 2 EXPRESSION CHART (all front view bust):
- Panel 4 (bottom-left): Calm neutral, mouth softly closed.
- Panel 5 (bottom-center): Warm gentle smile, hint of upper teeth.
- Panel 6 (bottom-right): Gentle quiet laugh, eyes softly closed in upward arc.

Every panel must depict UNMISTAKABLY THE SAME PERSON. Same hairstyle, glasses, face shape, skin tone, eye shape, earring, scrub top, lanyard."
  FILENAME="gpt-image-character-sheet-${TS}.png"
  SCENE_LINE="$SCENE"
else
  [ -z "$CATEGORY" ] && { echo "ERROR: --category required for --mode=single" >&2; exit 2; }
  [ -z "$SCENE" ] && { echo "ERROR: --scene required for --mode=single" >&2; exit 2; }
  FILENAME="gpt-image-${CATEGORY}-${TS}.png"

  # Codex (GPT-5.5) で SCENE を ChatGPT UI 風 prompt に rewrite (default ON)
  if [ "$CODEX_REWRITE" = "on" ]; then
    echo "[gen.sh] codex-rewrite=on: optimizing SCENE via codex-rewrite.sh ..."
    REWRITTEN=$("$SKILL_DIR/scripts/codex-rewrite.sh" "$SCENE" 2>&1)
    REWRITE_EXIT=$?
    if [ $REWRITE_EXIT -eq 0 ] && [ -n "$REWRITTEN" ]; then
      SCENE="$REWRITTEN"
      echo "[gen.sh] SCENE rewritten by Codex ($(echo "$REWRITTEN" | wc -c | tr -d ' ') chars)"
    else
      echo "[gen.sh] WARN: codex-rewrite failed (exit=$REWRITE_EXIT), falling back to original SCENE" >&2
      echo "$REWRITTEN" | tail -10 >&2
    fi
  fi

  SCENE_LINE="NEW SCENE: ${SCENE}

Horizontal 16:9 editorial illustration for a Japanese elderly-care company recruitment website. No text anywhere in the image."
fi

PROMPT="${FACE_SPEC}

${STYLE_SPEC}

${OUTFIT_SPEC}

${SCENE_LINE}"

RESP="$(mktemp -t gpt-image-resp.XXXXXX.json)"
trap 'rm -f "$RESP"' EXIT

KEY=$(gcloud secrets versions access latest --secret=openai-api-key --project=openai-api-yh --account=hy.unimail.11@gmail.com 2>/dev/null)
[ -z "$KEY" ] && { echo "ERROR: failed to fetch openai-api-key from Secret Manager" >&2; exit 3; }

MAX=3
DELAY=10
HTTP_CODE=""
REF_ARGS=()
if [ "$REF_MODE" = "both" ]; then
  REF_ARGS+=(-F "image[]=@${REF_FULL}" -F "image[]=@${REF_FACE}")
else
  REF_ARGS+=(-F "image[]=@${REF_FACE}")
fi

for i in $(seq 1 $MAX); do
  HTTP_CODE=$(curl -s -o "$RESP" -w "%{http_code}" \
    -X POST "https://api.openai.com/v1/images/edits" \
    -H "Authorization: Bearer $KEY" \
    -F "model=gpt-image-2" \
    "${REF_ARGS[@]}" \
    -F "prompt=${PROMPT}" \
    -F "size=1536x1024" \
    -F "quality=high" \
    -F "output_format=png" \
    -F "n=1")
  echo "[${MODE}/${CATEGORY:-sheet}] attempt ${i}: HTTP ${HTTP_CODE}"
  [ "$HTTP_CODE" = "200" ] && break
  if [ "$i" -lt "$MAX" ]; then
    echo "[${MODE}/${CATEGORY:-sheet}] retry in ${DELAY}s"
    sleep "$DELAY"
    DELAY=$((DELAY * 2))
  fi
done

if [ "$HTTP_CODE" != "200" ]; then
  echo "[${MODE}/${CATEGORY:-sheet}] FAILED" >&2
  cat "$RESP" >&2
  exit 1
fi

FILENAME="$FILENAME" OUT_DIR="$OUT_DIR" RESPONSE_FILE="$RESP" python3 - <<'PY'
import json, base64, os
with open(os.environ['RESPONSE_FILE']) as f:
    data = json.load(f)
if 'error' in data:
    err = data['error']
    print(f"Error [{err.get('code','?')}]: {err.get('message','')}")
    raise SystemExit(1)
filename = os.environ['FILENAME']
out_dir = os.environ['OUT_DIR']
for item in data['data']:
    out = os.path.join(out_dir, filename)
    img = base64.b64decode(item['b64_json'])
    with open(out, 'wb') as f:
        f.write(img)
    print(f"[saved] {out} ({len(img):,} bytes)")
PY

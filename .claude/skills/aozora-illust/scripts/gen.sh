#!/usr/bin/env bash
# aozora-illust: メインキャラ厳密再現で画像生成
# usage:
#   gen.sh --mode=single --category=<key> --scene="<英語シーン記述>" [--outfit="<override>"] [--ref-mode=both|face-only]
#   gen.sh --mode=sheet [--scene="<6 パネル指定>"] [--ref-mode=both|face-only]
#
# --ref-mode:
#   both (default) — baseline (full scene) + close-up を両方 reference に渡す。
#                    キャラ同一性は最強だが、reference の構図 (タブレット相談等) を強く継承する。
#   face-only      — close-up (顔のみ) だけを渡す。構図は prompt のシーン記述で自由制御可。
#                    職種別シーン差別化が必要なときに使う (実証 2026-06-30)。
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
for arg in "$@"; do
  case "$arg" in
    --mode=*)     MODE="${arg#--mode=}" ;;
    --category=*) CATEGORY="${arg#--category=}" ;;
    --scene=*)    SCENE="${arg#--scene=}" ;;
    --outfit=*)   OUTFIT_OVERRIDE="${arg#--outfit=}" ;;
    --ref-mode=*) REF_MODE="${arg#--ref-mode=}" ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown arg: $arg" >&2; exit 2 ;;
  esac
done

case "$REF_MODE" in
  both|face-only) ;;
  *) echo "ERROR: --ref-mode must be 'both' or 'face-only' (got: $REF_MODE)" >&2; exit 2 ;;
esac

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

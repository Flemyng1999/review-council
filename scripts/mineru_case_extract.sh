#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <source.pdf> <case-dir>" >&2
  exit 2
fi

PDF_PATH="$1"
CASE_DIR="$2"

if [[ ! -f "$PDF_PATH" ]]; then
  echo "PDF not found: $PDF_PATH" >&2
  exit 1
fi
if [[ ! -d "$CASE_DIR" ]]; then
  echo "Case directory not found: $CASE_DIR" >&2
  exit 1
fi

MINERU_ENV="${MINERU_ENV:-mineru312}"
CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
MINERU_MODEL_SOURCE="${MINERU_MODEL_SOURCE:-modelscope}"

NORMALIZED_DIR="$CASE_DIR/normalized"
PROVENANCE_DIR="$CASE_DIR/provenance"
mkdir -p "$NORMALIZED_DIR" "$PROVENANCE_DIR"

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "MinerU PDF conversion must run on ubuntu-303/Linux, not macOS." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate "$MINERU_ENV"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

STEM="$(basename "$PDF_PATH")"
STEM="${STEM%.*}"

export MINERU_MODEL_SOURCE
mineru -p "$PDF_PATH" -o "$TMP_DIR" -l en -b hybrid-auto-engine

MD_FILE="$(find "$TMP_DIR" -maxdepth 5 -type f -name "${STEM}.md" | head -n 1)"
if [[ -z "$MD_FILE" ]]; then
  echo "No ${STEM}.md produced by MinerU." >&2
  exit 1
fi

PRODUCT_DIR="$(dirname "$MD_FILE")"
ASSET_DIR="$NORMALIZED_DIR/${STEM}.assets"
mkdir -p "$ASSET_DIR"

cp "$MD_FILE" "$NORMALIZED_DIR/manuscript.md"
find "$PRODUCT_DIR" -maxdepth 2 -type d -name images -exec cp -R {} "$ASSET_DIR/" \;
find "$PRODUCT_DIR" -maxdepth 1 -type f \( -name "*_content_list.json" -o -name "*_middle.json" -o -name "*_layout.pdf" \) -exec cp {} "$ASSET_DIR/" \;

if [[ -d "$ASSET_DIR/images" ]]; then
  sed -i "s#](images/#](${STEM}.assets/images/#g" "$NORMALIZED_DIR/manuscript.md"
fi

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m review_council.cli index-markdown \
  "$NORMALIZED_DIR/manuscript.md" \
  "$PROVENANCE_DIR/source_map.jsonl"

echo "Wrote $NORMALIZED_DIR/manuscript.md"
echo "Wrote $PROVENANCE_DIR/source_map.jsonl"

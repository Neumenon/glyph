#!/usr/bin/env bash
# materialize_corpus.sh — copy the canonical corpus from the Go testdata tree into
# conformance/corpus/ so external implementers have a single directory to clone.
#
# Run this from the repo root or from conformance/:
#   bash conformance/materialize_corpus.sh
#
# Source of truth is go/glyph/testdata/loose_json/ — do not edit corpus/ directly.
# Re-run this script whenever the source corpus changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC="${REPO_ROOT}/go/glyph/testdata/loose_json"
DST="${SCRIPT_DIR}/corpus"

mkdir -p "${DST}/cases" "${DST}/golden"

cp "${SRC}/manifest.json" "${DST}/manifest.json"
cp "${SRC}/cases/"*.json  "${DST}/cases/"
cp "${SRC}/golden/"*.want "${DST}/golden/"

COUNT=$(ls "${DST}/cases/"*.json | wc -l)
echo "Materialized ${COUNT} corpus cases into conformance/corpus/"

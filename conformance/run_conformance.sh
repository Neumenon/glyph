#!/usr/bin/env bash
# run_conformance.sh — thin shell entry point for the GLYPH conformance suite.
#
# Delegates to run_conformance.py.  All arguments are forwarded.
# Run from the repo root or from conformance/:
#
#   bash conformance/run_conformance.sh
#   bash conformance/run_conformance.sh --impl go --impl py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "${SCRIPT_DIR}/run_conformance.py" "$@"

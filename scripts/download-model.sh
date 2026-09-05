#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT}/docker"
WHEEL="${MODEL_DIR}/en_core_web_sm-3.8.0-py3-none-any.whl"
MODEL_URL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
MIRROR_URL="https://ghfast.top/${MODEL_URL}"

mkdir -p "${MODEL_DIR}"

if [[ -f "${WHEEL}" ]] && [[ $(stat -c%s "${WHEEL}" 2>/dev/null || stat -f%z "${WHEEL}") -gt 1000000 ]]; then
    echo "spaCy model wheel already present: ${WHEEL}"
    exit 0
fi

echo "Downloading spaCy model wheel..."
if curl -fsSL --connect-timeout 15 --max-time 120 -o "${WHEEL}.tmp" "${MODEL_URL}"; then
    mv "${WHEEL}.tmp" "${WHEEL}"
elif curl -fsSL --connect-timeout 15 --max-time 120 -o "${WHEEL}.tmp" "${MIRROR_URL}"; then
    mv "${WHEEL}.tmp" "${WHEEL}"
else
    rm -f "${WHEEL}.tmp"
    echo "Failed to download spaCy model wheel." >&2
    echo "Try manually: curl -L -o ${WHEEL} ${MIRROR_URL}" >&2
    exit 1
fi

echo "Downloaded: ${WHEEL}"

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Protocol Sentinel Evidence Pipeline ==="

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    echo "ERROR: Working tree is not clean."
    echo "Commit or remove pending changes before exporting."
    git status --short
    exit 1
fi

SOURCE_COMMIT="$(git rev-parse HEAD)"
echo "Source commit: $SOURCE_COMMIT"

mkdir -p artifacts/demo
rm -f artifacts/demo/authority-regression.json

echo "=== Executing authority regression ==="

SOURCE_COMMIT="$SOURCE_COMMIT" \
EXPORT_WITNESS=true \
forge test \
    --match-path test/AuthorityRegression.t.sol \
    --match-test test_ExportRiskyWitness \
    -vv

echo "=== Verifying witness ==="

python3 scripts/verify_witness.py
python3 scripts/replay_policy.py artifacts/demo/authority-regression.json

echo "=== Evidence pipeline PASSED ==="

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/sentinel-consumer-v04b.XXXXXX")"

trap 'rm -rf "$WORK"' EXIT

mkdir -p \
  "$WORK/src" \
  "$WORK/test" \
  "$WORK/lib/protocol-sentinel"

# Install a copy of the current local library.
# No source files from the main repository are modified.
cp -R "$ROOT/src" "$WORK/lib/protocol-sentinel/src"

# Reuse pinned, read-only dependency checkouts.
ln -s \
  "$ROOT/lib/forge-std" \
  "$WORK/lib/forge-std"

ln -s \
  "$ROOT/lib/openzeppelin-contracts" \
  "$WORK/lib/openzeppelin-contracts"

ln -s \
  "$ROOT/lib/openzeppelin-contracts-upgradeable" \
  "$WORK/lib/openzeppelin-contracts-upgradeable"

cp \
  "$ROOT/examples/consumer/SentinelTimelockConsumer.t.sol" \
  "$WORK/test/"

cat > "$WORK/foundry.toml" <<'CONFIG'
[profile.default]
src = "src"
test = "test"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
auto_detect_remappings = false

remappings = [
  "forge-std/=lib/forge-std/src/",
  "protocol-sentinel/=lib/protocol-sentinel/src/",
  "@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/",
  "@openzeppelin/contracts-upgradeable/=lib/openzeppelin-contracts-upgradeable/contracts/"
]
CONFIG

echo "=== Independent consumer workspace ==="
echo "$WORK"
echo

echo "=== Compile and run external consumer ==="

(
  cd "$WORK"

  forge build

  if ! forge test \
    --json \
    --threads 1 \
    --match-contract SentinelTimelockConsumerTest \
    > "$WORK/consumer-results.json"; then
    cat "$WORK/consumer-results.json" >&2
    echo "ERROR | Consumer Forge execution failed" >&2
    exit 1
  fi

  python3 "$ROOT/scripts/verify_timelock_consumer_results.py" \
    "$WORK/consumer-results.json"

  forge fmt --check
)

echo
echo "PASS | Independent Timelock consumer"
echo "PASS | External imports and pinned dependencies"
echo "PASS | Real Waiting/Ready route and comparison"
echo "PASS | Source repository remained untouched"

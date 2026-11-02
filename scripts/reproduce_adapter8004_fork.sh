#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

RPC="${ETH_RPC_URL:-https://eth.drpc.org}"

BLOCK=24995819
EXPECTED_HASH=0x7ed82b73024b26c48660f875e9e6816e16102b33731b504b8b86746ee10abc68
PROXY=0xde152AfB7db5373F34876E1499fbD893A82dD336
EXPECTED_IMPL=0xcdeFFf9EaFCfa28be798D1c1B1c8D731087d1CE4
EXPECTED_OWNER=0xF8e03bd4436371E0e2F7C02E529b2172fe72b4EF
SLOT=0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc

lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

echo "=== Adapter8004 mainnet fork preflight ==="

test "$(cast chain-id --rpc-url "$RPC")" = "1"

ACTUAL_HASH="$(cast block "$BLOCK" --field hash --rpc-url "$RPC")"

test "$(lower "$ACTUAL_HASH")" = "$(lower "$EXPECTED_HASH")"

echo "PASS | Ethereum block hash verified"

RAW="$(cast storage "$PROXY" "$SLOT" --block "$BLOCK" --rpc-url "$RPC")"

ACTUAL_IMPL="$(python3 - "$RAW" <<'PY'
import sys
value = int(sys.argv[1], 16) & ((1 << 160) - 1)
print(f"0x{value:040x}")
PY
)"

test "$(lower "$ACTUAL_IMPL")" = "$(lower "$EXPECTED_IMPL")"

echo "PASS | Historical implementation verified"

ACTUAL_OWNER="$(cast call "$PROXY" 'owner()(address)' --block "$BLOCK" --rpc-url "$RPC")"

test "$(lower "$ACTUAL_OWNER")" = "$(lower "$EXPECTED_OWNER")"

echo "PASS | Historical owner verified"

echo "=== Executing isolated mainnet fork tests ==="

RESULT_FILE="$(mktemp)"
trap 'rm -f "$RESULT_FILE"' EXIT

if ! ETH_RPC_TIMEOUT=120 ETH_RPC_URL="$RPC" RUN_MAINNET_FORK=true \
  forge test \
  --json \
  --threads 1 \
  --match-path test/Adapter8004MainnetFork.t.sol \
  > "$RESULT_FILE"; then
  cat "$RESULT_FILE" >&2
  echo "ERROR | Forge execution failed" >&2
  exit 1
fi

python3 scripts/verify_fork_results.py "$RESULT_FILE"

REPORT_DIR="${FORK_REPORT_DIR:-artifacts/fork}"
REPORT_FILE="$REPORT_DIR/adapter8004-mainnet-24995819.json"

python3 scripts/write_fork_report.py \
  --results "$RESULT_FILE" \
  --output "$REPORT_FILE" \
  --block-hash "$ACTUAL_HASH" \
  --implementation "$ACTUAL_IMPL" \
  --owner "$ACTUAL_OWNER"

echo "MAINNET FORK REPRODUCTION PASSED"

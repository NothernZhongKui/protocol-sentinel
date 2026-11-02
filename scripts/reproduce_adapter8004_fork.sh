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

python3 - "$RESULT_FILE" <<'CHECK'
import json
import sys

expected = {
    "testFork_NonOwnerCannotUpgrade()",
    "testFork_OwnerUpgradeDetectedAndRestored()",
    "testFork_HistoricalOwnerCanActuallyUpgrade()",
    "testFork_OutsiderAuthorityRegressionPassFailPass()",
}

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
except (ValueError, OSError) as exc:
    sys.exit(f"ERROR | Invalid Forge JSON: {exc}")

if not isinstance(data, dict):
    sys.exit("ERROR | Unexpected Forge JSON structure")

matching = [
    value
    for name, value in data.items()
    if name.endswith(":Adapter8004MainnetForkTest")
]

if len(matching) != 1:
    sys.exit("ERROR | Fork suite was not executed exactly once")

suite = matching[0]
results = suite.get("test_results", {})

if not isinstance(results, dict):
    sys.exit("ERROR | Invalid test_results structure")

failed = False

for name in sorted(expected):
    result = results.get(name)
    status = (
        result.get("status")
        if isinstance(result, dict)
        else None
    )

    if status == "Success":
        print(f"PASS | {name}")
    else:
        print(f"ERROR | Required fork test {name}: {status}")
        failed = True

for name, result in results.items():
    if name in expected:
        continue

    status = (
        result.get("status")
        if isinstance(result, dict)
        else None
    )

    if status != "Success":
        print(f"ERROR | Additional fork test {name}: {status}")
        failed = True

if failed:
    sys.exit(1)

print(f"PASS | {len(expected)} required fork tests executed")
CHECK

echo "MAINNET FORK REPRODUCTION PASSED"

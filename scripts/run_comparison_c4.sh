#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
LOG="$(mktemp)"
ERROR="$(mktemp)"
BAD="$(mktemp -d)"

trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo "C4 FAILED"; tail -n 18 "$LOG"; tail -n 8 "$ERROR"; fi; rm -f "$LOG" "$ERROR"; rm -rf "$BAD"' EXIT

completed() {
  sed -n 's/^COMPLETED: //p' "$LOG" | tail -1
}

verify_forge() {
  "$PYTHON" - "$LOG" "$1" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
tests = [
    (name, value.get("status"))
    for suite in data.values()
    for name, value in suite.get("test_results", {}).items()
]
assert tests == [(sys.argv[2] + "()", "Success")], tests
PY
}

echo "=== C4: Fresh evidence ==="

"$PYTHON" scripts/run_direct_comparison.py > "$LOG" 2> "$ERROR"
DIRECT="$(completed)/evidence.json"
test -f "$DIRECT"

"$PYTHON" scripts/run_timelock_comparison.py > "$LOG" 2> "$ERROR"
ROUTED="$(completed)"
READY="$ROUTED/ready-evidence.json"
WAITING="$ROUTED/waiting-evidence.json"
test -f "$READY"
test -f "$WAITING"
echo "PASS | Fresh C2 and C3 evidence"

echo "=== C4: Solidity differential oracles ==="

DIRECT_ORACLE="$PWD/artifacts/demo/direct-differential-oracle.json"
ROUTED_ORACLE="$PWD/artifacts/demo/timelock-differential-oracle.json"
rm -f "$DIRECT_ORACLE" "$ROUTED_ORACLE"

DIRECT_DIFFERENTIAL_EVIDENCE="$DIRECT" \
DIRECT_DIFFERENTIAL_OUTPUT="$DIRECT_ORACLE" \
forge test --json --threads 1 \
  --match-contract ComparisonDirectDifferentialOracleTest \
  --match-test test_DirectDifferentialOracle \
  > "$LOG" 2> "$ERROR"

verify_forge test_DirectDifferentialOracle

ROUTED_DIFFERENTIAL_READY_EVIDENCE="$READY" \
ROUTED_DIFFERENTIAL_WAITING_EVIDENCE="$WAITING" \
ROUTED_DIFFERENTIAL_OUTPUT="$ROUTED_ORACLE" \
forge test --json --threads 1 \
  --match-contract ComparisonTimelockDifferentialOracleTest \
  --match-test test_TimelockDifferentialOracle \
  > "$LOG" 2> "$ERROR"

verify_forge test_TimelockDifferentialOracle
echo "PASS | Both Solidity oracles"

echo "=== C4: Python differential parity ==="

"$PYTHON" scripts/check_direct_differential_parity.py \
  --evidence "$DIRECT" --oracle "$DIRECT_ORACLE" \
  > "$LOG" 2> "$ERROR"
grep -q '48/48 MATCH' "$LOG"
echo "PASS | Direct 48/48"

"$PYTHON" scripts/check_timelock_differential_parity.py \
  --ready "$READY" --waiting "$WAITING" \
  --oracle "$ROUTED_ORACLE" \
  > "$LOG" 2> "$ERROR"
grep -q '42/42 MATCH' "$LOG"
echo "PASS | Timelock 42/42"

echo "=== C4: Negative oracle controls ==="

"$PYTHON" - "$DIRECT_ORACLE" "$ROUTED_ORACLE" "$BAD" <<'PY'
import json, sys
from pathlib import Path
for source, filename, field in (
    (sys.argv[1], "direct.json", "slot_context_before_reason"),
    (sys.argv[2], "timelock.json", "ready_wrong_state_failure"),
):
    data = json.loads(Path(source).read_text())
    data[field] = (data[field] + 1) % 8
    (Path(sys.argv[3]) / filename).write_text(json.dumps(data))
PY

if "$PYTHON" scripts/check_direct_differential_parity.py \
  --evidence "$DIRECT" --oracle "$BAD/direct.json" \
  > "$LOG" 2>&1; then
  echo "FAIL | Direct forged oracle accepted"
  exit 1
fi
grep -q 'slot_context_before_reason' "$LOG"

if "$PYTHON" scripts/check_timelock_differential_parity.py \
  --ready "$READY" --waiting "$WAITING" \
  --oracle "$BAD/timelock.json" \
  > "$LOG" 2>&1; then
  echo "FAIL | Timelock forged oracle accepted"
  exit 1
fi
grep -q 'ready_wrong_state_failure' "$LOG"
echo "PASS | Both forged oracles rejected"

echo "=== C4: External consumer ==="

"$PYTHON" scripts/check_comparison_external_replay.py \
  --direct "$DIRECT" --ready "$READY" --waiting "$WAITING" \
  > "$LOG" 2> "$ERROR"

grep -q 'EXTERNAL COMPARISON REPRODUCTION: PASS' "$LOG"
echo "PASS | Standalone consumer"

echo "=== C4: Legacy compatibility ==="

"$PYTHON" scripts/check_policy_replay.py > "$LOG" 2> "$ERROR"
"$PYTHON" scripts/test_schema_boundaries.py > "$LOG" 2> "$ERROR"
"$PYTHON" scripts/test_policy_reason_mutations.py > "$LOG" 2> "$ERROR"

"$PYTHON" scripts/test_comparison_legacy_boundary.py \
  --direct "$DIRECT" --timelock "$READY" \
  > "$LOG" 2> "$ERROR"

grep -q 'LEGACY COMPATIBILITY: PASS' "$LOG"
echo "PASS | Witness 0.2–0.4 compatibility"

forge fmt --check > "$LOG" 2> "$ERROR"
echo "C4 ACCEPTANCE: PASS"

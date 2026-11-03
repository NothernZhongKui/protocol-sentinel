#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== PORTABLE DIRECT EXTERNAL INTEGRATION ==="

ROOT="$(git rev-parse --show-toplevel)"
TOOL_SHA="$(git -C "$ROOT" rev-parse HEAD)"

CONSUMER_REPO="NothernZhongKui/protocol-sentinel-consumer"
CONSUMER_SHA="c46e8703254f9ff3ab220229dfe72fdad1a9c92a"

test -n "${GITHUB_SHA:-}"
test "$TOOL_SHA" = "$GITHUB_SHA"

TEMP="$(mktemp -d "${RUNNER_TEMP:-/tmp}/sentinel-portable.XXXXXX")"
trap 'rm -rf "$TEMP"' EXIT

CONSUMER="$TEMP/protocol-sentinel-consumer"
POLICY="$TEMP/trusted-policy.toml"

echo
echo "=== CLONE PINNED EXTERNAL CONSUMER ==="

git clone --quiet \
  "https://github.com/$CONSUMER_REPO.git" \
  "$CONSUMER"

git -C "$CONSUMER" checkout -q --detach "$CONSUMER_SHA"

git -C "$CONSUMER" submodule update \
  --init --recursive --quiet

test "$(git -C "$CONSUMER" rev-parse HEAD)" = "$CONSUMER_SHA"

echo "PASS | External consumer pinned"

echo
echo "=== BIND CURRENT SENTINEL REVISION ==="

INSTALLED="$CONSUMER/lib/protocol-sentinel"

git -C "$INSTALLED" fetch \
  --quiet --no-tags "$ROOT" "$TOOL_SHA"

git -C "$INSTALLED" checkout \
  -q --detach "$TOOL_SHA"

git -C "$INSTALLED" submodule update \
  --init --recursive --quiet

git -C "$CONSUMER" add lib/protocol-sentinel

git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "ci: pin Sentinel under test"

test "$(git -C "$INSTALLED" rev-parse HEAD)" = "$TOOL_SHA"
test -z "$(git -C "$CONSUMER" status --porcelain)"
test -f "$CONSUMER/foundry.lock"

cp "$CONSUMER/.github/sentinel/trusted-policy.toml" "$POLICY"

echo "PASS | Consumer gitlink points to tested Sentinel"
echo "PASS | Clean committed test checkout"

RUNNER="$INSTALLED/scripts/run_portable_direct.py"

run_gate() {
  local label="$1"
  local verdict="$2"
  local decision="$3"
  local expected_exit="$4"

  local log="$TEMP/$label.log"
  local status=0
  local revision

  revision="$(git -C "$CONSUMER" rev-parse HEAD)"

  echo
  echo "=== RUN $label ==="

  set +e
  env \
    GITHUB_REPOSITORY="$CONSUMER_REPO" \
    GITHUB_SHA="$revision" \
    GITHUB_WORKFLOW_REF="$CONSUMER_REPO/.github/workflows/sentinel-gate.yml@refs/heads/main" \
    python -B "$RUNNER" \
      --project "$CONSUMER" \
      --config sentinel-safe.toml \
      --trusted-policy "$POLICY" \
      > "$log" 2>&1
  status=$?
  set -e

  cat "$log"

  test "$status" -eq "$expected_exit"

  grep -Fqx "CLASSIFICATION: $verdict" "$log"
  grep -Fqx "REPLAY: MATCH" "$log"
  grep -Fqx "CI DECISION: $decision" "$log"

  local completed
  completed="$(sed -n 's/^COMPLETED: //p' "$log" | tail -n 1)"

  test -n "$completed"
  test -d "$completed"

  python - "$completed" "$verdict" "$decision" \
    "$revision" "$TOOL_SHA" <<'PY'
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
verdict, decision, revision, tool_sha = sys.argv[2:]

assert folder.parent.name == "completed"

def read(name):
    return json.loads((folder / name).read_text())

evidence = read("evidence.json")
verification = read("verification.json")
gate = read("ci-gate.json")

assert verification["producer_test"] == "Success"
assert verification["schema"] == "VALID"
assert verification["classification_replay"] == "MATCH"
assert verification["comparison"] == verdict
assert verification["publication"] == "COMPLETED"
assert verification["tool_revision"] == tool_sha

assert evidence["provenance"]["sourceCommit"] == revision
assert gate["decision"] == decision
assert (folder / "build/build-provenance.json").is_file()

print(f"PASS | {verdict} -> {decision}")
print("PASS | Verified Evidence published")
PY

  test -z "$(git -C "$CONSUMER" status --porcelain)"
}

echo
echo "=== SAFE PRODUCER AND POLICY PASS ==="

run_gate \
  safe \
  STILL_SATISFIED \
  PASS \
  0

echo
echo "=== INTRODUCE REAL AUTHORITY REGRESSION ==="

python - "$CONSUMER/src/ConsumerTreasury.sol" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text()

old = '''contract ConsumerTreasuryV2Safe is ConsumerTreasuryV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }
}'''

new = '''contract ConsumerTreasuryV2Safe is ConsumerTreasuryV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }

    function _authorizeUpgrade(address) internal view override {
        if (msg.sender != treasuryAdmin && msg.sender != settlementOperator) {
            revert NotTreasuryAdmin(msg.sender);
        }
    }
}'''

assert content.count(old) == 1
path.write_text(content.replace(old, new, 1))

print("PASS | Test-only privilege regression introduced")
PY

git -C "$CONSUMER" add src/ConsumerTreasury.sol

git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "ci: temporary authority regression"

echo
echo "=== UNSAFE PRODUCER AND POLICY BLOCK ==="

run_gate \
  regression \
  CHANGED_TO_VIOLATION \
  BLOCK \
  2

echo
echo "=== FAILED PRODUCER MUST NOT PUBLISH ==="

python - "$CONSUMER/test/TreasuryAuthority.t.sol" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text()

old = '''        _compareAgainst(address(next));
    }

    /// @dev Example assertions'''

new = '''        _compareAgainst(address(next));
        assertTrue(false);
    }

    /// @dev Example assertions'''

assert content.count(old) == 1
path.write_text(content.replace(old, new, 1))

print("PASS | Deliberately failing producer prepared")
PY

git -C "$CONSUMER" add test/TreasuryAuthority.t.sol

git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "ci: temporary failed producer"

COMPLETED_ROOT="$CONSUMER/artifacts/sentinel/runs/completed"

BEFORE="$(find "$COMPLETED_ROOT" \
  -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"

test "$BEFORE" = "2"

REVISION="$(git -C "$CONSUMER" rev-parse HEAD)"
LOG="$TEMP/failed-producer.log"

set +e
env \
  GITHUB_REPOSITORY="$CONSUMER_REPO" \
  GITHUB_SHA="$REVISION" \
  GITHUB_WORKFLOW_REF="$CONSUMER_REPO/.github/workflows/sentinel-gate.yml@refs/heads/main" \
  python -B "$RUNNER" \
    --project "$CONSUMER" \
    --config sentinel-safe.toml \
    --trusted-policy "$POLICY" \
    > "$LOG" 2>&1
STATUS=$?
set -e

cat "$LOG"

test "$STATUS" = "2"
grep -q 'Producer failed or ambiguous' "$LOG"
grep -q 'No completed evidence published' "$LOG"

AFTER="$(find "$COMPLETED_ROOT" \
  -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"

test "$AFTER" = "$BEFORE"

echo "PASS | Failed producer rejected"
echo "PASS | No additional completed Evidence"

echo
echo "=== PORTABLE INTEGRATION PASSED ==="

#!/usr/bin/env bash
# External v0.6 acceptance, pinned upstream and test-only fixtures.
set -Eeuo pipefail

ROOT="$(git rev-parse --show-toplevel)"
TOOL_SHA="$(git -C "$ROOT" rev-parse HEAD)"
UPSTREAM_SHA="40b713b58f39476bcc081d7987c34a46cc085dd9"
FIXTURES="$ROOT/tests/external/capu"
TEMP="$(mktemp -d /tmp/sentinel-capu-v06.XXXXXX)"
trap 'rm -rf "$TEMP"' EXIT
CONSUMER="$TEMP/capminal-contracts"
PROJECT="$CONSUMER/projects/capu"
INSTALLED="$PROJECT/lib/protocol-sentinel"
POLICY="$TEMP/trusted-policy.toml"
RUNNER="$INSTALLED/scripts/run_workspace_direct.py"

echo "=== V0.6 CAPMINAL EXTERNAL ACCEPTANCE ==="
for name in \
  AuthorityRegressionOracle.t.sol \
  CapuSentinelProducer.t.sol \
  sentinel-safe.toml \
  sentinel-faulty.toml
do
  test -f "$FIXTURES/$name" || {
    echo "Missing external fixture: $FIXTURES/$name" >&2
    exit 1
  }
done

git clone -q https://github.com/Capminal/capminal-contracts.git "$CONSUMER"
git -C "$CONSUMER" checkout -q --detach "$UPSTREAM_SHA"
git -C "$CONSUMER" submodule update --init --recursive -q
test "$(git -C "$CONSUMER" rev-parse HEAD)" = "$UPSTREAM_SHA"

cp "$FIXTURES/AuthorityRegressionOracle.t.sol" "$PROJECT/test/"
cp "$FIXTURES/CapuSentinelProducer.t.sol" "$PROJECT/test/"
cp "$FIXTURES/sentinel-safe.toml" "$PROJECT/"
cp "$FIXTURES/sentinel-faulty.toml" "$PROJECT/"

git -C "$CONSUMER" -c protocol.file.allow=always submodule add -q \
  https://github.com/NothernZhongKui/protocol-sentinel.git \
  projects/capu/lib/protocol-sentinel
git -C "$INSTALLED" fetch -q --no-tags "$ROOT" "$TOOL_SHA"
git -C "$INSTALLED" checkout -q --detach "$TOOL_SHA"
git -C "$INSTALLED" submodule update --init --recursive -q

git -C "$CONSUMER" add \
  .gitmodules projects/capu/lib/protocol-sentinel \
  projects/capu/test/AuthorityRegressionOracle.t.sol \
  projects/capu/test/CapuSentinelProducer.t.sol \
  projects/capu/sentinel-safe.toml \
  projects/capu/sentinel-faulty.toml
git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "test: isolate Sentinel v0.6 external pilot"

test -z "$(git -C "$CONSUMER" status --porcelain)"
test -z "$(git -C "$INSTALLED" status --porcelain --untracked-files=all)"
git -C "$CONSUMER" diff --quiet "$UPSTREAM_SHA" HEAD -- \
  projects/capu/src projects/cap-staking/src

echo "PASS | Upstream pinned; production contracts unchanged"
echo "=== NATIVE FOUNDRY ORACLE ==="
(
  cd "$PROJECT"
  forge test --match-path test/AuthorityRegressionOracle.t.sol -vv
  forge test --match-path test/CapuSentinelProducer.t.sol -vv
)

SOLC=""
for candidate in \
 "$HOME/.svm/0.8.26/solc-0.8.26" \
 "$HOME/Library/Application Support/svm/0.8.26/solc-0.8.26" \
 "$HOME/.local/share/svm/0.8.26/solc-0.8.26"
do
  if test -x "$candidate"; then
    SOLC="$candidate"
    break
  fi
done
test -n "$SOLC" || {
  echo "Exact solc 0.8.26 binary not found" >&2
  exit 1
}
"$SOLC" --version
CONSUMER_SHA="$(git -C "$CONSUMER" rev-parse HEAD)"

run_case() {
  local variant="$1"
  local verdict="$2"
  local decision="$3"
  local exit_expected="$4"
  local fixture="$FIXTURES/sentinel-$variant.toml"
  local logfile="$TEMP/$variant.log"
  local status=0
  local before=0
  local after completed

  python3 - "$fixture" "$POLICY" "$CONSUMER_SHA" "$TOOL_SHA" <<'PY'
import sys
import tomllib
from pathlib import Path
fixture = Path(sys.argv[1])
policy_file = Path(sys.argv[2])
consumer_sha, tool_sha = sys.argv[3:]
producer = tomllib.loads(fixture.read_text())["producer"]
lines = [
    "[policy]",
    'version = "2"',
    'repository = "NothernZhongKui/protocol-sentinel"',
    'consumer_repository = "Capminal/capminal-contracts"',
    f'consumer_commit = "{consumer_sha}"',
    'workspace = "projects/capu"',
    'workflow = ".github/workflows/test.yml"',
    f'tool_commit = "{tool_sha}"',
    "",
    "[[required_scenario]]",
]
for name in ("id", "scenario_id", "source", "contract", "test", "fixture_id"):
    lines.append(f'{name} = "{producer[name]}"')
lines.append('route = "DIRECT_EOA_UUPS"')
policy_file.write_text("\n".join(lines) + "\n")
PY

  if test -d "$PROJECT/artifacts/sentinel/runs/completed"; then
    before="$(find "$PROJECT/artifacts/sentinel/runs/completed" \
      -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  fi

  echo "=== V0.6 $variant: $verdict -> $decision ==="
  env \
    GITHUB_REPOSITORY="NothernZhongKui/protocol-sentinel" \
    GITHUB_SHA="$TOOL_SHA" \
    GITHUB_RUN_ID="123" \
    GITHUB_RUN_ATTEMPT="1" \
    GITHUB_WORKFLOW_REF="NothernZhongKui/protocol-sentinel/.github/workflows/test.yml@refs/heads/main" \
    python3 -B "$RUNNER" \
      --project "$PROJECT" \
      --tool-root "$INSTALLED" \
      --config "sentinel-$variant.toml" \
      --solc "$SOLC" \
      --trusted-policy "$POLICY" \
      > "$logfile" 2>&1 || status=$?
  cat "$logfile"
  test "$status" -eq "$exit_expected"
  grep -Fqx "CLASSIFICATION: $verdict" "$logfile"
  grep -Fqx "REPLAY: MATCH" "$logfile"
  grep -Fqx "CI DECISION: $decision" "$logfile"
  completed="$(sed -n 's/^COMPLETED: //p' "$logfile" | tail -n 1)"
  test -d "$completed"
  after="$(find "$PROJECT/artifacts/sentinel/runs/completed" \
    -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  test "$after" -eq "$((before+1))"
  test -z "$(git -C "$CONSUMER" status --porcelain)"

  python3 - "$completed" "$verdict" "$decision" "$CONSUMER_SHA" "$TOOL_SHA" <<'PY'
import json
import sys
from pathlib import Path
run = Path(sys.argv[1])
verdict, decision, consumer_sha, tool_sha = sys.argv[2:]
def read(name):
    return json.loads((run / name).read_text())
evidence = read("evidence.json")
verification = read("verification.json")
gate = read("ci-gate.json")
assert evidence["schema_version"] == "1.1"
assert evidence["provenance"]["sourceCommit"] == consumer_sha
assert evidence["provenance"]["toolCommit"] == tool_sha
assert evidence["provenance"]["workspace"] == "projects/capu"
assert evidence["provenance"]["buildProvenance"]["format"] == (
    "protocol-sentinel-build-provenance-v2"
)
assert verification["classification_replay"] == "MATCH"
assert verification["build_replay"] == "ISOLATED_COMPILER_OUTPUT_MATCH"
assert verification["comparison"] == verdict
assert verification["publication"] == "COMPLETED"
assert gate["decision"] == decision
print("PASS | Completed Evidence 1.1 and trusted policy gate")
PY
}

run_case safe STILL_SATISFIED PASS 0
run_case faulty CHANGED_TO_VIOLATION BLOCK 2

echo "=== V0.6 CAPMINAL EXTERNAL ACCEPTANCE PASS ==="

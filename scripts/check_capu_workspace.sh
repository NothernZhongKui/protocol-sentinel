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

# Local CLI runs use explicit synthetic CI context. In GitHub Actions, never
# overwrite the actual workflow/run/attempt identity with test constants.
if test "${GITHUB_ACTIONS:-}" = "true"; then
  : "${GITHUB_REPOSITORY:?}"
  : "${GITHUB_SHA:?}"
  : "${GITHUB_RUN_ID:?}"
  : "${GITHUB_RUN_ATTEMPT:?}"
  : "${GITHUB_WORKFLOW_REF:?}"
  test "$GITHUB_REPOSITORY" = "NothernZhongKui/protocol-sentinel"
  test "$GITHUB_SHA" = "$TOOL_SHA"
  CI_REPOSITORY="$GITHUB_REPOSITORY"
  CI_SHA="$GITHUB_SHA"
  CI_RUN_ID="$GITHUB_RUN_ID"
  CI_RUN_ATTEMPT="$GITHUB_RUN_ATTEMPT"
  CI_WORKFLOW_REF="$GITHUB_WORKFLOW_REF"
  echo "PASS | Using real GitHub Actions run/attempt/workflow context"
else
  CI_REPOSITORY="NothernZhongKui/protocol-sentinel"
  CI_SHA="$TOOL_SHA"
  CI_RUN_ID="123"
  CI_RUN_ATTEMPT="1"
  CI_WORKFLOW_REF="NothernZhongKui/protocol-sentinel/.github/workflows/test.yml@refs/heads/main"
  echo "LOCAL | Using synthetic CI context (not production workflow attestation)"
fi

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

# The upstream Foundry workspace intentionally has no write permission
# for vm.writeJson. Grant only the generated Sentinel Evidence directory,
# and commit the effective test-only config into the temporary consumer.
python3 - "$PROJECT/foundry.toml" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
contents = path.read_text(encoding="utf-8")
header = "[profile.default]\n"
assert contents.count(header) == 1
assert "fs_permissions" not in contents
contents = contents.replace(
    header,
    header + 'fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]\n',
    1,
)
path.write_text(contents, encoding="utf-8")
PY

git -C "$CONSUMER" -c protocol.file.allow=always submodule add -q \
  https://github.com/NothernZhongKui/protocol-sentinel.git \
  projects/capu/lib/protocol-sentinel
git -C "$INSTALLED" fetch -q --no-tags "$ROOT" "$TOOL_SHA"
git -C "$INSTALLED" checkout -q --detach "$TOOL_SHA"
git -C "$INSTALLED" submodule update --init --recursive -q

git -C "$CONSUMER" add \
  .gitmodules projects/capu/foundry.toml projects/capu/lib/protocol-sentinel \
  projects/capu/test/AuthorityRegressionOracle.t.sol \
  projects/capu/test/CapuSentinelProducer.t.sol \
  projects/capu/sentinel-safe.toml \
  projects/capu/sentinel-faulty.toml
git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "test: isolate Sentinel v0.6 external pilot"

# Keep generated Evidence out of the tracked upstream checkout without
# modifying or committing its .gitignore.
printf '\n/projects/capu/artifacts/\n' >> "$CONSUMER/.git/info/exclude"

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
    GITHUB_REPOSITORY="$CI_REPOSITORY" \
    GITHUB_SHA="$CI_SHA" \
    GITHUB_RUN_ID="$CI_RUN_ID" \
    GITHUB_RUN_ATTEMPT="$CI_RUN_ATTEMPT" \
    GITHUB_WORKFLOW_REF="$CI_WORKFLOW_REF" \
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

  echo "=== INDEPENDENT COMPLETED EVIDENCE REPLAY: $variant ==="
  local verify_log="$TEMP/$variant-independent.log"
  local verify_status=0
  env \
    GITHUB_REPOSITORY="$CI_REPOSITORY" \
    GITHUB_SHA="$CI_SHA" \
    GITHUB_RUN_ID="$CI_RUN_ID" \
    GITHUB_RUN_ATTEMPT="$CI_RUN_ATTEMPT" \
    GITHUB_WORKFLOW_REF="$CI_WORKFLOW_REF" \
    python3 -B "$INSTALLED/scripts/verify_workspace_run.py" \
      --project "$PROJECT" \
      --tool-root "$INSTALLED" \
      --run-dir "$completed" \
      --config "sentinel-$variant.toml" \
      --solc "$SOLC" \
      --trusted-policy "$POLICY" \
      > "$verify_log" 2>&1 || verify_status=$?
  cat "$verify_log"
  test "$verify_status" -eq "$exit_expected"
  grep -Fqx "PUBLISHED_EVIDENCE=INDEPENDENTLY_REVERIFIED" "$verify_log"
  grep -Fqx "CI_DECISION=$decision" "$verify_log"

  if test "$variant" = "safe"; then
    echo "=== REJECT TAMPERED COMPLETED EVIDENCE ==="
    local evidence="$completed/evidence.json"
    local original="$TEMP/safe-evidence-original.json"
    cp "$evidence" "$original"
    python3 - "$evidence" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
doc = json.loads(path.read_text())
assert doc["comparison"]["verdict"] == "STILL_SATISFIED"
doc["comparison"]["verdict"] = "CHANGED_TO_VIOLATION"
path.write_text(json.dumps(doc, sort_keys=True) + "\n")
PY
    local tamper_status=0
    env \
      GITHUB_REPOSITORY="$CI_REPOSITORY" \
      GITHUB_SHA="$CI_SHA" \
      GITHUB_RUN_ID="$CI_RUN_ID" \
      GITHUB_RUN_ATTEMPT="$CI_RUN_ATTEMPT" \
      GITHUB_WORKFLOW_REF="$CI_WORKFLOW_REF" \
      python3 -B "$INSTALLED/scripts/verify_workspace_run.py" \
        --project "$PROJECT" \
        --tool-root "$INSTALLED" \
        --run-dir "$completed" \
        --config "sentinel-safe.toml" \
        --solc "$SOLC" \
        --trusted-policy "$POLICY" \
        > "$TEMP/tampered-evidence.log" 2>&1 || tamper_status=$?
    cat "$TEMP/tampered-evidence.log"
    test "$tamper_status" -eq 2
    grep -q "COMPLETED_RUN_REJECTED:" "$TEMP/tampered-evidence.log"
    cp "$original" "$evidence"
    cmp "$original" "$evidence"
    test -z "$(git -C "$CONSUMER" status --porcelain)"
    echo "PASS | Tampered completed Evidence rejected"

    echo "=== ADVERSARIAL ARTIFACT MUTATIONS: safe ==="
    env \
      GITHUB_REPOSITORY="$CI_REPOSITORY" \
      GITHUB_SHA="$CI_SHA" \
      GITHUB_RUN_ID="$CI_RUN_ID" \
      GITHUB_RUN_ATTEMPT="$CI_RUN_ATTEMPT" \
      GITHUB_WORKFLOW_REF="$CI_WORKFLOW_REF" \
      python3 -B "$INSTALLED/scripts/test_workspace_artifact_mutations.py" \
        --run-dir "$completed" \
        --verifier "$INSTALLED/scripts/verify_workspace_run.py" \
        --project "$PROJECT" \
        --tool-root "$INSTALLED" \
        --config sentinel-safe.toml \
        --solc "$SOLC" \
        --trusted-policy "$POLICY"
    test -z "$(git -C "$CONSUMER" status --porcelain)"
  fi
}

run_case safe STILL_SATISFIED PASS 0
run_case faulty CHANGED_TO_VIOLATION BLOCK 2

echo "=== FAILED PRODUCER MUST NOT PUBLISH EVIDENCE ==="

python3 - "$PROJECT/test/CapuSentinelProducer.t.sol" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
content = path.read_text()
before = """    function test_ProduceSafe() public {
        _record(false);
    }"""
after = """    function test_ProduceSafe() public {
        _record(false);
        assertTrue(false);
    }"""
assert content.count(before) == 1
path.write_text(content.replace(before, after))
PY

git -C "$CONSUMER" add projects/capu/test/CapuSentinelProducer.t.sol
git -C "$CONSUMER" \
  -c user.name="Sentinel CI" \
  -c user.email="sentinel-ci@example.invalid" \
  commit -q -m "test: deliberately fail external Sentinel producer"

NEW_CONSUMER_SHA="$(git -C "$CONSUMER" rev-parse HEAD)"

# Rebind BOTH the trusted consumer revision and the selected scenario:
# the preceding run used the faulty policy, but this negative control
# intentionally invokes the safe producer with a failing assertion.
python3 - "$POLICY" "$CONSUMER_SHA" "$NEW_CONSUMER_SHA" "$FIXTURES/sentinel-safe.toml" <<'PY'
from pathlib import Path
import sys
import tomllib

path = Path(sys.argv[1])
old, new, safe_config = sys.argv[2:]
existing = tomllib.loads(path.read_text())
policy = existing["policy"]
assert policy["consumer_commit"] == old
assert existing["required_scenario"][0]["id"] == "capu_faulty"
policy["consumer_commit"] = new
producer = tomllib.loads(Path(safe_config).read_text())["producer"]
lines = ["[policy]"]
for key in (
    "version", "repository", "consumer_repository", "consumer_commit",
    "workspace", "workflow", "tool_commit",
):
    lines.append(f'{key} = "{policy[key]}"')
lines.extend(["", "[[required_scenario]]"])
for key in ("id", "scenario_id", "source", "contract", "test", "fixture_id"):
    lines.append(f'{key} = "{producer[key]}"')
lines.append('route = "DIRECT_EOA_UUPS"')
path.write_text("\n".join(lines) + "\n")
assert tomllib.loads(path.read_text())["required_scenario"][0]["id"] == "capu_safe"
print("PASS | Trusted policy rebound to safe producer and new consumer commit")
PY

COMPLETED_ROOT="$PROJECT/artifacts/sentinel/runs/completed"
BEFORE="$(find "$COMPLETED_ROOT" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
FAIL_LOG="$TEMP/failed-producer.log"
FAIL_STATUS=0

env \
  GITHUB_REPOSITORY="$CI_REPOSITORY" \
  GITHUB_SHA="$CI_SHA" \
  GITHUB_RUN_ID="$CI_RUN_ID" \
  GITHUB_RUN_ATTEMPT="$CI_RUN_ATTEMPT" \
  GITHUB_WORKFLOW_REF="$CI_WORKFLOW_REF" \
  python3 -B "$RUNNER" \
    --project "$PROJECT" \
    --tool-root "$INSTALLED" \
    --config sentinel-safe.toml \
    --solc "$SOLC" \
    --trusted-policy "$POLICY" \
    > "$FAIL_LOG" 2>&1 || FAIL_STATUS=$?

cat "$FAIL_LOG"
test "$FAIL_STATUS" -eq 2
grep -q 'Producer failed or ambiguous' "$FAIL_LOG"
grep -q 'No completed Evidence published' "$FAIL_LOG"

AFTER="$(find "$COMPLETED_ROOT" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
test "$BEFORE" -eq "$AFTER"
test -z "$(git -C "$CONSUMER" status --porcelain)"

echo "PASS | Failed producer rejected with no completed Evidence"
echo "=== V0.6 CAPMINAL EXTERNAL ACCEPTANCE PASS ==="

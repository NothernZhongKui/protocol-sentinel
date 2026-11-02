#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_SHA="2ee48d0af7dfdc6f0daa0a3017b70edf137033ec"

echo "=== Protocol Sentinel | Fortytwo Reproduction ==="

# Use the exact dependency revisions pinned by Protocol Sentinel.
for entry in \
  "forge-std:f3dae6e6ee381f25eb6a246f7da9b85c91a68219" \
  "openzeppelin-contracts:dbb6104ce834628e473d2173bbc9d47f81a9eec3" \
  "openzeppelin-contracts-upgradeable:723f8cab09cdae1aca9ec9cc1cfa040c2d4b06c1"
do
  name="${entry%%:*}"
  expected="${entry#*:}"
  path="$ROOT/lib/$name"

  if [[ ! -d "$path" ]]; then
    echo "ERROR | Missing dependency: $name"
    echo "Run: git submodule update --init --recursive"
    exit 1
  fi

  actual="$(git -C "$path" rev-parse HEAD)"

  if [[ "$actual" != "$expected" ]]; then
    echo "ERROR | Unexpected dependency revision: $name"
    exit 1
  fi
done

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/sentinel-x402.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

EXTERNAL="$SCRATCH/fortytwo-x402Escrow"

mkdir -p "$EXTERNAL"
git -C "$EXTERNAL" init -q

echo "=== Fetch pinned Fortytwo source ==="

git -C "$EXTERNAL" fetch --quiet --depth 1 \
  https://github.com/Fortytwo-Network/fortytwo-x402Escrow.git \
  "$EXTERNAL_SHA"

git -C "$EXTERNAL" -c advice.detachedHead=false \
  checkout -q --detach FETCH_HEAD

test "$(git -C "$EXTERNAL" rev-parse HEAD)" = "$EXTERNAL_SHA"

echo "PASS | External source revision verified"

# Copy pinned dependencies; do not download their histories again.
mkdir -p "$EXTERNAL/lib"

for name in \
  forge-std \
  openzeppelin-contracts \
  openzeppelin-contracts-upgradeable
do
  cp -R "$ROOT/lib/$name" "$EXTERNAL/lib/$name"
done

# Use the current Protocol Sentinel core without symlinks.
mkdir -p "$EXTERNAL/lib/protocol-sentinel"
cp -R "$ROOT/src" "$EXTERNAL/lib/protocol-sentinel/src"

cp "$ROOT/examples/x402/ExternalSentinelIntegration.t.sol" \
  "$EXTERNAL/test/ExternalSentinelIntegration.t.sol"

cat > "$EXTERNAL/foundry.toml" <<'CONFIG'
[profile.default]
src = "src"
test = "test"
out = "out"
libs = ["lib"]
solc_version = "0.8.28"
auto_detect_remappings = false
remappings = [
    "forge-std/=lib/forge-std/src/",
    "@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/",
    "@openzeppelin/contracts-upgradeable/=lib/openzeppelin-contracts-upgradeable/contracts/",
    "protocol-sentinel/=lib/protocol-sentinel/src/"
]
CONFIG

echo "=== Generate intentional authority regression ==="

python3 "$ROOT/examples/x402/generate_risky_fixture.py" \
  "$EXTERNAL/src/X402Escrow.sol" \
  "$EXTERNAL/test/fixtures/SentinelRiskyEscrow.sol" \
  --write

python3 "$ROOT/examples/x402/generate_risky_fixture.py" \
  "$EXTERNAL/src/X402Escrow.sol" \
  "$EXTERNAL/test/fixtures/SentinelRiskyEscrow.sol" \
  --check

echo "=== Run external integration tests ==="

(
  cd "$EXTERNAL"
  forge test \
    --match-path test/ExternalSentinelIntegration.t.sol \
    -vv
)

git -C "$EXTERNAL" diff --exit-code HEAD -- src/X402Escrow.sol

echo "PASS | All external regression tests passed"
echo "PASS | Original Fortytwo contract unchanged"
echo "=== Reproduction complete ==="

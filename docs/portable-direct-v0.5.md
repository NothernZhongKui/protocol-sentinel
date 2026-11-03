# Portable Direct Authority Regression — v0.5

## What it does

Protocol Sentinel runs a developer-declared upgrade
authority scenario inside an external Foundry project.

It compares behavior before and after a legitimate
implementation change.

The portable runner performs:

1. Fresh execution of one selected Foundry test.
2. Capture of actual Solidity observations.
3. Strict Evidence assembly and validation.
4. Independent Python classification replay.
5. Independent solc 0.8.24 compiler replay.
6. Optional trusted CI policy decision.

No consumer-specific Python scripts are required.

## Supported scope

- Direct EOA actor.
- ERC-1967 implementation observation.
- Canonical UUPS upgradeToAndCall(address,bytes).
- Empty upgrade initialization calldata.
- Declared actor, target, candidate and expected revert.
- One configured producer scenario per invocation.

This is not automatic authorization discovery.

The existing Timelock adapter is separate from the
portable Direct runner.

## Requirements

- Foundry with compatible forge test/build-info support.
- Python 3.12 and the Sentinel verifier dependencies.
- Exact solc 0.8.24+commit.e11b9ed9.
- A Git-tracked Foundry project with a clean checkout.
- Committed foundry.toml and foundry.lock.
- A pinned, clean Sentinel Git submodule at
  lib/protocol-sentinel.
- Git-ignored artifacts/sentinel/ output directory.

Use a Python virtual environment outside the consumer
checkout to preserve the clean-working-tree requirement.

## 1. Install the library

From your Foundry project:

```bash
forge install --no-commit NothernZhongKui/protocol-sentinel
```

Pin the installed lib/protocol-sentinel submodule to
the tested revision or a published release tag.

The consumer must commit its submodule gitlink,
.gitmodules, foundry.lock and Sentinel configuration.

Add the import remapping to foundry.toml:

```toml
"protocol-sentinel/=lib/protocol-sentinel/src/"
```

Keep your existing forge-std and dependency remappings.

## 2. Write one Foundry producer test

Import DirectComparisonCapture:

```solidity
import {
    DirectComparisonCapture
} from "protocol-sentinel/DirectComparisonCapture.sol";
```

Your test should:

1. Construct the initial upgradeable fixture.
2. Declare UpgradeCheck for the actor and action.
3. Observe the before stage using _observeDirectStage.
4. Perform the intended authorized implementation change.
5. Observe the after stage.
6. Call _compareDirectUpgrade.
7. Call _exportDirectComparison with the same scenario ID.

The producer must be a passing, uniquely selected
Foundry test and export exactly one Direct capture.

For a complete working Solidity implementation, see:

https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/main/test/TreasuryAuthority.t.sol

## 3. Configure the producer

Create a tracked file named sentinel-safe.toml:

```toml
[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "treasury_safe"
contract = "TreasuryAuthorityTest"
test = "test_SafeUpgradePreservesRestriction"
source = "test/TreasuryAuthority.t.sol"
fixture_id = "external-treasury-v1-safe-v2"
scenario_id = "0x86917dbb645eece6a5a6f11fa636fdae5558fa7fd4ab12c07488142cbfbb39bf"
```

These values describe the reference consumer, not a
generic configuration. Replace them with your own
contract, test, fixture and exact bytes32 scenario ID.

The scenario ID must match the ID exported by Solidity.

## 4. Run locally

Install dependencies in your Python 3.12 environment:

```bash
python -m pip install \
  -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt
```

Then, from a clean consumer checkout:

```bash
python -B \
  lib/protocol-sentinel/scripts/run_portable_direct.py \
  --project "$PWD" \
  --config sentinel-safe.toml
```

Successful verification prints classification, replay
status and the completed Evidence location.

Completed runs are published under:

artifacts/sentinel/runs/completed/<run-id>/

The directory contains evidence.json, verification.json,
compiler build provenance and execution records.

Local mode prints CI DECISION: NOT_EVALUATED.

A matched replay is not permission to merge.

## 5. Trusted GitHub CI

To receive PASS, BLOCK or REVIEW, a protected workflow
must supply --trusted-policy using an absolute path to
a policy checked out from the trusted base revision.

The policy identifies one required producer scenario
and the expected repository and workflow.

Use the working external consumer as an integration
reference, adapting repository identity, paths,
policy, pinned tool revision and test selection:

https://github.com/NothernZhongKui/protocol-sentinel-consumer

A trusted CI boundary must prevent unreviewed PRs
from replacing the required GitHub Actions check.

The reference consumer demonstrates an independent
workflow-integrity check and protected required checks.

The runner alone does not establish that trust boundary.

## CI decision meanings

| Comparison | CI decision |
| --- | --- |
| STILL_SATISFIED | PASS |
| CHANGED_TO_VIOLATION | BLOCK |
| STILL_VIOLATED | BLOCK |
| CHANGED_TO_SATISFIED | REVIEW |
| INDETERMINATE | REVIEW |
| INCOMPARABLE | REVIEW |

Missing, duplicated or invalid required scenarios
are blocking errors.

A successfully replayed security violation is BLOCK,
not PASS.

## Trust and limitations

Sentinel verifies the selected declared scenario,
not every authorization path in the protocol.

The test author controls fixture setup, actor selection,
expected reverts and the before/after transition.

Compiler reproduction establishes consistency of
compiler outputs against the recorded build inputs.

Independent Python replay establishes consistency of
classification against recorded observations.

Neither establishes independently authenticated
EVM execution or guarantees contract security.

Evidence execution provenance remains UNAUTHENTICATED.

For production adoption, review the tested scenario,
protected CI workflow, trusted policy and branch rules.

# Comparative Authority Core — Quick Start

Status: experimental API included in v0.4.1.

The comparison helper was introduced during v0.4-A
and is included in the consolidated v0.4.1 release.

## Purpose

ComparativeAuthorityProbe compares one declared upgrade
scenario across two different active implementations.

It reports whether the specified authority restriction:

- Remained satisfied.
- Became violated.
- Became satisfied again.
- Remained violated.
- Cannot be determined from available evidence.
- Cannot be compared across the supplied stages.

It does not discover permissions automatically.

## Import

Inherit the comparison helper in a Foundry test:

~~~solidity
import {ComparativeAuthorityProbe} from
    "protocol-sentinel/ComparativeAuthorityProbe.sol";

contract MyAuthorityTest is ComparativeAuthorityProbe {
    // Your fixture and tests go here.
}
~~~

The helper inherits AuthorityProbe and retains its
observation and policy evaluation API.

## Comparison workflow

1. Declare one UpgradeCheck specification.
2. Execute the baseline isolated probe.
3. Explicitly perform an authorized implementation upgrade.
4. Execute the updated-version isolated probe.
5. Compare the two recorded observations.

The same declared actor, proxy, candidate, expected
revert and policy are used for both observations.

## Example

The following snippet assumes a Foundry fixture defining:

- operator: actor whose authority is being tested.
- governor: actor permitted to install the next version.
- proxy: ERC-1967 UUPS proxy.
- baselineImplementation: initial implementation address.
- riskyImplementation: implementation to install.
- candidate: valid UUPS candidate for the tested action.
- expectedRevert: exact expected authorization revert.

The snippet belongs inside a test inheriting
ComparativeAuthorityProbe.

~~~solidity
UpgradeCheck memory spec = UpgradeCheck({
    actor: operator,
    target: address(proxy),
    candidate: address(candidate),
    expectedRevert: expectedRevert,
    policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
});

// Observe the baseline version without keeping state changes.
DetailedUpgradeCheckResult memory baseline =
    _checkIsolatedUpgradeDetailed(spec);

// The fixture explicitly performs a real authorized upgrade.
vm.prank(governor, governor);
RoleVaultV1(address(proxy)).upgradeToAndCall(
    address(riskyImplementation),
    bytes("")
);

// Observe the new version without keeping probe effects.
DetailedUpgradeCheckResult memory updated =
    _checkIsolatedUpgradeDetailed(spec);

DirectComparisonResult memory comparison =
    _compareDirectUpgrade(
        keccak256("operator-upgrade-restriction"),
        spec,
        DirectStage({
            expectedActiveImplementation:
                address(baselineImplementation),
            observation: baseline.observation
        }),
        DirectStage({
            expectedActiveImplementation:
                address(riskyImplementation),
            observation: updated.observation
        })
    );

assertEq(
    uint256(comparison.verdict),
    uint256(ComparisonVerdict.CHANGED_TO_VIOLATION)
);
~~~

This example uses the project's RoleVault test fixture.
The complete executable integration example is:

test/ComparativeAuthorityIntegration.t.sol

An independent consumer example is:

examples/consumer/SentinelComparativeConsumer.t.sol

## Comparison verdicts

| Before | After | Comparison |
|---|---|---|
| PASS | PASS | STILL_SATISFIED |
| PASS | FAIL | CHANGED_TO_VIOLATION |
| FAIL | PASS | CHANGED_TO_SATISFIED |
| FAIL | FAIL | STILL_VIOLATED |
| UNKNOWN | Any valid status | INDETERMINATE |
| Any valid status | UNKNOWN | INDETERMINATE |

INCOMPARABLE takes precedence when declared scenario
identity or stage binding does not match.

Both individual evaluations are always recomputed,
including when the overall verdict is INCOMPARABLE.

An individual PASS does not override INCOMPARABLE.

## Stage binding

Each DirectStage declares:

~~~solidity
address expectedActiveImplementation;
Observation observation;
~~~

The comparator compares the implementation address
using the lower 160 bits of the ERC-1967 storage word.

Changes only in the upper 96 bits cannot establish
that two different implementations were used.

The expected active implementation addresses must differ.

This API does not compare role changes while retaining
the same implementation address.

## Scenario identity

The scenarioKey is derived using domain-separated
ABI encoding of:

- Explicit scenarioId.
- Direct comparison semantics version.
- Declared actor and target.
- Candidate implementation and canonical calldata.
- Expected revert payload.
- Selected upgrade policy.
- ERC-1967 implementation slot.

The key is not an execution proof.

## Policy interpretation

Phase A supports the existing negative policies:

- NO_IMPLEMENTATION_REPLACEMENT
- NO_SUCCESSFUL_UPGRADE_CALL

An authorized successful upgrade may produce FAIL
when the declared negative policy forbids that action.

Therefore CHANGED_TO_VIOLATION means the declared
restriction became violated under the recorded scenario.
It does not independently establish exploitability.

A matching expected revert does not prove which
authorization branch rejected the transaction.

## Required environment controls

The Foundry test author must:

- Establish genuine baseline and updated deployments.
- Prepare the intended actor and authorization state.
- Use the same scenario specification across stages.
- Confirm the active implementation at each stage.
- Execute authorized installation explicitly.
- Preserve isolation of each attempted upgrade.
- Document relevant non-implementation state changes.
- Stop on setup, execution or restoration failures.

A scenarioKey does not establish matching chain state,
roles, timestamps, bytecode or observation provenance.

The comparator is pure; it does not call the EVM,
authenticate observations or inspect infrastructure errors.

## Limitations

The experimental phase A API supports only:

- Direct EOA observations.
- ERC-1967 implementation slots.
- Canonical UUPS upgradeToAndCall(address,bytes).
- Empty initialization data.
- One common scenario specification.
- Distinct active implementation addresses.

There is no comparison JSON evidence schema in phase A.

Contract-mediated execution, Timelock routes and
positive authorized-operation checks belong to
later v0.4 development phases.

## Verification

Run:

~~~bash
forge test --match-path test/ComparativeAuthorityProbe.t.sol
forge test --match-path test/ComparativeAuthorityFuzz.t.sol
forge test --match-path test/ComparativeAuthorityIntegration.t.sol
python3 scripts/check_comparison_mutations.py
~~~

See also:

- docs/rfc-004-comparative-authority-regression.md
- docs/adr-004a-comparison-core.md

# Protocol Sentinel — Library Quick Start

## Purpose

Protocol Sentinel checks declared authorization properties
in upgradeable Ethereum contracts using local Foundry execution.

It does not discover every permission or prove protocol security.

## Requirements

- Foundry
- Solidity 0.8.24
- forge-std
- ERC-1967 proxy with a supported UUPS upgrade entry point

## Import

Make Protocol Sentinel available as a Foundry dependency.

Example remapping:

    protocol-sentinel/=lib/protocol-sentinel/src/

Import its public helper:

~~~solidity
import {AuthorityProbe} from "protocol-sentinel/AuthorityProbe.sol";
~~~

Your test contract inherits AuthorityProbe.

## Example

Assume the test fixture already defines operator, proxy,
and a valid UUPS candidate implementation.

~~~solidity
UpgradeCheck memory spec = UpgradeCheck({
    actor: operator,
    target: address(proxy),
    candidate: address(candidate),
    expectedRevert: abi.encodeWithSignature(
        "NotGovernor(address)",
        operator
    ),
    policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
});

UpgradeCheckResult memory result = _checkIsolatedUpgrade(spec);

assertEq(
    uint256(result.status),
    uint256(PolicyStatus.PASS)
);
~~~

## Diagnostic API

The optional detailed API returns the observation, status
and diagnostic reason without executing an additional probe.

Example, using the UpgradeCheck specification defined above:

    DetailedUpgradeCheckResult memory detailed =
        _checkIsolatedUpgradeDetailed(spec);

    assertEq(
        uint256(detailed.status),
        uint256(PolicyStatus.PASS)
    );

    assertEq(
        uint256(detailed.reason),
        uint256(PolicyReason.NONE)
    );

UNKNOWN diagnostic reasons:

- INVALID_SLOT: incorrect implementation slot.
- INVALID_TARGET: target preconditions are not satisfied.
- CONTEXT_MISMATCH: actor, origin or target differs.
- NON_CANONICAL_CALLDATA: unsupported upgrade calldata.
- INVALID_CANDIDATE: invalid candidate on rejected execution.
- UNEXPECTED_REVERT: unexpected rejection or state observation.
- SUCCESS_WITHOUT_REPLACEMENT: successful call without replacement.

PASS and FAIL use PolicyReason.NONE.

The legacy UpgradeCheckResult remains unchanged.

An empty expectedRevert cannot establish PASS.
Use the actual expected authorization error payload.

The evaluator does not independently prove which contract
branch caused a matching revert.

## Evidence compatibility

The main execution witness currently uses schema 0.2.

Current diagnostic policy matrices use schema 0.4 and require
reason and target_valid_at_observation.

Python replay checks the recorded classification independently.
It does not independently inspect EVM state.

Legacy schemas 0.2 and 0.3 remain supported. Their replay
results do not establish target validity.

## Policy semantics

NO_IMPLEMENTATION_REPLACEMENT:

- PASS: expected rejection, valid candidate, unchanged address
- FAIL: successful call changes effective implementation address
- UNKNOWN: insufficient evidence for either conclusion

NO_SUCCESSFUL_UPGRADE_CALL:

- PASS: expected rejection, valid candidate, unchanged address
- FAIL: supported upgrade call succeeds
- UNKNOWN: insufficient evidence

ERROR is reserved for setup or execution failures.

## Supported scope

- Direct EOA calls
- ERC-1967 implementation storage slot
- Canonical upgradeToAndCall(address,bytes)
- Empty initialization data
- Known actors and targets
- Foundry snapshot isolation

Contract-mediated calls and other upgrade selectors
are outside the convenience API's current scope.

## Important limitations

Candidate validation uses proxiableUUID() from the test
harness context. It is not a full upgrade-safety check.

The expected authorization revert is supplied by the
test author. Matching revert bytes do not prove which
authorization branch executed.

Target preconditions are captured before execution:
the target has code, the ERC-1967 implementation slot
contains a nonzero address, and that address has code.
A non-proxy contract can still imitate these conditions.

PASS applies only to the specified actor, call, and policy.

The helper is not a substitute for an independent audit.

## External integration experiment

One synthetic Treasury consumer produced:

- Plain Foundry: 132 lines
- Sentinel low-level API: 129 lines
- Sentinel convenience API: 111 lines

All three implementations passed their test scenarios.

This comparison demonstrates local integration, not
independent market validation or a general benchmark.

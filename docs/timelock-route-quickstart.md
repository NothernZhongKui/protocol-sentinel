# Timelock Route Adapter — Quick Start

Status: experimental, unreleased Protocol Sentinel v0.4-B.

This API is available on the development branch.
It is not part of the published v0.3.0 release.

## Purpose

TimelockAuthorityProbe tests one declared execution route:

EOA executor
  -> OpenZeppelin TimelockController
  -> ProxyAdmin
  -> TransparentUpgradeableProxy

The route uses one scheduled Timelock operation, value
zero, and canonical ProxyAdmin.upgradeAndCall calldata
with empty initialization bytes.

The adapter does not support arbitrary governance routes,
Safe, AccessManager, batched operations, or live-chain
execution.

## Import

In a Foundry test:

~~~solidity
import {TimelockAuthorityProbe} from
    "protocol-sentinel/TimelockAuthorityProbe.sol";

contract MyRouteTest is TimelockAuthorityProbe {
    // Prepare a controlled Timelock fixture here.
}
~~~

The adapter inherits ComparativeAuthorityProbe and
AuthorityProbe without changing their original APIs.

It depends on the repository's pinned OpenZeppelin 5.x
contracts and a compatible forge-std installation.

## Clean OpenZeppelin 5.x deployment

The second TransparentUpgradeableProxy constructor
argument is initialOwner, not an existing ProxyAdmin.

The proxy creates its own ProxyAdmin.

A controlled fixture should:

1. Deploy TimelockController with the intended roles.
2. Deploy the initial implementation and upgrade candidate.
3. Deploy TransparentUpgradeableProxy with the Timelock
   address as initialOwner.
4. Identify the newly created ProxyAdmin and verify its
   ownership and the effective proxy administration.
5. Schedule the exact declared operation.
6. Explicitly establish Waiting or Ready.
7. Invoke Sentinel only after preparation is complete.

The adapter does not grant roles, schedule operations,
or advance block time automatically.

## Declare a scenario

This example assumes the fixture already supplies the
addresses and salt shown below.

~~~solidity
TimelockScenario memory spec = TimelockScenario({
    timelock: address(timelock),
    proposer: proposer,
    executor: executor,
    proxyAdmin: address(admin),
    proxy: address(proxy),
    candidate: address(candidate),
    predecessor: bytes32(0),
    salt: salt,
    property: TimelockProperty.READY_UPGRADE_SUCCEEDS
});
~~~

The proposer is declared preparation context. Its field
is not proof of historical scheduling provenance.

The library derives canonical calldata and operationId
from the declared scenario.

## Observe and evaluate

After explicit scheduling and advancing to the operation's
readiness timestamp:

~~~solidity
RoutedObservation memory obs =
    _observeIsolatedTimelockRoute(spec);

RoutedEvaluation memory evaluation =
    _evaluateTimelockRoute(spec, obs);

assertEq(
    uint256(evaluation.status),
    uint256(PolicyStatus.PASS)
);
~~~

The isolated probe calls the actual Timelock execute
entry point using the declared initiating EOA context.

It records the outcome and restores the pre-probe EVM
state. Restoration failure aborts the probe.

For the negative property, use
NOT_READY_EXECUTION_REJECTED with an operation that is
exactly Waiting and an eligible executor.

A valid negative PASS requires the exact pinned
TimelockUnexpectedOperationState error payload.

A role rejection does not prove a timelock delay.

A Ready operation with an unfinished predecessor is
not valid positive-property preparation.

## Compare versions

Observe the common scheduled operation while the
first implementation is active.

Use a separate authorized governance operation to
install the second implementation.

Observe the original operation again without consuming
it in either probe.

Then call:

~~~solidity
RoutedComparisonResult memory result =
    _compareTimelockRoute(
        keccak256("my-declared-route"),
        spec,
        RoutedStage({
            expectedActiveImplementation: firstImplementation,
            observation: beforeObservation
        }),
        RoutedStage({
            expectedActiveImplementation: secondImplementation,
            observation: afterObservation
        })
    );
~~~

The code above assumes firstImplementation,
secondImplementation, beforeObservation, and
afterObservation are supplied by the fixture.

The common scenario must retain its identity.
Recorded governance-role changes, rescheduling, or
other incompatible preparation can make the stages
INCOMPARABLE.

A change only in the active implementation normally
does not change the OpenZeppelin administrative route.

STILL_SATISFIED is therefore the expected result for
a correctly configured route across two compatible
implementations.

## Complete executable example

See:

examples/consumer/SentinelTimelockConsumer.t.sol

Run the independent consumer:

~~~bash
bash scripts/check_timelock_consumer.sh
~~~

Run the targeted adversarial mutation suite:

~~~bash
python3 scripts/check_timelock_mutations.py
~~~

Run all project regression tests:

~~~bash
forge test
~~~

## Trust and scope

RoutedObservation is evidence supplied by a local
observer, not a cryptographic execution certificate.

The pure evaluator can reject missing, malformed, or
inconsistent evidence. It cannot independently detect
a fully fabricated but internally consistent record.

The effective Transparent proxy administrator cannot
be authenticated from the mutable ERC-1967 admin
storage word alone.

The controlled fixture establishes the trusted
deployment topology and checks actual execution.

The adapter is a testing helper, not a security audit,
a governance discovery engine, or a transaction sender.

See docs/adr-004b-timelock-route.md.

## EOA executor boundary

The current adapter accepts nonzero executor addresses
without deployed runtime bytecode. Contract executors
and the zero address are rejected before the probe.

The observation records whether the EOA-shaped
executor precondition was established.

Missing evidence produces UNKNOWN. Known invalid
executor preparation is rejected rather than producing
a policy PASS or FAIL.

Absence of bytecode does not prove possession of a
private key, exclude every precompile or counterfactual
account, or authenticate a real transaction signer.

Contract-mediated executors require a separate
execution adapter exercising their actual entry point.

The independent consumer runner validates Forge JSON.
Skipped, missing or unsuccessful tests never satisfy
its required acceptance checks.

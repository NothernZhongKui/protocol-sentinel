# ADR-004B: Timelock Execution Route

Status: PROPOSED
Target: Protocol Sentinel v0.4-B
Parent: RFC-004
Dependency: ADR-004A
Baseline: v0.4-A comparison core

## 1. Decision

Add one explicit contract-mediated execution route:

EOA executor
    -> TimelockController
    -> ProxyAdmin
    -> TransparentUpgradeableProxy

Support OpenZeppelin single-operation execution only.

The initial adapter must observe a real EOA-initiated
execution, evaluate one declared route property, and
support comparison across different proxy implementations.

The administrative upgrade route is generally independent
of the current implementation's authorization logic.

Phase B primarily verifies governance-route properties.
It does not claim that changing implementation code
necessarily changes Timelock or ProxyAdmin authority.

Do not change AuthorityProbe or the v0.4-A direct API.

## 2. Scope

Included:

- One explicitly declared Timelock route.
- One canonical ProxyAdmin upgrade action.
- Explicitly prepared and scheduled operations.
- Ready and not-ready operation properties.
- Actual outer execution through TimelockController.
- Proxy implementation effect observation.
- Isolated EVM execution and state restoration.
- Pure route evaluation.
- Comparison of matching routed scenarios.

Excluded:

- Automatic operation scheduling.
- Automatic role grants.
- Automatic vm.warp.
- Batched Timelock operations.
- Safe or AccessManager integrations.
- Arbitrary calldata routing.
- Universal governance discovery.
- Live-chain execution.

## 3. OpenZeppelin Compatibility

Use the repository's pinned OpenZeppelin submodules.

Reviewed repository pins:

- openzeppelin-contracts:
  dbb6104ce834628e473d2173bbc9d47f81a9eec3
- openzeppelin-contracts-upgradeable:
  723f8cab09cdae1aca9ec9cc1cfa040c2d4b06c1

Verify these pins before implementation.

The relevant TransparentUpgradeableProxy and ProxyAdmin
interfaces use the OpenZeppelin 5.x architecture.

The implementation must preserve exact API compatibility
with the pinned dependencies.

The canonical action is:

    ProxyAdmin.upgradeAndCall(
        ITransparentUpgradeableProxy(proxy),
        candidate,
        bytes("")
    )

The initial Timelock operation value is zero.

Operation execution uses:

    TimelockController.execute(
        proxyAdmin,
        0,
        canonicalPayload,
        predecessor,
        salt
    )

No arbitrary initialization calldata in phase B.

The initial candidate must have deployed runtime code.
It need not implement UUPS proxiableUUID().

Transparent proxy administrative upgrades use the
ProxyAdmin route rather than UUPS authorization.

With empty initialization data, the current implementation
is not called to authorize the administrative upgrade.

The clean fixture must not pretend otherwise.

Use a clean Transparent Proxy + ProxyAdmin fixture.

In the pinned OpenZeppelin 5.x implementation,
TransparentUpgradeableProxy creates its own ProxyAdmin.

Its constructor's second argument is initialOwner,
not an existing ProxyAdmin address.

The clean deployment recipe is:

1. Deploy the TimelockController.
2. Deploy the initial implementation.
3. Deploy TransparentUpgradeableProxy with the
   Timelock address as initialOwner.
4. Obtain the ProxyAdmin created by the proxy.
5. Verify that the deployed ProxyAdmin has code
   and is owned by the Timelock.
6. Prepare the operation targeting that ProxyAdmin.

Passing a predeployed ProxyAdmin as initialOwner
would not make it the effective proxy administrator.

Reading the ERC-1967 admin slot is useful for the
trusted initial fixture, but is not sufficient
authentication of effective administration.

Do not use the mixed Transparent/UUPS authority
regression fixture as the generic adapter baseline.

## 4. Execution Identity

The actual initiating EOA is the declared executor.

An ordinary EOA transaction to the Timelock has:

    tx.origin == executor
    msg.sender == executor

Inside ProxyAdmin the Timelock is msg.sender.

Inside the transparent proxy administrative upgrade,
ProxyAdmin is the immediate caller.

The adapter MUST call the real Timelock execute entry.

It MUST NOT impersonate Timelock or ProxyAdmin as
an EOA using vm.prank.

Foundry prank may establish the initiating executor
only, with sender and origin equal to that executor.

## 5. Scenario Model

Proposed TimelockScenario fields:

- timelock
- proposer as declared preparation context
- executor
- proxyAdmin
- proxy
- candidate
- predecessor
- salt
- property

The initial public scenario does not contain an
arbitrary expectedRevert field.

The not-ready rejection is derived from the exact
pinned TimelockController implementation.

The route derives its canonical ProxyAdmin calldata.

The Timelock operation tuple is:

    (proxyAdmin, 0, payload, predecessor, salt)

The operationId is derived from the full tuple using
the OpenZeppelin Timelock hashOperation semantics.

Do not accept an arbitrary operation ID without
recomputing and checking it.

The proposer is a declared participant in preparation,
not an authenticated historical schedule() sender.

The existence of an operation and the proposer's
current role do not prove who originally scheduled it.

The consumer explicitly performs and verifies
scheduling in the controlled Foundry fixture.
The phase B observer does not attest historical
scheduling provenance.

## 6. Route Properties

Define two explicit properties:

READY_UPGRADE_SUCCEEDS

The declared, ready and executable operation must
replace the proxy's implementation with the candidate.

Timelock Ready describes timestamp readiness only.

For positive-property executability also require:

    predecessor == bytes32(0)
        || predecessorDoneBefore

A known unfinished predecessor invalidates positive
scenario preparation, even if the operation is Ready.

An unknown predecessor state yields UNKNOWN when
evaluation cannot establish the required precondition.

A legitimate TimelockUnexecutedPredecessor revert
must not become a false positive-policy FAIL.

NOT_READY_EXECUTION_REJECTED

A specifically scheduled, not-ready operation must
reject execution, leave the proxy implementation
unchanged and remain not done.

The properties must be evaluated independently.

A rejected early execution does not prove that the
upgrade would succeed after the delay expires.

## 7. Explicit Preparation

The consumer is responsible for:

1. Deploying a clean proxy and ProxyAdmin.
2. Assigning ProxyAdmin ownership to the Timelock.
3. Configuring declared proposer and executor roles.
4. Deploying the upgrade candidate.
5. Scheduling the exact declared operation.
6. Establishing the intended readiness state.
7. Providing any necessary EVM time advancement.
8. Verifying the initial active implementation.

The adapter must not silently perform these actions.

For BOTH route properties, verify executor eligibility:

    hasRole(EXECUTOR_ROLE, executor)
        || hasRole(EXECUTOR_ROLE, address(0))

The second case represents OpenZeppelin's open
executor role. The executor need not personally
hold the role when it is open.

For READY_UPGRADE_SUCCEEDS, require:

- Operation state exactly Ready.
- Executor eligible.
- Predecessor absent or already Done.
- Verified ProxyAdmin ownership and candidate validity.

For NOT_READY_EXECUTION_REJECTED, require:

- Operation state exactly Waiting.
- Executor eligible.
- Predecessor absent or already Done, to isolate
  the delay restriction from dependency failures.
- Verified scheduled operation identity.

An unauthorized executor cannot establish PASS
for the Timelock delay property.

A not-ready operation is not merely any pending
operation: pending includes both Waiting and Ready.

At block.timestamp == getTimestamp(operationId),
a scheduled operation is Ready, not Waiting.

Unscheduled-operation checks require an explicitly
declared negative test, not a fabricated PASS.

Known invalid required setup is a caller/runner
error before ordinary positive-policy evaluation.

An observation with unknown or incomplete required
preconditions yields UNKNOWN when the evaluator
cannot establish the property.

Do not treat invalid preparation as a policy FAIL,
or turn missing preparation evidence into PASS.

## 8. Observation

A distinct RoutedObservation must record:

- Observed executor and transaction origin.
- Outer call target and calldata.
- Outer execution success and return data.
- Declared Timelock and ProxyAdmin addresses.
- Operation ID.
- Operation state before execution: Unset, Waiting,
  Ready or Done.
- Operation done state before and after.
- Declared predecessor ID.
- Predecessor Done state before execution, including
  whether that fact was actually observed.
- Observed timestamp and readiness timestamp.
- ERC-1967 implementation slot before and after.
- Candidate and proxy precondition results.
- Relevant ProxyAdmin ownership and executor eligibility.

Do not populate existing direct-EOA Observation fields
with invented contract-mediated context.

In the pinned TransparentUpgradeableProxy implementation,
the actual ProxyAdmin is stored in an immutable field.

The ERC-1967 admin storage slot may be altered by
implementation code without altering that immutable admin.

Therefore reading the admin slot alone cannot authenticate
the effective administrative authority.

The test fixture must establish the deployed topology,
verify ProxyAdmin ownership, and exercise the real route.

The proxy implementation is read from the proxy,
not from Timelock or ProxyAdmin.

## 9. Inner Execution Evidence

An outer-call success is not by itself evidence
that the intended implementation replacement occurred.

For READY_UPGRADE_SUCCEEDS require independently:

- The exact declared operation was ready.
- The declared executor was eligible.
- The predecessor was zero or already Done.
- The outer Timelock execute call succeeded.
- The operation became done.
- The proxy implementation became the candidate.
- The previous implementation was different.

Observe the implementation slot before and after.

A slot change establishes an observed state effect.
It does not prove authorization causality or provide
an independent authenticated execution trace.

Never fabricate an innerSuccess boolean.

## 10. Positive Evaluation

READY_UPGRADE_SUCCEEDS:

PASS when all declared preconditions are established
and the required state effect is observed.

FAIL only when valid, ready, executable preparation,
including predecessor completion and executor eligibility,
is established but the required execution or upgrade
effect does not occur.

An operation that is Ready but blocked by an unfinished
predecessor has invalid positive-property preparation,
not a demonstrated failure of the upgrade route.

UNKNOWN when the recorded observations are insufficient,
inconsistent or cannot establish preconditions.

Infrastructure and snapshot failures abort in the runner.

A revert after verified ready preparation is not
automatically UNKNOWN: it can violate the positive
property when the preconditions are established.

## 11. Negative Evaluation

NOT_READY_EXECUTION_REJECTED:

PASS requires:

- The exact operation was scheduled.
- The initial operation state was exactly Waiting.
- The declared executor was eligible.
- The predecessor was zero or already Done.
- Execution reverted with the pinned time-state error.
- The proxy implementation remained unchanged.
- The operation remained not done.

For the pinned OpenZeppelin 5.x controller, require
the complete revert payload:

    TimelockUnexpectedOperationState(
        operationId,
        bytes32(uint256(4))
    )

The value 4 encodes the Ready-state bitmap.

Verify both the error selector and its arguments.
Do not accept arbitrary expectedRevert bytes.

An AccessControl rejection from an ineligible executor
does not establish the delay property.

FAIL when an otherwise valid Waiting operation
unexpectedly executes successfully.

UNKNOWN for unexpected revert data, missing evidence
or contradictory recorded effects.

Known invalid preparation is rejected by the runner.
An absent operation is not interchangeable with
a specifically scheduled Waiting operation.

## 12. Snapshot Isolation

The caller explicitly prepares the initial state.

The isolated probe:

1. Captures pre-execution evidence.
2. Creates an EVM snapshot.
3. Executes the declared outer call.
4. Captures post-execution evidence.
5. Reverts to the snapshot.
6. Verifies restoration where observable.

Verify restoration of:

- Proxy implementation slot.
- Timelock operation state.
- Timelock readiness and done flags.
- Relevant ProxyAdmin and governance state.

Test timestamp restoration explicitly.

Do not assume that snapshotState covers every
environmental property without checking it.

Failed restoration aborts the scenario.

Do not restore to a state that predates the explicit
preparation required for the current observation.

## 13. Pure Evaluation Boundary

Execution and evaluation remain separate.

The route evaluator receives a recorded observation
and the one declared TimelockScenario.

It performs no external calls or cheatcode operations.

Use route-specific evaluation types and diagnostic
reasons rather than overloading direct EOA PolicyReason.

All statuses must be initialized explicitly.

The evaluator must never turn missing evidence
into PASS through default enum values.

The pure evaluator checks consistency and declared
properties, not authenticity of EVM execution.

A fabricated but internally consistent RoutedObservation
may be indistinguishable from genuine recorded evidence.

Provenance therefore depends on the trusted observer
and controlled execution environment.

## 14. Comparative Semantics

Compare the same declared operation and property
across two different active implementations.

For a clean OpenZeppelin Transparent proxy, changing only
the currently active implementation normally cannot change
the result of the administrative ProxyAdmin upgrade route.

With identical Timelock, ProxyAdmin, roles, operation
preconditions and candidate, a preserved route property
is the primary expected comparative outcome.

A changing verdict must not automatically be attributed
to the implementation-code change.

The phase B adapter must not manufacture PASS-to-FAIL
examples by silently altering governance conditions.

Changes to governance configuration require explicit
scenario declarations and separate semantic treatment.
They are not implementation-code regressions by default.

Reuse the six verdict semantics defined in ADR-004A:

- STILL_SATISFIED
- CHANGED_TO_VIOLATION
- CHANGED_TO_SATISFIED
- STILL_VIOLATED
- INDETERMINATE
- INCOMPARABLE

Bind the route scenario to a domain-separated key.

The key includes route type, semantic version,
actors, Timelock, ProxyAdmin, proxy, candidate,
policy and the complete operation tuple.

The expected not-ready error is determined by
the pinned route semantics version, not by
caller-supplied arbitrary revert bytes.

The active implementation belongs to each stage,
not to the common scenario key.

Both individual route evaluations must be recomputed
even if the final comparison is INCOMPARABLE.

Compare active implementation addresses, not entire
256-bit storage words.

## 15. Preparation Between Versions

An isolated successful probe must not consume the
prepared operation in the persistent test environment.

The consumer must explicitly prepare comparable
before and after stage states.

A version transition may require a separate,
authorized operation.

Do not silently re-schedule an operation that is
already pending or completed.

Different operation IDs or different route policies
are not automatically comparable.

Additional changes to roles, timestamps, balances
or governance state must be declared and controlled.

For the initial comparative API, hold governance routing,
roles and administrative ownership constant between stages.

The candidate must differ from both active stage
implementation addresses when the property requires
an actual implementation replacement.

A stage with misconfigured ownership or missing scheduled
operations is not automatically a policy FAIL.
Distinguish invalid preparation from a failed execution
with established valid preconditions.

Governance-configuration regressions need an explicit
comparison model before definitive classification.

A comparison key cannot authenticate the environment.

## 16. Required Tests

1. Ready operation executes through the full route.
2. Proxy implementation becomes the candidate.
3. Timelock operation transitions to done.
4. Early execution is rejected.
5. Early execution does not change the implementation.
6. Early execution does not consume the operation.
7. Unscheduled operation is not classified as ready.
8. Wrong salt changes the operation identity.
9. Wrong predecessor changes the operation identity.
10. Unauthorized executor cannot execute.
11. Wrong ProxyAdmin ownership is detected.
12. Outer success without the required effect fails
    the positive property.
13. Unexpected early revert remains UNKNOWN.
14. Snapshot restores proxy state.
15. Snapshot restores Timelock operation state.
16. Time restoration behavior is explicitly tested.
17. Mismatched routed scenarios are INCOMPARABLE.
18. Both evaluations survive INCOMPARABLE.
19. Malformed, incomplete or internally inconsistent
    observations cannot produce a definitive false PASS.

    A fully fabricated but internally consistent record
    cannot be authenticated by a pure evaluator.
    Its provenance depends on the trusted observer.
20. Existing v0.3 and v0.4-A tests remain green.
21. Changing only the active implementation preserves
    a correctly configured administrative route.
22. A candidate without UUPS proxiableUUID() can still
    be a valid Transparent proxy upgrade candidate.
23. An altered ERC-1967 admin storage word cannot
    by itself establish a new effective ProxyAdmin.
24. Invalid governance preparation is not silently
    reported as a definitive policy violation.
25. Candidate equal to a stage implementation cannot
    masquerade as an implementation replacement.
26. Ready operation with an unfinished predecessor
    does not produce a false positive-policy FAIL.
27. Waiting operation with an ineligible executor
    does not produce a delay-property PASS.
28. At the exact readiness timestamp the operation
    is Ready, not Waiting.
29. Open executor role through address(0) permits an
    EOA without its own EXECUTOR_ROLE assignment.
30. Two sequential isolated probes preserve the same
    prepared operation without consuming it.
31. Not-ready PASS requires the exact selector,
    operationId and Ready-state bitmap.
32. A fully consistent fabricated observation is
    documented as unauthenticated, not proven genuine.
33. The declared proposer is not mistaken for
    authenticated scheduling provenance.

Include adversarial mutation testing and a standalone
consumer of the new adapter.

## 17. Implementation Boundaries

Proposed separate helper:

    src/TimelockAuthorityProbe.sol

Retain unchanged:

    src/AuthorityProbe.sol
    src/ComparativeAuthorityProbe.sol

Do not introduce Timelock logic into the original
direct EOA observer.

Prefer small route-specific types and pure functions.

Exact public types remain subject to adversarial
design review before implementation.

## 18. Deferred Work

Phase C adds comparison JSON evidence, replay and
strict validation.

Phase D adds independent consumer validation and
additional external verification.

No JSON schema expansion is required in the initial
phase B implementation.

## 19. Acceptance Criteria

The first Timelock adapter is acceptable only if:

- It executes the actual four-contract route.
- The executor is the initiating EOA.
- Setup and scheduling remain explicit.
- Positive and negative properties are independent.
- A successful outer call cannot fabricate an upgrade.
- UNKNOWN cannot silently become PASS.
- Both stage evaluations survive comparison failure.
- Snapshot restoration is verified.
- The comparison retains v0.4-A semantics.
- Old APIs remain source-compatible.
- Independent tests detect deliberate defects.

## 20. Review Questions

Before accepting this ADR:

1. Is the proposed interface unnecessarily large?
2. Can a successful outer call hide a failed effect?
3. Are setup errors separated from policy failures?
4. Can an operation be reused incorrectly between stages?
5. Are scheduling and time assumptions explicit?
6. Can malformed observations fabricate a PASS?
7. Is the positive property strong enough?
8. Can the clean proxy fixture distinguish route
   failures from implementation behavior?
9. Are any route semantics silently inherited from
   the old direct EOA helper?
10. Does the design incorrectly attribute administrative
    route behavior to the current implementation code?
11. Are effective proxy administration and the ERC-1967
    admin storage slot being confused?
12. Are invalid setup and a violated positive property
    distinguished clearly enough?
13. Does Ready incorrectly imply predecessor completion?
14. Can an unauthorized executor fabricate a delay PASS?
15. Are exact pinned revert bytes checked?
16. Is proposer identity treated as preparation context
    rather than authenticated historical provenance?

Status remains PROPOSED until independently reviewed.

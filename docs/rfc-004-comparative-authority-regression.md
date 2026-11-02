# RFC-004: Comparative Authority Regression

Status: PROPOSED
Target: Protocol Sentinel v0.4
Base release: v0.3.0

## 1. Summary

Protocol Sentinel v0.4 introduces comparison of declared
upgrade-authority scenarios across contract versions.

The release also introduces one contract-mediated execution
route using OpenZeppelin TimelockController.

The objective is to detect:

- Newly available unauthorized upgrade paths.
- Previously authorized upgrade paths that stop working.
- Preserved restrictions and preserved authorized behavior.
- Insufficient or incomparable observations.

The v0.3 direct EOA API remains available and unchanged.

## 2. Motivation

v0.3 evaluates individual upgrade attempts.

Developers currently assemble before/after comparisons
manually using multiple Sentinel calls and assertions.

v0.4 should provide a repeatable comparison workflow
without expanding into a general security framework.

The product outcome is a report explaining which declared
authority properties changed across implementations.

## 3. Scope

Included:

- Comparison of declared scenarios across two versions.
- Existing direct EOA UUPS checks.
- One OpenZeppelin TimelockController execution adapter.
- Single scheduled operations.
- ProxyAdmin-mediated upgrade execution.
- Independent checks for forbidden and authorized paths.
- Snapshot-based scenario isolation.
- Structured comparison evidence.
- Negative, mutation and external consumer tests.

Excluded:

- Safe transaction execution.
- AccessManager adapters.
- Timelock batch operations.
- Automatic governance topology discovery.
- Arbitrary privileged actions.
- Universal execution routing.
- Live blockchain monitoring.
- Cryptographic attestation of execution.
- General storage-layout verification.

## 4. Design Principles

1. Preserve the v0.3 public Solidity API.
2. Separate action semantics from execution routes.
3. Never infer inner-call success from outer-call success.
4. Never invent observed execution context.
5. Treat missing evidence as indeterminate.
6. Keep scenario preparation explicit.
7. Do not silently grant roles, schedule operations,
   or advance EVM time.
8. Compare only equivalent declared scenarios.
9. Keep evaluation independent of EVM execution.
10. Minimize new public abstractions.

## 5. Conceptual Model

Action:
The intended effect being checked.

For v0.4 this means replacement of a declared ERC-1967
proxy implementation.

Route:
How execution reaches the upgrade action.

Supported routes:

- DIRECT_EOA
- OZ_TIMELOCK_SINGLE

Scenario:
A declared action, route, actors, execution conditions,
expected outcome, and policy version.

Observation:
Facts captured during local EVM execution.

Evaluation:
Whether the observed behavior satisfies the policy.

Comparison:
Relationship between evaluations of equivalent
scenarios in two contract versions.

## 6. Compatibility

The following v0.3 components remain unchanged:

- AuthorityProbe
- Observation
- UpgradeCheck
- UpgradeCheckResult
- DetailedUpgradeCheckResult
- UpgradePolicy
- PolicyStatus
- PolicyReason

Contract-mediated execution receives separate types.

Existing direct EOA observations must not be populated
with fabricated routed execution context.

No breaking changes to the published helper API.

## 7. Scenario Identity

A comparison requires equivalent scenarios.

Identity must bind:

- Scenario and policy identifiers and versions.
- Action kind and semantic target proxy.
- Route kind and relevant execution contracts.
- Initiating actor and executor identity.
- Candidate implementation and exact action payload.
- Declared execution phase and expected behavior.
- Timelock operation tuple where applicable.

Observed block timestamps and implementation versions
are stage-specific evidence, not scenario identity.

The before/after execution state may differ only where
the test explicitly declares an allowed variation.

If the scenario identity or required preconditions differ,
comparison returns INCOMPARABLE.

It must not silently produce a regression verdict.

## 8. Individual Scenario Evaluation

New comparison-facing outcomes:

- SATISFIED
- VIOLATED
- INDETERMINATE

Infrastructure or setup failures abort the scenario
with a structured execution error.

They must not silently become SATISFIED.

Existing direct EOA policy evaluation retains its
PASS / FAIL / UNKNOWN / ERROR model.

The comparison layer may translate the existing
policy verdict into the new outcome vocabulary.

The translation must preserve the original evidence
and diagnostic reason.

## 9. Comparison Semantics

Comparison outcomes:

- STILL_SATISFIED
- CHANGED_TO_VIOLATION
- CHANGED_TO_SATISFIED
- STILL_VIOLATED
- INDETERMINATE
- INCOMPARABLE

A forbidden action available in both versions remains
a violation, even though behavior did not change.

UNKNOWN evidence must not produce a definitive
authority-regression claim.

Changes in policies or route semantics must not
be reported as comparable security outcomes.

The report preserves both individual evaluations.

## 10. Positive and Negative Properties

Negative property:

An unauthorized upgrade attempt must be rejected
without replacing the implementation.

Positive property:

An explicitly authorized, correctly prepared upgrade
must replace the implementation with the candidate.

These properties are evaluated independently.

A fix that blocks all upgrades is not necessarily safe:
it may remove a required governance capability.

A Timelock refusal before readiness establishes a
route-level restriction, not proxy-level authorization.

## 11. Timelock Adapter v0.4

Initial supported topology:

EOA executor
    |
    v
TimelockController
    |
    v
ProxyAdmin
    |
    v
TransparentUpgradeableProxy

Use a pinned OpenZeppelin major and exact tested version.

Support one TimelockController operation containing:

- target
- value
- data
- predecessor
- salt

The operation identity must be computed from the
complete operation tuple.

The adapter must bind the ProxyAdmin operation
to the specific observed proxy and candidate.

The implementation slot is observed at the proxy,
not at the Timelock or ProxyAdmin.

The adapter does not automatically prepare governance
permissions or scheduled operations.

## 12. Explicit Preparation

Scenario setup must explicitly provide:

- Deployed controller and proxy topology.
- Authorized proposer.
- Declared executor.
- Prepared operation tuple.
- Scheduled operation state, if required.
- Readiness requirements.
- Upgrade candidate.

No hidden role grants.

No hidden scheduling.

No hidden time advancement.

The test harness controls preparation and time.

The runner may observe and validate preconditions.

An absent required operation is a setup error unless
the scenario explicitly tests operation absence.

## 13. Routed Observation

A new RoutedObservation should capture:

- Declared route and initiating actor.
- Actual outer call target and calldata.
- Outer call success and return data.
- Timelock operation identity.
- Operation state before and after execution.
- Relevant timestamps and readiness evidence.
- Observed proxy implementation before and after.
- Expected candidate implementation.
- Target validity and candidate preconditions.
- Whether inner execution was independently established.

Outer-call success does not imply target action success.

A changed proxy implementation establishes an observed
state effect, but does not independently identify every
internal call or authorization branch.

If inner execution cannot be established, record
that uncertainty instead of inventing a boolean.

## 14. Evaluation of the Timelock Route

For an authorized ready operation:

- The exact declared operation must be ready.
- The executor must be permitted to execute it.
- The outer execution must succeed.
- The operation must become done.
- The observed proxy implementation must equal
  the declared candidate.

A ready operation that cannot achieve the required
effect violates the positive property when its
preconditions were established.

For a not-ready operation:

- The same exact operation must be scheduled.
- Its readiness state must be established.
- An early execution must be rejected.
- The proxy implementation must remain unchanged.
- The operation must not become done.

Expected refusal before readiness confirms only
the declared Timelock route restriction.

Unexpected reverts require explicit diagnostics.

## 15. Snapshot Isolation

Snapshot boundaries must cover the complete probe.

Verify restoration of:

- Proxy implementation.
- Timelock operation state.
- Any modified governance state.
- Relevant execution-time state.

Snapshot restoration failure is an execution error.

Do not report a successful isolated evaluation when
state restoration cannot be confirmed.

Before and after observations must use independently
prepared and isolated stage states.

Preparation for one stage must not contaminate another.

## 16. Evidence

Introduce a separate comparison evidence format.

Do not overload the existing witness schema 0.4.

Comparison evidence must include:

- Source commit and relevant source hashes.
- Tool and adapter versions.
- Scenario identity and policy version.
- Route and operation identity.
- Declared actors and payloads.
- Stage identity and implementation.
- Preparation and readiness observations.
- Outer execution result.
- Observed implementation effect.
- Individual evaluations and reasons.
- Comparison verdict and rationale.
- Explicit limitations.

The validator must reject missing required evidence,
ambiguous fields and contradictory results.

JSON replay verifies classification consistency.
It does not authenticate EVM execution.

Execution traces may assist diagnostics but must not
be treated as proof of authorization causality.

## 17. Required Adversarial Tests

At minimum:

1. Direct unauthorized upgrade becomes available.
2. Unauthorized upgrade remains rejected.
3. Previously authorized upgrade becomes unavailable.
4. Authorized ready operation succeeds.
5. Scheduled operation cannot execute early.
6. Unscheduled operation is rejected.
7. Wrong salt or predecessor is detected.
8. Unauthorized executor is rejected.
9. Outer success without required state effect is detected.
10. Operation state is restored after isolated execution.
11. Proxy implementation is restored after isolated execution.
12. Unexpected revert remains indeterminate where appropriate.
13. Mismatched scenario identities are incomparable.
14. Malformed comparison evidence is rejected.
15. Existing v0.3 consumers remain compatible.

Use a clean Transparent Proxy + ProxyAdmin fixture for
the generic routed adapter.

Retain the existing intentionally mixed Transparent/UUPS
fixture as a separate authority-regression demonstration.

## 18. Delivery Phases

Phase A — Comparison core

- Scenario identity model.
- Pure outcome comparison.
- Direct EOA integration.
- Unit and mutation tests.

Phase B — Timelock route

- Single-operation adapter.
- Explicit preparation.
- Positive and negative route checks.
- Snapshot isolation tests.

Phase C — Evidence

- Structured comparison witness.
- Independent validation and replay.
- CI negative controls.

Phase D — External validation

- Independent Foundry consumer.
- Adversarial review.
- Fork experiment if it contributes new evidence.
- Documentation and release verification.

## 19. Acceptance Criteria

v0.4 is complete when:

- The v0.3 API remains source-compatible.
- Direct scenarios can be compared before and after.
- A real Timelock route is executed without impersonating
  the Timelock as the initiating EOA.
- Forbidden and authorized paths are tested separately.
- A regression granting new authority is detected.
- A regression breaking required authority is detected.
- Unknown and incomparable outcomes are not hidden.
- Full scenario state is restored after isolated probes.
- Structured evidence is independently validated.
- Negative controls detect deliberately introduced defects.
- An external Foundry consumer reproduces the workflow.
- The new API reduces repeated scenario boilerplate
  without concealing important preconditions.

## 20. Open Design Questions

Resolve before implementation:

1. Exact Solidity types and minimal public API.
2. Scenario identity encoding and versioning.
3. Comparison evaluation mapping.
4. Required observations for Timelock positive controls.
5. Snapshot and block-time restoration semantics.
6. Explicit operation preparation contract.
7. Evidence schema version and validation boundary.
8. Supported OpenZeppelin release pin.
9. Cross-version handling of candidate implementation.
10. Whether the first adapter warrants a separate module.

No implementation begins until these decisions have
concrete tests and an agreed interface.

## 21. Release Philosophy

v0.4 is not a universal governance-security scanner.

It is a narrow, reproducible Foundry workflow for
declared authority properties across upgrade versions.

Expand execution depth before expanding feature breadth.

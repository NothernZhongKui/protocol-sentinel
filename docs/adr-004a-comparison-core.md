# ADR-004A: Comparative Authority Core

Status: PROPOSED
Target: Protocol Sentinel v0.4-A
Parent: RFC-004
Baseline: v0.3.0

## 1. Decision

Build a small, pure comparison layer on top of the
existing AuthorityProbe observation and evaluation API.

First support direct EOA UUPS upgrade scenarios.

Do not implement routed execution or Timelock in phase A.

The comparison must identify:

- Newly violated authority restrictions.
- Restrictions restored after an upgrade.
- Restrictions preserved across versions.
- Violations present in both versions.
- Indeterminate or incomparable observations.

## 2. Compatibility

Keep src/AuthorityProbe.sol unchanged.

Retain:

- Observation
- UpgradeCheck
- PolicyEvaluation
- PolicyStatus
- PolicyReason
- UpgradeCheckResult
- DetailedUpgradeCheckResult
- Existing convenience and low-level APIs

Implement the comparison core as a separate helper,
tentatively src/ComparativeAuthorityProbe.sol.

No migration should be necessary for v0.3 consumers.

## 3. Core Types

Proposed Solidity interface:

    abstract contract ComparativeAuthorityProbe
        is AuthorityProbe
    {
        enum ComparisonVerdict {
            STILL_SATISFIED,
            CHANGED_TO_VIOLATION,
            CHANGED_TO_SATISFIED,
            STILL_VIOLATED,
            INDETERMINATE,
            INCOMPARABLE
        }

        enum ComparisonReason {
            NONE,
            SCENARIO_MISMATCH,
            STAGE_BINDING_MISMATCH,
            SAME_IMPLEMENTATION_STAGE,
            INDETERMINATE_POLICY
        }

        struct DirectStage {
            bytes32 expectedActiveImplementation;
            Observation observation;
        }

        struct DirectComparisonResult {
            bytes32 scenarioKey;
            PolicyEvaluation beforeEvaluation;
            PolicyEvaluation afterEvaluation;
            ComparisonVerdict verdict;
            ComparisonReason reason;
        }

        function _compareDirectUpgrade(
            bytes32 scenarioId,
            UpgradeCheck memory spec,
            DirectStage memory beforeStage,
            DirectStage memory afterStage
        )
            internal
            pure
            returns (DirectComparisonResult memory);
    }

These types are architectural proposals, not yet
committed production interfaces.

The implementation phase may simplify naming or layout
without changing the documented semantics.

## 4. Scenario Identity

Use one UpgradeCheck specification for both stages.

The scenario identity is computed from:

- Explicit scenarioId.
- Comparison format version.
- Route identifier DIRECT_EOA.
- Actor.
- Target proxy.
- Candidate implementation.
- Canonical upgrade calldata.
- Expected revert payload.
- Upgrade policy and its semantic version.
- ERC-1967 implementation slot.

The scenario key must be derived from actual specification
fields, not accepted solely from a caller-supplied hash.

Use deterministic ABI encoding and domain separation.
The domain must pin the comparison semantics version.

The API receives one UpgradeCheck for both stages.
Actor, target, candidate, policy and expected revert
are therefore shared by construction.

Observation does not independently record the policy
or expected revert selected by its producer.
The comparator reevaluates both observations using
the same declared specification.

Two observations must match the declared scenario identity.

In particular:

- Actor must equal the declared actor.
- tx.origin must equal the declared actor.
- Target must equal the declared proxy.
- Calldata must match the canonical declared action.
- Observed implementation slot must be ERC-1967.

Mismatched recorded actor, origin, target, calldata
or implementation slot values are INCOMPARABLE.

An unexpected revert under the shared policy may
produce UNKNOWN rather than INCOMPARABLE.

The comparison cannot establish which policy was
originally intended when an observation was produced.

A matching scenario key proves only internal consistency
of the declared comparison, not authenticity of execution.

## 5. Stage Binding

Each stage declares the expected active implementation
before its isolated probe.

Require:

    observation.implementationBefore
        == expectedActiveImplementation

Require distinct before/after active implementations
for a version-upgrade comparison.

Stage implementation differences are expected.

The following are not part of scenario identity:

- Active implementation version.
- Observed call success or failure.
- Return or revert data.
- Observed state after the call.
- Execution timestamp.

If an observation does not match its declared active
implementation, the result is INCOMPARABLE.

If both stages refer to the same active implementation,
the result is INCOMPARABLE for this comparison API.

The comparison must not claim that an implementation
change caused all observed behavior differences.

Stage binding validates internal consistency only.
It does not authenticate observation provenance
or prove that execution occurred on the claimed
contract version.

The Foundry test must explicitly establish the
version transition and verify the deployed state.
A pure comparator cannot prove that transition.

## 6. Evaluation

Reuse the existing detailed policy evaluator.

Recompute the evaluation independently for each
stage from its recorded Observation and the same spec.

Do not accept supplied PASS or FAIL labels without
checking the underlying observation.

The evaluator remains pure.

Individual result mapping:

    PASS    -> SATISFIED
    FAIL    -> VIOLATED
    UNKNOWN -> INDETERMINATE

PolicyStatus.ERROR is not a valid ordinary comparison
result in phase A.

Execution and setup failures must stop the caller
before comparison input is constructed.

The phase A comparator is pure and receives no
RPC status, runner status or execution-error field.
It cannot independently identify infrastructure
failures from arbitrary recorded observations.

The Foundry runner is responsible for failing
explicitly on preparation or observation errors.
Such errors must never be converted into PASS.

Retain the original PolicyReason for each stage.

## 7. Comparison Table

Before       After        Comparison

PASS         PASS         STILL_SATISFIED
PASS         FAIL         CHANGED_TO_VIOLATION
FAIL         PASS         CHANGED_TO_SATISFIED
FAIL         FAIL         STILL_VIOLATED
UNKNOWN      any valid    INDETERMINATE
any valid    UNKNOWN      INDETERMINATE

Scenario mismatch             INCOMPARABLE
Invalid stage binding         INCOMPARABLE
Identical stage versions      INCOMPARABLE
Execution or setup error      Abort

Precedence:

1. Validate scenario identity and stage bindings.
2. Reject execution/setup errors.
3. Recompute both detailed evaluations.
4. Resolve UNKNOWN to INDETERMINATE.
5. Apply the four definite transitions.

Do not interpret STILL_VIOLATED as a safe result.

Do not interpret STILL_SATISFIED as proof that every
privileged execution path is safe.

CHANGED_TO_VIOLATION establishes a change in the
declared policy verdict for the recorded scenario.
It does not independently prove exploitability
or establish implementation-code causality.

## 8. Meaning of Positive and Negative Properties

Phase A compares existing negative upgrade policies:

- NO_IMPLEMENTATION_REPLACEMENT
- NO_SUCCESSFUL_UPGRADE_CALL

A successful owner upgrade may correctly be classified
FAIL by a policy that forbids successful upgrades.

That does not establish an unauthorized action.

The future Timelock adapter must introduce a separate
positive property for an expected authorized operation.

Do not overload the existing negative policies to
represent successful authorized execution.

## 9. Stage Execution

Phase A does not automatically install implementations
or prepare governance state.

The consumer explicitly establishes:

1. Baseline implementation.
2. Isolated baseline observation.
3. Authorized installation of the new implementation.
4. Isolated updated-version observation.
5. Pure comparison of the two observations.

Use the existing snapshot-isolated direct probe API.

Do not leave candidate implementations installed by
an isolated authorization check.

Preparation and the authorized upgrade between stages
remain explicit in the Foundry test.

No hidden vm.prank authorization grants or vm.warp calls.

## 10. Trust Boundary

The comparison layer receives recorded EVM observations.

It does not establish:

- Authenticity of the EVM execution.
- Correctness of the contract's complete authorization model.
- Causation of a revert.
- Storage-layout compatibility.
- Safety of the installed implementation.
- Exhaustive actor or privileged-action coverage.

A matching expected revert is evidence of rejection
under the declared scenario, not proof of which source
branch performed authorization.

The comparison must preserve UNKNOWN when the existing
evaluator cannot establish a definitive policy outcome.

## 11. Minimal API Usage

The intended user workflow:

    UpgradeCheck memory spec = ...;

    Observation memory beforeObs =
        _checkIsolatedUpgradeDetailed(spec).observation;

    // Consumer performs an authorized upgrade here.

    Observation memory afterObs =
        _checkIsolatedUpgradeDetailed(spec).observation;

    DirectComparisonResult memory comparison =
        _compareDirectUpgrade(
            scenarioId,
            spec,
            DirectStage({
                expectedActiveImplementation: oldImpl,
                observation: beforeObs
            }),
            DirectStage({
                expectedActiveImplementation: newImpl,
                observation: afterObs
            })
        );

The concrete tests must verify that both observations
refer to their declared stage implementations.

The expected external result is a comparison verdict
plus both detailed policy evaluations.

## 12. Required Tests

Positive:

1. PASS to PASS.
2. PASS to FAIL.
3. FAIL to PASS.
4. FAIL to FAIL.
5. Real fixture baseline to risky.
6. Real fixture risky to fixed.
7. Existing direct API remains compatible.

Negative:

8. UNKNOWN before stage.
9. UNKNOWN after stage.
10. Actor mismatch.
11. Target mismatch.
12. Calldata mismatch.
13. Incorrect expected revert produces UNKNOWN and
    therefore INDETERMINATE when rejection evidence
    is insufficient.
14. Invalid implementation slot.
15. Stage implementation mismatch.
16. Identical stage implementations.
17. Malformed or inconsistent observations.
18. Deliberately inverted comparison mapping.

The implementation must include deterministic tests
for the full comparison table.

Fuzzing must cover scenario identity and evaluation
precedence without changing the v0.3 policy semantics.

At least one mutation must show that a defective
comparison mapping is detected by the test suite.

## 13. Evidence

Phase A returns structured Solidity comparison results.

Do not introduce a new public JSON schema solely to
complete the first phase.

A versioned comparison evidence format will be designed
after the Timelock observation model is defined.

No evidence exporter may label a comparison as
cryptographic proof of execution.

## 14. Acceptance Criteria

Phase A is complete only when:

- Existing v0.3 tests and consumers still pass.
- AuthorityProbe production API is unchanged.
- Comparison requires one consistent scenario.
- All four definite transitions are classified correctly.
- UNKNOWN never becomes a definitive PASS or FAIL.
- Incomparable stages are rejected as comparable evidence.
- Stage implementations are explicitly bound.
- The before/after experiment preserves probe isolation.
- Independent mutation tests detect faulty mapping.
- A standalone Foundry consumer exercises the new API.
- The new helper reduces manual comparison boilerplate.

## 15. Deferred Decisions

ADR-004B will specify:

- TimelockController adapter interface.
- RoutedObservation.
- Inner versus outer execution evidence.
- Explicit scheduling and readiness state.
- Snapshot boundaries for controller and proxy.
- Positive authorized-upgrade properties.
- Comparison evidence format for routed execution.

No Timelock API should be implemented in phase A.

## 16. Review Questions

Before accepting this ADR, independently check:

1. Can scenario identity accidentally match
   different actions or policies?
2. Can malformed observations produce a definite verdict?
3. Is the proposed API smaller than manual comparison?
4. Does requiring distinct implementations create
   unacceptable restrictions?
5. Are INCOMPARABLE and INDETERMINATE correctly separated?
6. Can a malicious stage report fabricate its version?
   Does the trust boundary explain this limitation?
7. Is reusing the existing evaluator sufficient?
8. Are any new types or checks unnecessary?

Status remains PROPOSED until reviewed.

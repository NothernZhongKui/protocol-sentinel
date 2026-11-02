# RFC-004C: Comparison Evidence & Independent Replay

Status: DRAFT — architectural review required
Target: Protocol Sentinel v0.4-C
Baseline: merged v0.4-A and v0.4-B
Parent: RFC-004
Dependencies: ADR-004A, ADR-004B

## 1. Problem

Protocol Sentinel currently supports:

1. Direct EOA UUPS authority observations.
2. Direct before/after authority comparison.
3. A real OpenZeppelin Timelock -> ProxyAdmin ->
   Transparent Proxy execution route.
4. Timelock before/after comparison.
5. Pure Solidity evaluation and comparison.

These components can classify local Foundry execution.

However, v0.4-A and v0.4-B comparison observations
do not yet have a portable, versioned JSON evidence
format with independent Python classification replay.

The existing schema 0.4 serves a different purpose:
it records the legacy single direct-authority witness.

It must not be silently reinterpreted as a comparison
schema.

## 2. Goals

Phase C must provide:

- Portable structured comparison evidence.
- Support for both existing execution routes.
- Explicit scenario and stage identities.
- Complete raw observations needed for replay.
- Recorded Solidity statuses and diagnostic reasons.
- Recorded comparison verdict and reason.
- Independent Python re-evaluation.
- Strict schema and type validation.
- Deterministic cross-language classification.
- Negative controls and mutation testing.
- Reproducible local and CI workflows.
- Compatibility with existing releases.

The primary result is independently reproducible
classification, not authenticated execution.

## 3. Non-goals

Phase C does not implement:

- New governance adapters.
- New authorization policies.
- Automatic permission discovery.
- On-chain transaction execution.
- Cryptographic proof of EVM execution.
- Zero-knowledge execution attestations.
- A general-purpose blockchain indexer.
- A new RPC-dependent verification service.
- A universal security audit report.
- A replacement for Foundry.

No public Solidity execution API changes are required
to introduce the evidence pipeline.

## 4. Compatibility

The following existing APIs remain unchanged:

- AuthorityProbe
- ComparativeAuthorityProbe
- TimelockAuthorityProbe

The existing scripts/replay_policy.py and its
schema versions 0.2, 0.3 and 0.4 remain compatible.

Do not extend legacy schema 0.4 with optional fields
that create ambiguity between single-policy witnesses
and comparison evidence.

Introduce a separate comparison artifact namespace.

## 5. Recommended Evidence Envelope

Proposal:

    format: "protocol-sentinel-comparison"
    schema_version: "1.0"

This is a separate format version, not a replacement
for legacy authority witness schema 0.4.

Top-level sections:

    format
    schema_version
    route
    scenario
    stages
    comparison
    environment
    provenance
    limitations

The validator must use strict per-route field definitions.

Unknown top-level and nested fields are rejected by default.

No inference of missing fields from defaults.

The concrete JSON Schema and serialization details
remain open until ADR-004C.

## 6. Route Discriminator

Supported route values:

    DIRECT_EOA_UUPS
    OZ_TIMELOCK_SINGLE

Each route has its own required scenario fields,
observation fields, policy semantics and reasons.

The discriminator must prevent interpreting
Timelock evidence as direct EOA evidence.

Unsupported routes cause a schema error.

A route-specific observation must not be
accepted merely because it contains a subset
of the fields from another route.

## 7. Common Scenario

Required concepts:

- Explicit scenario ID.
- Computed scenario key.
- Route discriminator.
- Declared policy/property.
- Expected target and initiating actor.
- Canonical execution calldata.
- Relevant implementation slot.
- Route semantic version.

The scenario key must be recomputed during replay.

A supplied key cannot establish scenario identity
without checking its underlying fields.

The existing Solidity domain-separated key formulas
remain authoritative for compatibility.

Do not introduce a second incompatible identity formula.

## 8. Direct Scenario

For DIRECT_EOA_UUPS, preserve all inputs required by
the existing UpgradeCheck and direct comparison logic.

Required declaration:

- scenarioId
- actor
- target
- candidate
- expectedRevert
- UpgradePolicy
- canonical upgradeToAndCall calldata
- ERC-1967 implementation slot

Required observations per stage:

- actor
- txOrigin
- target
- success
- returnData
- callData
- observedSlot
- implementationBefore
- implementationAfter
- candidateValidAtObservation
- targetValidAtObservation

Store the complete PolicyEvaluation for each stage.

The Python replay must independently reproduce
PolicyStatus and PolicyReason using the precise
current Solidity evaluation order.

## 9. Timelock Scenario

For OZ_TIMELOCK_SINGLE, preserve the complete
TimelockScenario declaration:

- timelock
- proposer
- executor
- proxyAdmin
- proxy
- candidate
- predecessor
- salt
- property

Also record the canonical inner upgrade action,
canonical outer execute action and operationId.

Recompute the operation ID from the actual tuple:

    proxyAdmin
    value = 0
    upgradeAndCall payload
    predecessor
    salt

The route uses the pinned OpenZeppelin semantics.

The declared proposer does not authenticate
historical scheduling provenance.

## 10. Timelock Observations

Retain the full RoutedObservation from each stage.

Required groups:

Execution context:
- executor
- txOrigin
- executorEOAObserved
- executorEOAValid
- outerTarget
- outerCallData

Execution result:
- outerSuccess
- returnData

Operation identity:
- timelock
- proxyAdmin
- operationId

Operation state:
- operationStateBefore
- operationStateBeforeObserved
- operationDoneBefore
- operationDoneAfter

Predecessor:
- predecessor
- predecessorStateObserved
- predecessorDoneBefore

Time:
- observedTimestamp
- readyAt

Proxy effect:
- observedSlot
- implementationBefore
- implementationAfter

Preconditions:
- proxyCodeObserved
- proxyHasCode
- candidateCodeObserved
- candidateHasCode
- proxyAdminOwnershipObserved
- proxyAdminOwnedByTimelock
- executorRolesObserved
- executorHasRole
- openExecutorRole

Missing fields are schema errors.

Explicitly recorded false observation flags may
produce UNKNOWN under the Solidity evaluator.

These two cases must remain distinguishable.

## 11. Stage Representation

The artifact contains exactly two ordered stages:

    before
    after

Each stage includes:

- expectedActiveImplementation
- complete raw observation
- recorded policy evaluation
- recorded diagnostic reason

The two stages use the same declared scenario.

The active implementation may differ between stages
and must not be included in the shared scenario key.

Implementation identity uses the lower 160 bits of
the ERC-1967 storage word, matching Solidity.

The serialized data must preserve the complete
original bytes32 storage word.

Never silently truncate the stored evidence.

## 12. Comparison Result

Required recorded fields:

- scenarioKey
- verdict
- reason

Supported verdicts:

- STILL_SATISFIED
- CHANGED_TO_VIOLATION
- CHANGED_TO_SATISFIED
- STILL_VIOLATED
- INDETERMINATE
- INCOMPARABLE

Route-specific reasons must remain distinct:

- ComparisonReason for direct execution.
- RoutedComparisonReason for Timelock execution.

The Python comparison implementation must independently
recompute both individual evaluations first.

It must then apply the existing Solidity precedence
rules for comparability and verdict classification.

A claimed INCOMPARABLE result must retain the
two original evaluated statuses and reasons.

UNKNOWN must never be silently converted into PASS.

## 13. Preparation Failures

The Timelock evaluator may revert
InvalidTimelockPreparation for known invalid setup.

An invalid preparation must not be represented
as an ordinary PASS, FAIL or UNKNOWN verdict.

An aborted run cannot emit a valid completed
comparison artifact.

Optional diagnostic reports for aborted runs
must use a separately declared artifact kind.

Such diagnostic reports are not successful
comparison evidence and cannot pass replay.

Infrastructure failure and failed snapshot restoration
must also abort the witness generation process.

## 14. Serialization Rules

Recommended encoding:

- Addresses: 0x-prefixed 20-byte hexadecimal strings.
- bytes32: 0x-prefixed 32-byte hexadecimal strings.
- Dynamic bytes: even-length 0x-prefixed hexadecimal.
- Booleans: JSON true or false only.
- Enums: exact stable symbolic identifiers.
- uint256: canonical unsigned decimal strings.
- Route and schema identifiers: exact strings.

No JSON floating-point encoding for EVM integers.

Avoid numeric enum ordinals in the evidence format.

JSON must reject duplicate object keys.

The validator must reject:

- Invalid hex and incorrect fixed widths.
- Unrecognized enum labels.
- Negative or overflowing integers.
- Noncanonical decimal encodings.
- Missing required fields.
- Unknown fields.
- Incorrect stage cardinality.
- Incorrect route discriminator.
- Schema-version mismatches.

Byte-level JSON canonicalization is not itself
proof of execution and is not required for initial replay.

## 15. Independent Replay

The replay tool must not trust stored evaluation
or comparison statuses.

Proposed conceptual steps:

1. Parse JSON with duplicate-key rejection.
2. Validate exact schema and primitive types.
3. Reconstruct the declared scenario.
4. Recompute canonical calldata and scenario key.
5. Recompute the policy evaluation for each stage.
6. Validate stage and governance comparability.
7. Recompute comparison verdict and reason.
8. Compare every recomputed output with the recorded one.
9. Reject any mismatch or invalid preparation.
10. Emit a narrowly scoped verification report.

Python logic must be implemented independently
from Solidity, not by invoking the Solidity evaluator.

The replay does not require RPC or new EVM execution.

It may use a narrowly scoped Keccak-256 utility
for identity and calldata verification.

The cryptographic implementation/dependency choice
is an explicit architectural decision.

Python SHA3-256 must not be confused with
Ethereum Keccak-256.

## 16. Cross-language Fidelity

A Python replay implementation must match the
actual Solidity implementation, including:

- Validation order.
- UNKNOWN reason precedence.
- Preparation error precedence.
- Exact Waiting/Ready time boundaries.
- Timelock predecessor handling.
- Executor eligibility and EOA evidence.
- Exact revert selector and arguments.
- State consistency checks.
- Implementation address masking.
- Stage identity.
- Governance-preparation comparability.
- Final comparison reason precedence.

The Solidity implementation is the behavioral
reference for the first schema version.

A mismatch is a verification failure.

Do not silently adjust Python rules to make a
specific witness pass without a regression test.

## 17. Execution Provenance

Record the environment required to reproduce
the local experiment:

- Repository identifier.
- Source commit SHA.
- Working-tree cleanliness status.
- Source file hashes or equivalent manifest.
- Foundry version.
- Solidity compiler version.
- OpenZeppelin dependency revisions.
- Chain ID.
- Execution mode: local fixture or fork.
- Relevant fork block information when applicable.
- Adapter semantic version.
- Evidence schema version.
- Reproduction command and fixture identity.

Environment metadata are assertions supplied
by the producing test environment.

A validator can check their structure and
optionally compare them with a local checkout.

They are not cryptographically authenticated
merely because they appear in JSON.

No private RPC URLs, secrets or credentials
may enter the evidence artifact.

## 18. Validation Levels

Separate three concepts.

Level 1: Schema validity

- Well-formed complete typed data.
- No unexpected fields or duplicates.
- Correct supported format version.

Level 2: Classification replay

- Independent recomputation of policy results.
- Independent recomputation of comparison.
- Exact agreement with recorded statuses/reasons.

Level 3: Reproduction context

- Locally checkable source and tool metadata.
- Consistency with the declared fixture and execution mode.
- Explicitly identified unverified provenance claims.

A successful Level 2 result must not be described
as independent proof of EVM execution.

The result should say classification reproduced,
not execution authenticated.

## 19. Export Architecture

Prefer an explicit, opt-in Foundry witness export.

The producer should:

- Prepare the scenario.
- Execute isolated observations.
- Retain the actual returned Solidity structures.
- Evaluate and compare them.
- Serialize those results without recomputing
  or inventing execution outcomes in the exporter.
- Write an artifact only after successful completion.

The Python side validates and independently replays
the recorded results.

Avoid a Python exporter constructing synthetic
observations from expected outcomes.

Avoid modifying the existing legacy exporter.

Use separate output paths under artifacts/comparison/.

Do not silently overwrite previous run artifacts.

## 20. Initial Test Matrix

Direct comparison:

- PASS -> PASS
- PASS -> FAIL
- FAIL -> PASS
- FAIL -> FAIL
- UNKNOWN -> INDETERMINATE
- Scenario mismatch -> INCOMPARABLE
- Stage mismatch -> INCOMPARABLE

Timelock comparison:

- Real Ready operation preserving PASS.
- Real Waiting rejection preserving PASS.
- Incomplete evidence -> UNKNOWN.
- Invalid preparation -> export abort.
- Changed executor roles -> INCOMPARABLE.
- Different readyAt -> INCOMPARABLE.
- Same implementation -> INCOMPARABLE.
- Wrong operationId -> INCOMPARABLE.
- Wrong revert bytes -> appropriate UNKNOWN.
- Missing EOA evidence -> UNKNOWN.
- Non-EOA executor -> invalid preparation.

Negative controls:

- Remove a required field.
- Add a forbidden field.
- Duplicate a JSON key.
- Change an address or operation salt.
- Alter canonical calldata.
- Falsify one individual result.
- Falsify a diagnostic reason.
- Falsify the comparison verdict.
- Falsify comparison reason.
- Replace a stage implementation.
- Corrupt a source hash.
- Invert a policy mapping.
- Skip the producing test.
- Truncate the artifact.
- Supply an unsupported schema version.

Mutation testing must show that deliberate classifier
errors are detected by the independent replay suite.

## 21. CI Acceptance

Required CI workflow:

1. Build pinned Solidity project.
2. Execute required evidence-producing tests.
3. Verify actual execution of every required test.
4. Reject zero, missing or skipped executions.
5. Generate fresh direct and routed evidence.
6. Validate schema and replay all generated artifacts.
7. Run Python negative controls.
8. Run cross-language classification mutations.
9. Report the specific verified scope.

CI must not rely on a stale artifact committed
from an earlier successful execution.

The result must fail closed if any required artifact
or test is absent.

No archive RPC required for baseline CI.

## 22. Security and Trust Boundary

The evidence format does not prove:

- Actual EVM execution provenance.
- Ownership of an EOA private key.
- Historical scheduling authorship.
- Universal ProxyAdmin identity.
- Absence of alternative privilege paths.
- Causality between code changes and outcomes.
- Contract security beyond declared properties.

The existing Timelock observer deliberately fails
closed on an altered ERC-1967 admin storage slot.

Replay must preserve this scope limitation.

It must not reinterpret the slot as independent
proof of the effective immutable ProxyAdmin.

A fabricated but internally coherent JSON document
can still satisfy classification replay.

The format is for reproducible testing,
not a cryptographic execution certificate.

## 23. Recommended Implementation Slices

C1: Format and semantics

- Accept schema and route discriminators.
- Define mandatory per-route fields.
- Establish fixed serialization conventions.
- Resolve Keccak and ABI recomputation strategy.

C2: Direct comparison evidence

- Export real direct observations.
- Replay direct evaluation and comparison.
- Add negative controls.

C3: Timelock comparison evidence

- Export real routed observations.
- Replay route preparation and evaluation.
- Replay routed comparison.
- Add adversarial negative controls.

C4: CI and documentation

- Fresh artifact generation.
- Mandatory test-execution verification.
- Cross-language mutation tests.
- Independent consumer evidence example.
- Reproduction instructions.

Do not introduce new authority adapters in phase C.

## 24. Open Architecture Questions

Review before ADR-004C:

Q1. Is one discriminated comparison schema preferable
to separate direct and routed schema families?

Q2. Is schema_version "1.0" appropriate for the new
comparison namespace, independently of legacy 0.4?

Q3. Should v1 use standard-library Python plus
Foundry cast for Keccak, or a pinned Python dependency?

Q4. How should the source revision and dirty tree
be handled during local development and CI?

Q5. Which exact metadata are mandatory and which
are optional but validated when present?

Q6. What is the minimal Foundry serializer API that
avoids duplicating existing scenario logic?

Q7. Should the initial pipeline export successful
comparison results only, with abort reports separate?

Q8. Should route-specific semantic versions be
explicitly recorded in addition to schema version?

Q9. How should the replay report distinguish schema
validity, classification equivalence and provenance?

Q10. Which additional mutation controls best detect
false PASS and false comparative verdicts?

## 25. Acceptance Criteria

v0.4-C is acceptable when:

- Legacy single-witness schema 0.4 remains compatible.
- Existing Solidity APIs remain source-compatible.
- Both direct and routed comparisons export evidence.
- All evidence fields needed for replay are retained.
- Missing fields cannot silently default to PASS.
- Both stage evaluations are independently reproduced.
- Comparison verdict and reason are reproduced.
- Invalid preparation cannot masquerade as FAIL.
- INCOMPARABLE retains genuine individual evaluations.
- Scenario key and canonical calldata are recomputed.
- Unexpected schema versions fail closed.
- CI verifies required test execution, not only exit codes.
- Deliberately mutated evidence is rejected.
- No unsupported execution-authenticity claims are made.
- Independent consumers can reproduce the workflow.

## 26. Review Request

An independent architecture review should examine:

1. Schema completeness against actual Solidity structs.
2. Threats from ambiguous or fabricated evidence.
3. Python/Solidity semantic divergence.
4. ABI and Keccak implementation correctness.
5. Treatment of invalid preparation.
6. Stage identity and governance comparability.
7. Backward compatibility.
8. Failure behavior under malformed evidence.
9. Minimum practical implementation scope.
10. Whether the architecture is unnecessarily complex.

Status remains DRAFT until ADR-004C is accepted.

# ADR-004C: Comparison Evidence and Independent Replay

Status: ACCEPTED
Target: Protocol Sentinel v0.4-C
Parent: RFC-004C
Dependencies: ADR-004A, ADR-004B
Reference implementation: merged v0.4-B
Initial reviewed code commit:
3d9c31dcf9a10a2bea0eb497edffecaafdffdfbe

## 1. Decision

Introduce an independent comparison evidence pipeline.

The pipeline records actual Solidity observations,
their Solidity-computed evaluations, and the final
Solidity-computed comparison result.

Python independently reconstructs the declared scenario,
recomputes evaluation and comparison, and checks equality
with the recorded outputs.

Classification reproduction is not authentication
of execution provenance.

Do not modify the existing core Solidity APIs.

## 2. Format Namespace

Use a separate comparison evidence format:

    format = "protocol-sentinel-comparison"
    schema_version = "1.0"

Legacy witness schemas 0.2, 0.3 and 0.4 retain
their existing independent semantics.

No implicit migration or legacy fallback.

## 3. Common Envelope

Required top-level concepts:

    format
    schema_version
    route
    semantics_version
    scenario
    stages
    comparison
    environment
    provenance

Route-defined limitations are supplied by the
frozen semantic manifest.

They are not arbitrary assertions of security.

The concrete schema must define exact field names,
types, and allowed values before implementation.

Reject unknown and missing required fields.

Use one strict envelope with separate route branches.

The route branches are mutually exclusive.

## 4. Route Discriminator

Initial route identifiers:

    DIRECT_EOA_UUPS
    OZ_TIMELOCK_SINGLE

Each route has its own scenario, raw observation,
evaluation reason, comparison reason and semantics.

Do not allow a valid direct record to be interpreted
as a Timelock record or vice versa.

## 5. Semantics Versioning

Dispatch replay using:

    (
        format,
        schema_version,
        route,
        semantics_version
    )

The first supported route semantics are frozen to
the reviewed Solidity implementations.

For every semantics version maintain a manifest with:

- Reference source commit.
- Exact Solidity evaluation and comparison functions.
- Validation and diagnostic precedence.
- Domain separators.
- Exact ABI argument types and ordering.
- Enum symbolic-to-numeric mappings.
- Canonical calldata rules.
- Positive and negative test vectors.
- Known scope and trust limitations.

A code change that changes classification semantics
requires a new semantics version.

Changing JSON structure requires a schema version change.

A new schema need not imply new policy semantics.

Unknown semantics versions are rejected.

Do not silently apply the current replay rules
to an artifact produced using older semantics.

## 6. Ethereum ABI and Keccak

Use pinned Python packages:

    eth-abi
    eth-hash[pycryptodome]

Resolve exact versions and dependency hashes
during C1 before implementation.

Python replay must not require Foundry, cast or RPC
to classify an existing evidence artifact.

Use Ethereum Keccak-256, not Python SHA3-256.

ABI computations must exactly reproduce Solidity.

For direct comparison, reproduce:

    DIRECT_COMPARISON_DOMAIN
    scenarioId
    actor
    target
    candidate
    canonical calldata
    expectedRevert
    UpgradePolicy enum ordinal
    ERC1967_IMPL_SLOT

For Timelock operation identity, reproduce:

    proxyAdmin
    uint256(0)
    canonical ProxyAdmin calldata
    predecessor
    salt

For Timelock comparison identity, reproduce:

    TIMELOCK_COMPARISON_DOMAIN
    scenarioId
    complete TimelockScenario ABI tuple
    operationId
    canonical Timelock execute calldata
    ERC1967_IMPL_SLOT

TIMELOCK_ROUTE_DOMAIN must not be substituted
for TIMELOCK_COMPARISON_DOMAIN.

The scenario key uses Solidity ABI encoding,
not a hash of serialized JSON.

Mandatory ABI vectors cover expectedRevert lengths:

    0, 1, 31, 32, 33 bytes

Additional vectors cover nested dynamic calldata,
operation ID and both route scenario keys.

Use cast as an optional independent test oracle only.

## 7. Serialization Rules

Addresses are exact 20-byte hex values.

bytes32 uses exact 32-byte hex values.

Dynamic bytes use even-length 0x-prefixed hex.

Booleans must be actual JSON booleans.

Enums are stable symbolic strings in JSON.

The ABI layer maps enums to frozen numeric ordinals.

uint256 values are canonical unsigned decimal strings.

No JSON floats for EVM integer quantities.

Reject duplicate JSON keys.

Reject noncanonical decimal values, invalid widths,
overflow, unknown enum values and missing fields.

Hex case differences are permitted where bytes
are semantically identical.

Store raw implementation words without truncation.

For address comparisons mask to the lower 160 bits,
matching the reference Solidity implementation.

## 8. Scenario and Observation Boundaries

Distinguish three categories.

A. Declared and derived data

- Scenario fields.
- Canonical action calldata.
- Timelock operation ID derived from the declaration.
- Domain-separated scenario key.

These values must be recomputed and validated.

B. Raw observations

- Original actor, target and calldata.
- Original observed operation ID.
- Original operation readiness.
- Original implementation storage words.
- Original validity and eligibility flags.
- Original outer execution result.

These must be preserved without repair.

A validly typed observed value may differ from
its declared scenario counterpart.

Such disagreement is classifier input,
not automatically a schema error.

C. Recorded classification

- Stage evaluation statuses and reasons.
- Final comparison verdict and reason.

These are untrusted claims checked against replay.

Do not overwrite obs.operationId using a newly
computed operation ID.

Do not normalize observed actor, calldata or target
to declared expectations.

## 9. Stage Representation

Use a JSON object with exactly two required members:

    before
    after

Object key order has no significance.

Each stage contains:

    expectedActiveImplementation
    observation
    evaluation

The evaluation contains:

    status
    reason

There is exactly one recorded evaluation per stage.

Export it from the returned comparison result:

    comparison.beforeEvaluation
    comparison.afterEvaluation

Do not substitute separately cached evaluations
calculated under potentially different scenarios.

The top-level comparison stores:

    scenarioKey
    verdict
    reason

Avoid duplicating the same recorded result
across multiple JSON locations.

## 10. Exact Replay Precedence

The Python implementation reproduces the frozen
Solidity control flow, not an improved interpretation.

For direct comparison:

1. Evaluate the before observation.
2. Evaluate the after observation.
3. Reject PolicyStatus.ERROR.
4. Check scenario identity in both stages.
5. Check expected active implementation bindings.
6. Check that stage implementations differ.
7. Resolve UNKNOWN to INDETERMINATE.
8. Map the four definitive status transitions.

For Timelock comparison:

1. Evaluate the before observation.
2. Evaluate the after observation.
3. Respect any InvalidTimelockPreparation revert.
4. Reject PolicyStatus.ERROR.
5. Check scenario identity in both stages.
6. Check expected stage implementation bindings.
7. Check that stage implementations differ.
8. Compare recorded governance preparation.
9. Resolve UNKNOWN to INDETERMINATE.
10. Map definitive status transitions.

For each evaluator reproduce all internal checks
in their actual Solidity source order.

Do not pre-scan preparation flags independently.

For example, context mismatch may return UNKNOWN
before a later invalid EOA preparation check.

An evaluation whose required evidence is explicitly
unobserved may be UNKNOWN.

A missing required JSON field is a schema error.

The two cases must not be merged.

## 11. Timelock Invalid Preparation

Known invalid preparation is not a policy FAIL.

If the frozen evaluator would revert
InvalidTimelockPreparation, replay rejects the
artifact as an invalid completed comparison.

The producer must not publish a normal completed
comparison record for an aborted evaluation.

Role configuration drift has distinct outcomes:

- Both stages remain eligible:
  comparison may be INCOMPARABLE.
- Either stage becomes ineligible:
  evaluation aborts under the frozen rules.
- Eligibility evidence is not observed:
  UNKNOWN is possible, subject to earlier checks.

A schema validator must not replace these
semantic decisions with global boolean checks.

## 12. Completed Comparison Outcomes

Every successfully completed Solidity comparison
is eligible for evidence export.

This includes:

    STILL_SATISFIED
    CHANGED_TO_VIOLATION
    CHANGED_TO_SATISFIED
    STILL_VIOLATED
    INDETERMINATE
    INCOMPARABLE

The result's security meaning is independent
of successful evidence classification replay.

A replay MATCH does not mean policy PASS.

An INCOMPARABLE result may be faithfully reproduced
and still represent a successful replay.

## 13. Export and Publication Boundary

Foundry writes provisional evidence only.

An external runner owns the completed publication
decision.

Required sequence:

1. Create a unique staging directory for this run.
2. Execute producing tests with explicit export opt-in.
3. Capture the Forge JSON test result.
4. Require successful process exit.
5. Require every named test with status Success.
6. Reject missing, skipped or failed required tests.
7. Require precisely the expected artifact set.
8. Validate schema and replay each artifact.
9. Verify the run's locally checkable metadata.
10. Atomically publish the completed run directory.

Never reuse artifacts left by a previous run.

A failure may retain staging files for debugging,
but they must not appear as completed evidence.

The test case "file written, then producing test fails"
must not produce a completed published run.

Do not depend only on the presence of vm.writeJson output.

## 14. Replay Verification Report

Report separate dimensions:

    schema
    classification_replay
    comparison
    source_context
    execution_provenance

Example:

    schema: VALID
    classification_replay: MATCH
    comparison: CHANGED_TO_VIOLATION
    source_context: NOT_CHECKED
    execution_provenance: UNAUTHENTICATED

Do not report execution as authenticated solely
from matching JSON, hashes or scenario keys.

CI may separately assert an expected comparison
verdict for a known fixture.

That assertion is not part of generic replay success.

## 15. Provenance and Source Context

Record:

- Repository and source commit.
- Exact source input hashes.
- Working-tree cleanliness.
- Fixture identifier.
- Execution mode and chain ID.
- Forge, compiler and relevant dependency revisions.
- Adapter semantics version.
- Reproduction command.

For a fork also record original chain block number
and block hash independently from warped execution time.

CI must use a clean checkout.

Local development may use a dirty working tree,
provided the actual source inputs are hashed
and the dirty status is disclosed.

A well-formed but incorrect source hash cannot
be identified by classification replay alone.

It requires comparison with trusted or local source.

No secrets, private RPC URLs or credentials
may enter the artifact.

## 16. Validation and Mutation Categories

Category A — mandatory rejection:

- Malformed or truncated JSON.
- Duplicate or unknown fields.
- Missing required fields.
- Wrong schema or semantics version.
- Wrong derived scenario key.
- Wrong declared canonical operation identity.
- Forged evaluation status or reason.
- Forged comparison verdict or reason.
- Aborted or skipped required tests.

Category B — valid changed observation:

- Actor differs from the declared actor.
- Recorded operationId differs from scenario.
- Observed revert changes.
- Eligibility evidence is unavailable.

These may legitimately produce UNKNOWN,
INDETERMINATE or INCOMPARABLE.

Category C — semantics-preserving changes:

- Upper 96 bits of implementation word change
  without changing address identity where Solidity
  uses only the address.
- Hexadecimal case changes.
- JSON object key ordering changes.

These must retain the correct classification.

Add cases with multiple simultaneous defects
to test precedence.

Add intentional classifier mutations to ensure
the cross-language oracle detects semantic drift.

## 17. Implementation Sequence

C1 — Schema and frozen semantics

- Exact strict per-route schema.
- Semantics registry.
- ABI/Keccak dependency lock.
- Golden Solidity/Python identity vectors.
- Negative controls for format errors.

C2 — Direct end-to-end slice

- Real Foundry direct comparison export.
- Python direct evaluator and comparator replay.
- Fresh runner with staging and publication boundary.
- JSON test-status enforcement.
- Minimal CI acceptance.
- At least one multi-defect precedence test.

C3 — Timelock route

- Full routed raw observation export.
- Python routed evaluator and comparator replay.
- Timelock operation ID and calldata validation.
- Eligibility, predecessor and timing edge cases.
- Preparation-abort controls.

C4 — Hardening

- Route-wide mutation matrix.
- Additional cross-language vectors.
- Independent external consumer reproduction.
- Full CI integration.
- Documentation and compatibility checks.

Do not start new execution adapters during phase C.

## 18. Compatibility

Keep unchanged:

    src/AuthorityProbe.sol
    src/ComparativeAuthorityProbe.sol
    src/TimelockAuthorityProbe.sol

No public Solidity API migration is needed.

Retain historical legacy witness behavior.

Do not import legacy target-validity assumptions
into comparison schema 1.0.

Keep comparison evidence logic separate from
the existing single-witness replay tool.

## 19. Acceptance Criteria

The ADR is implementable when:

- Both route schema branches are complete.
- Reference semantics are frozen and versioned.
- Scenario keys and canonical calls are reproducible.
- Raw observations remain unmodified.
- Both evaluations are independently recomputed.
- Comparison reasons and verdicts match Solidity.
- Invalid preparation does not become policy FAIL.
- Known noncomparable observations remain representable.
- Completed non-PASS comparisons may replay successfully.
- Source metadata is not mistaken for authenticated proof.
- Publication requires a successful external runner.
- Skipped and absent producing tests cause failure.
- Legacy schemas remain backward compatible.
- Python replay does not require Foundry or RPC.
- All required negative and positive controls pass.

## 20. Decision Status

ACCEPTED after independent architectural review.

The reference behavior is fixed to the reviewed
v0.4-B implementation for architectural planning.

Accept this ADR before writing the production
comparison evidence exporter and replay pipeline.

The next implementation milestone is C1 followed by
a complete direct end-to-end C2 slice.

# RFC-005: Portable Evidence Workflow & CI Policy Gate

Status: PROPOSED — architecture reviewed, decisions pending
Review revision: 2 — external-consumer-first approach
Target: Protocol Sentinel v0.5
Baseline: released v0.4.1
Dependencies: RFC-004C, ADR-004A, ADR-004B, ADR-004C

## 1. Problem

Protocol Sentinel v0.4.1 provides execution-based
authority regression tests, before/after comparison,
strict Evidence 1.0, independent Python replay,
build provenance and independent compiler reproduction.

These capabilities are verified against the project's
own Direct and Timelock scenarios.

The public Solidity helpers are reusable, but the
complete evidence workflow is not yet portable.

The current implementation embeds project-specific
assumptions in multiple locations:

- Fixed producing Solidity test names and suites.
- Fixed fixture IDs and comparison expectations.
- Fixed repository identity and source manifests.
- Fixed source and artifact directory layouts.
- Fixed OpenZeppelin and forge-std gitlinks.
- Separate Direct and Timelock runner orchestration.
- Demonstration-specific publication verification.

An external consumer cannot currently supply its
own project, producer and scenario using a stable
integration interface.

The current pipeline also stops at verification.
A classification MATCH does not decide whether a
change should be permitted to merge.

For example:

    classification_replay = MATCH
    comparison = CHANGED_TO_VIOLATION

This is a correctly reproduced authority regression,
not an acceptable CI outcome.

## 2. Objective

Enable an independent Foundry project to produce
verifiable authority regression evidence for its
own contracts without forking Protocol Sentinel or
copying its internal Python orchestration.

The end-to-end workflow is:

    External Foundry project
        |
        v
    Declared actor, action and comparison scenario
        |
        v
    Protocol Sentinel Solidity execution helper
        |
        v
    Raw observation and comparison capture
        |
        v
    Portable evidence assembly and publication
        |
        v
    Independent Python verification
        |
        v
    Separate CI policy decision
        |
        +-- PASS
        +-- BLOCK
        +-- REVIEW

Success requires the complete workflow to operate
inside an independently maintained consumer repository.

## 3. Non-goals

v0.5 does not require:

- A new authority policy.
- A new governance execution adapter.
- Safe, AccessManager or arbitrary executor support.
- Automatic actor or privilege-path discovery.
- Live-chain monitoring or transaction submission.
- Remote or cloud execution infrastructure.
- A general-purpose Solidity compiler wrapper.
- A standalone hosted security service.
- A new universal evidence format.
- Cryptographic authentication of EVM execution.
- Generation of Solidity and Python evaluators
  from a common classification implementation.
- A mandatory PyPI package or custom GitHub Action.

The existing core Solidity interfaces and frozen
route semantics must remain compatible.

## 4. Architectural Principles

### 4.1 Independent responsibilities

Separate three responsibilities:

Execution:
- Execute a declared action using the supported
  Solidity observer.
- Preserve actual observations and comparison results.

Verification:
- Validate source capture and evidence structure.
- Verify lossless serialization.
- Independently reproduce classification.
- Verify required provenance and compiler outputs.

Policy decision:
- Interpret a verified comparison against a
  separately supplied CI acceptance policy.
- Produce PASS, BLOCK or REVIEW.

These responsibilities must not share an implicit
success flag.

### 4.2 Route-specific semantics remain independent

Keep the existing route-specific Solidity helpers
and Python evaluators.

Shared orchestration must not introduce a generic
replacement for their classification algorithms.

New abstractions are permitted for:

- Producer execution and status verification.
- Capture and artifact management.
- Source and build provenance.
- Atomic publication.
- Verification report aggregation.

### 4.3 Fail closed

Missing, malformed, skipped or failed producer
executions cannot produce completed evidence.

Invalid schema, failed lossless checks, failed
classification replay or failed required compiler
reproduction cannot produce a positive CI decision.

### 4.4 Versioned consumer interface

The external integration interface requires
explicit versioning independent of the Solidity
evaluation semantics.

A change to the consumer interface must not
silently change the meaning of Evidence 1.0.

## 5. Existing Capabilities to Reuse

The implementation should build on:

- `src/AuthorityProbe.sol`
- `src/ComparativeAuthorityProbe.sol`
- `src/TimelockAuthorityProbe.sol`
- `scripts/validate_comparison_schema.py`
- `scripts/replay_direct_comparison.py`
- `scripts/replay_timelock_comparison.py`
- `scripts/build_provenance.py`
- `scripts/replay_build_compilation.py`

The existing Direct and Timelock runners are
reference implementations, not the intended
public interface for external consumers.

The existing comparison evidence format is:

    format = protocol-sentinel-comparison
    schema_version = 1.0

Supported routes:

    DIRECT_EOA_UUPS
    OZ_TIMELOCK_SINGLE

Do not change the recorded observation semantics
to accommodate external projects.

## 6. Consumer Installation Boundary

The consumer should use a pinned Protocol Sentinel
release within its Foundry project.

The initial packaging mechanism may be a Git
dependency with a versioned Python CLI entry point
located within the installed Sentinel repository.

The consumer must not copy internal Sentinel
Python scripts into its own repository.

The consumer may provide:

- Its own Solidity contracts and test fixtures.
- Its own producer test using a documented export API.
- A small versioned Sentinel configuration.
- A separate CI gate policy.

Foundry and Python dependencies must be documented
and independently installable.

The initial implementation may rely on the pinned
tool versions used by v0.4.1.

## 7. External Producer Contract

An external producer is a declared Foundry test
that invokes a supported Sentinel Solidity helper
and exports genuine execution observations.

The consumer owns:

- Its test contract and fixture.
- Its scenario ID.
- Its actor and target.
- Its before and after implementations.
- Its upgrade candidates and expected rejection.
- Any required governance preparation.

Sentinel owns:

- The supported route capture convention.
- Safe output path selection.
- Strict producer status verification.
- Conversion of raw capture into Evidence.
- Preservation and verification of observed data.

The initial implementation should provide a small
route-specific export adapter instead of requiring
the consumer to reproduce the internal serializers.

The exporter must not invent observations, repair
mismatched context or construct expected outcomes.

An external producer may emit a valid security FAIL.
It must not be required to assert a security PASS
in order to complete the producing Foundry test.

This distinction is essential for CI policy gating.

### Direct actor admission

The public Direct producer path must reject a
contract actor before executing the probe.

The EOA-only contract must be checked at the
observer or public convenience API boundary.

Existing frozen evidence classification semantics
must not be silently redefined by admission checks.

The first consumer must demonstrate rejection of
an unsupported contract actor.

## 8. Producer Identity and Selection

The consumer configuration identifies an exact
producing test and supported route.

The runner verifies:

- Successful Forge process exit.
- Exact expected producing test identity.
- Status Success for every required producer.
- No missing, skipped or failed required producer.
- No unexpected producer replacing the declared one.
- Expected number of exported raw captures.
- Exact association of capture with run identity.

Avoid arbitrary shell command execution in
declarative producer configuration.

Producer selection must be unambiguous.

Multiple scenarios may be supported through
multiple explicit producer declarations.

The first implementation may support one Direct
scenario per producer execution.

## 9. Proposed Consumer Configuration

Illustrative interface only; not implemented:

    [sentinel]
    config_version = "1"
    evidence_route = "DIRECT_EOA_UUPS"

    [[producer]]
    id = "operator-upgrade-regression"
    test_contract = "ConsumerAuthorityTest"
    test_name = "test_ExportOperatorComparison"
    fixture_id = "consumer-vault-v1-to-v2"

The exact names, schema and location are subject
to ADR-005A.

The consumer must not provide expected policy
verdicts as a substitute for actual observations.

All paths must be resolved relative to the
consumer checkout, with traversal and symlink
escape checks.

## 10. Portable Evidence Pipeline

The shared runner should:

1. Resolve and validate consumer configuration.
2. Identify the consumer checkout and installed
   Sentinel version.
3. Create a unique run-local staging directory.
4. Execute precisely the required producing tests.
5. Verify actual Forge process and test statuses.
6. Capture the exact raw Solidity output.
7. Validate the route-specific raw capture.
8. Assemble strict Evidence 1.0.
9. Verify lossless raw-to-evidence mapping.
10. Run the independent route-specific Python replay.
11. Verify source and dependency provenance.
12. Capture fresh compiler build-info.
13. Bind Evidence to the build manifest.
14. Independently reproduce required compiler outputs.
15. Produce a verification report.
16. Atomically publish the verified run.

An unsuccessful step must prevent publication.

The runner must not consume a previous run's
completed artifacts as a substitute for fresh output.

A successful publisher does not certify EVM
execution authenticity.

## 11. Portable Source and Dependency Provenance

v0.4.1 checks source contents and known dependency
gitlinks against the Sentinel repository checkout.

External consumers require a more general
provenance model.

The implementation must distinguish:

- Consumer repository and commit.
- Installed Sentinel release and revision.
- Actual compiler source contents.
- Dependency revision or content identity.
- Effective compiler settings.
- Producing test source.
- Evidence and build manifest identity.

Source checks must use the consumer checkout
and the actual compiler input source mapping.

Do not require external consumers to reproduce
Sentinel's fixed list of three Git submodules.

Supported dependency sources must have an explicit
verification method. Unsupported dependency layouts
must not silently be marked verified.

Source paths must be safe and must not escape
the expected checkout or dependency roots.

A source commit alone is insufficient evidence
of the actual compiler inputs.

The v0.4.1 build replay normalization rules
must remain narrow and explicitly documented.

Compiler reproducibility and local source consistency
do not authenticate the original EVM execution.

### Evidence 1.0 compatibility constraint

The existing Comparison Evidence 1.0 schema
requires Git revisions for both OpenZeppelin
contracts dependencies.

A vendored dependency content hash is not a
Git revision and cannot be substituted for one.

The initial consumer must reveal whether the
existing schema can accurately represent its
actual dependency layout.

ADR-005A must select either:

1. A documented, narrow supported dependency
   layout for the first vertical slice; or
2. A minimal versioned provenance metadata
   evolution with backward-compatible reading
   of existing Evidence 1.0.

No fabricated dependency revisions or unnecessary
dependency installation are permitted.

Frozen Solidity and Python classification
semantics remain independent of metadata changes.

## 12. Verification Result

Verification reports must separate:

    schema
    lossless_capture
    producer_execution
    classification_replay
    source_context
    build_provenance
    compiler_replay
    execution_provenance

The precise report schema is to be decided in
ADR-005A.

A verified classification means the recorded
Solidity verdict was independently reproduced.

A verified classification does not establish
that the verdict represents a safe upgrade.

A classification replay result must not contain
an implicit merge permission.

The execution provenance field remains
UNAUTHENTICATED unless a separate future
authentication mechanism is implemented.

### Required gates versus informational fields

Automatic policy PASS requires explicit success
of the applicable checks:

- Required producer identity and successful execution.
- Expected capture count and run identity.
- Evidence schema validation.
- Lossless raw capture preservation.
- Independent route-specific classification replay.
- Source and dependency verification.
- Build provenance and compiler replay.
- Expected consumer revision and CI run binding.
- Required scenario coverage.

The precise machine-readable check vocabulary
will be finalized in ADR-005A/B.

Execution provenance is currently
UNAUTHENTICATED and is informational.

The gate must not require this informational
field to falsely report authentication in order
to produce a policy PASS.

## 13. CI Policy Gate

CI policy evaluation is a distinct downstream
step from evidence verification.

Inputs:

- Verified completed evidence.
- Verification report.
- Trusted versioned gate policy.
- Expected producer/scenario identities.

Output:

    decision = PASS | BLOCK | REVIEW

The gate must produce machine-readable reasons.

A verification failure is not a policy REVIEW.
It is an invalid or untrusted input and must
be rejected.

The gate may not change the recorded observation,
classification or comparison verdict.

### Trusted verification input

A saved verification.json file is not itself
proof that independent verification occurred.

An independently invoked gate must either
reverify the supplied bundle using a trusted
verifier or receive a verified result through
the same trusted execution process.

The verifier and gate versions are selected
through trusted configuration, not solely
through candidate-branch inputs.

The gate must bind evidence to the expected
consumer commit and CI execution identity.

A completed green artifact from an earlier
commit or CI run must not be accepted for a
different candidate revision.

## 14. Initial Gate Decision Matrix

Proposed conservative defaults:

| Verification | Comparison | Decision |
|---|---|---|
| Verified | STILL_SATISFIED | PASS |
| Verified | CHANGED_TO_VIOLATION | BLOCK |
| Verified | STILL_VIOLATED | BLOCK |
| Verified | CHANGED_TO_SATISFIED | REVIEW |
| Verified | INDETERMINATE | REVIEW |
| Verified | INCOMPARABLE | REVIEW |
| Failed | Any | BLOCK |

PASS requires all required verification dimensions
to succeed.

For STILL_SATISFIED, the required before and after
stage statuses must be consistent with the frozen
comparison semantics.

A policy can make some REVIEW outcomes stricter,
but must not silently reinterpret the comparison.

Changes to default policy behavior require an
explicit versioned architectural decision.

The acceptance policy cannot treat a replay
MATCH alone as permission to merge.

## 15. REVIEW Behavior

REVIEW means the verified result is insufficient
for automatic approval under the configured policy.

A REVIEW must not result in a successful required
CI check by default.

Manual override is a separate governance process.

The first implementation need not provide an
automated override mechanism.

The machine-readable result must distinguish:

- A verified but indeterminate comparison.
- Verified incomparable stages.
- A verified transition from violation to satisfaction.
- An invalid or failed verification.

### Resolved violations

CHANGED_TO_SATISFIED maps to REVIEW by default
because remediation is a meaningful authority
change that may merit human inspection.

This is a conservative initial policy choice,
not an implication that remediation is unsafe.

The first consumer must test whether this default
creates unnecessary friction.

A later explicitly versioned policy may permit
automatic approval for verified remediation
without modifying comparison semantics.

## 16. Multiple Scenario Aggregation

A consumer may declare multiple independent
required authority scenarios.

Proposed precedence:

1. Missing required scenario => BLOCK.
2. Any failed verification => BLOCK.
3. Any scenario producing BLOCK => BLOCK.
4. Otherwise, any REVIEW => REVIEW.
5. Otherwise, all scenarios PASS => PASS.

An empty required scenario set must not PASS.

The gate must not average statuses, count
majorities or discard failed scenarios.

Each scenario's decision and reason must remain
visible in the aggregate report.

## 17. Policy Configuration Trust

A malicious or mistaken change to a policy file
could undermine the CI gate.

Policy configuration therefore needs an explicit
trust boundary.

For pull requests, the trusted policy must come
from a protected source independent of the
untrusted proposed changes.

Candidate designs include:

- Policy read from the protected base revision.
- A protected centrally managed required workflow.
- A separate trusted policy repository.

A PR-local policy must not be automatically
trusted merely because it is valid TOML or JSON.

Ordinary repository CI cannot claim tamper
resistance against an attacker who controls
the workflow definition and required checks.

The exact trust and override model is reserved
for ADR-005B.

### Trusted required scenario set

The complete list of required scenarios must
come from the trusted policy source.

A pull request must not make its own gate pass
by removing an authority scenario or excluding
a producer from its local configuration.

The trusted execution contract must include:

- Expected consumer revision.
- Expected CI run identity.
- Required scenario identities.
- Trusted verifier and gate versions.
- Accepted policy configuration.

The scenario ID does not attest that the
underlying Solidity producer still checks
the intended property.

Producer test modifications remain subject
to code review and trusted CI execution.

## 18. Proposed CLI Boundary

Illustrative commands, not implemented:

    sentinel run --config sentinel.toml

    sentinel verify --run artifacts/sentinel/<run-id>

    sentinel gate --policy sentinel-policy.toml \
      --run artifacts/sentinel/<run-id>

The CLI may initially be invoked using an explicit
Python entry point within the pinned dependency.

A globally installed executable is not required.

The three commands must remain logically distinct.

`run` produces and publishes.

`verify` independently validates a completed run.

`gate` evaluates verified results against policy.

The gate must not silently execute a new
producer or rewrite completed evidence.

The exact entry point and command contract
are reserved for ADR-005A and ADR-005B.

## 19. Gate Reports and Exit Semantics

The policy gate should emit a strict,
machine-readable report containing:

- Gate format and policy version.
- Run identity.
- Scenario identities.
- Verification outcome.
- Recorded comparison verdicts.
- Per-scenario policy decisions.
- Aggregate policy decision.
- Explicit decision reasons.

PASS must exit successfully.

BLOCK and REVIEW must exit unsuccessfully
when used as required CI checks.

Distinct exit statuses may help local tooling,
but their exact values are not yet fixed.

Invalid verification input must be identifiable
separately from a verified security regression.

## 20. Security and Trust Boundary

The portable workflow does not prove:

- A real public-chain transaction occurred.
- Possession of an EOA private key.
- That a fabricated but consistent raw capture
  originated from genuine EVM execution.
- That all privilege paths were evaluated.
- That arbitrary governance routes are secure.
- That dependency source identity is externally
  authenticated without a trusted reference.
- That CI policy is protected when the attacker
  controls the required workflow configuration.

A successful external CI gate is conditional
on trusted test execution and trusted policy
configuration.

The system remains an experimental security
regression tool, not a comprehensive audit.

## 21. Backward Compatibility

Keep unchanged unless independently justified:

- `src/AuthorityProbe.sol`
- `src/ComparativeAuthorityProbe.sol`
- `src/TimelockAuthorityProbe.sol`
- Existing frozen route semantics.
- Legacy witness schemas 0.2, 0.3 and 0.4.
- Comparison Evidence 1.0 interpretation.

Keep the v0.4.1 demonstration runners
operational during migration.

The portable workflow should use the same
route-specific replay implementations.

The new gate policy schema must not be confused
with the comparison evidence schema version.

Do not silently modify the meaning of PASS,
FAIL, UNKNOWN or ComparisonVerdict values.

## 22. External Acceptance Repository

A separate consumer repository must demonstrate
the full v0.5 integration.

It must contain:

- Its own independently authored Solidity contracts.
- Its own upgradeable proxy fixture.
- Its own actor and authority scenario.
- An installed, pinned Sentinel dependency.
- A documented producer test using the public API.
- Consumer-owned configuration.
- End-to-end evidence generation and verification.
- A CI gate using the published Sentinel tooling.

It must not copy internal Python runners or
demonstration fixtures from Sentinel.

Its tests must exercise actual consumer code,
not wrappers around Sentinel's own tests.

Acceptance scenarios include:

A. Verified unchanged restriction:
   STILL_SATISFIED => PASS.

B. Verified authority regression:
   CHANGED_TO_VIOLATION => BLOCK.

C. Verified nondefinitive comparison:
   INDETERMINATE or INCOMPARABLE => REVIEW.

D. Failed or skipped producing test:
   no completed publication, CI BLOCK.

E. Tampered raw capture, Evidence or build-info:
   verification failure, CI BLOCK.

F. Missing required scenario:
   aggregate CI BLOCK.

The external integration must be reproducible
from a clean clone with documented dependencies.

### Early acceptance requirement

The external consumer is created and used in
the first implementation slice, not after
the portable runner and gate are finished.

The initial vertical slice must demonstrate
one full Direct EOA/UUPS workflow, including
a deliberately introduced authority regression
that blocks CI.

The implementation must be measured from the
consumer's perspective:

- Consumer-owned Solidity code and fixture.
- Minimal required configuration.
- No copied JSON serializer.
- No copied Python runner.
- No manual source manifest.
- Clear scenario, decision, reason and
  evidence path in terminal output.

A second real scenario validates whether
additional abstraction is justified.

For release readiness, a developer other than
the implementation author should repeat the
integration using only published instructions.

## 23. Proposed Implementation Slices

### v0.5-A: External Vertical Slice

- Create an independent consumer repository first.
- Use consumer-owned UUPS contracts and fixtures.
- Support one Direct EOA producer.
- Provide the smallest practical export helper.
- Generate genuine comparison Evidence.
- Run independent verification.
- Apply a minimal PASS/BLOCK/REVIEW gate.
- Demonstrate a verified regression blocking CI.
- Reject an unsupported Direct contract actor.
- Record integration friction and missing interfaces.

The first slice is an end-to-end proof of
integration, not a finished general-purpose API.

### v0.5-B: Portable Integration

- Remove confirmed consumer-specific assumptions.
- Support a versioned configuration contract.
- Share producer verification and publication.
- Generalize source and dependency provenance
  only as required by real consumer layouts.
- Preserve route-specific independent evaluators.
- Keep historical Evidence readable.
- Keep v0.4.1 demo runners operational.
- Test a second consumer-owned scenario.

### v0.5-C: Trusted CI Gate

- Define the versioned policy input.
- Trust required scenario identities and policy.
- Bind artifacts to commit and CI run identity.
- Reverify evidence through a trusted verifier.
- Distinguish PASS, BLOCK and REVIEW.
- Reject old, incomplete or forged artifacts.
- Test scenario omission and policy tampering.
- Preserve separate machine-readable reasons.

### v0.5-D: Independent Adoption and Release

- Measure consumer integration effort.
- Measure Forge execution, Python verification
  and independent compiler replay time.
- Reuse identical build-unit verification inside
  a run rather than repeating it per scenario.
- Preserve fresh execution for every required run.
- Do not add a persistent compiler cache without
  measured justification.
- Have an independent developer follow the guide.
- Confirm clean-clone reproducibility.
- Assess Timelock compatibility and release scope.

## 24. Architectural Decisions Required

ADR-005A must resolve:

1. How an external test invokes the export adapter.
2. The smallest stable capture interface.
3. How a consumer declares producing test identity.
4. Whether one producer can emit multiple scenarios.
5. The packaging and CLI invocation contract.
6. How consumer and dependency sources are mapped.
7. How producer execution and publication are shared.
8. How existing comparison schema compatibility is kept.

ADR-005B must resolve:

1. Gate policy versioning.
2. Default verdict-to-decision mapping.
3. REVIEW and override semantics.
4. Aggregate decision precedence.
5. Protected policy configuration.
6. Exit codes and machine-readable reporting.
7. CI behavior for tampered or missing evidence.
8. The trust boundary of pull-request workflows.

Additional ADR-005A decisions:

- How to represent external dependency provenance
  without fabricating Git revision fields.
- EOA actor admission boundary.
- One compilation unit verified once per run.
- The minimum external export API.

Additional ADR-005B decisions:

- Trusted list of required scenarios.
- Commit and CI run binding.
- Trusted verifier and gate version selection.
- Saved verification report trust boundary.
- Remediation REVIEW default and override policy.

## 25. Acceptance Criteria

v0.5 is complete only if:

- An unrelated Foundry repository can install the
  published Sentinel version without a fork.
- Consumer-owned Solidity tests produce real captures.
- The consumer does not copy internal Python runners.
- Raw capture is preserved losslessly.
- The existing route-specific replay reproduces
  classification independently.
- Required source and compiler checks pass.
- Failed producer executions cannot publish.
- The policy gate distinguishes MATCH from permission.
- A verified dangerous regression blocks CI.
- Unresolved or incomparable evidence requires review.
- Missing evidence and invalid verification block CI.
- The policy source is explicitly trusted or its
  limitations are clearly disclosed.
- The external integration works from a clean clone.
- Existing v0.4.1 scenarios and APIs remain compatible.

Further acceptance requirements:

- External consumer integration begins in v0.5-A.
- No false dependency Git revisions are generated.
- Direct contract actor inputs are rejected.
- A stale valid artifact cannot satisfy a new CI run.
- Removing a required scenario cannot produce PASS.
- Standalone gate does not trust a saved report alone.
- Identical compilation units are not needlessly
  reverified within one execution.
- Terminal output prioritizes scenario, decision,
  reason and evidence location.
- Independent adoption is tested before release.

## 26. Proposed Decision

Proceed with v0.5 as a portable evidence workflow
and separate CI policy gate.

Prioritize the external Direct EOA/UUPS path
before broadening execution adapter coverage.

Preserve independent Python classification logic.

Extract shared orchestration only where it removes
demonstration-specific assumptions and duplication.

Define the minimal producer contract and trusted
gate boundary in ADR-005A and ADR-005B before
implementing the first external vertical slice.

Use that consumer integration to validate and
refine subsequent architecture decisions rather
than finalizing generalized orchestration first.

RFC-005 is a proposal for independent review,
not an accepted implementation specification.

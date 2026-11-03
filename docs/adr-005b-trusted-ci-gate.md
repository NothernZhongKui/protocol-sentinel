# ADR-005B: Trusted CI Policy Gate

Status: PROPOSED
Target: Protocol Sentinel v0.5
Parent: RFC-005, revision 2
Dependency: ADR-005A
Baseline: v0.4.1

## 1. Context

Protocol Sentinel independently reproduces
recorded Solidity authority classifications.

A classification replay MATCH establishes
agreement with the recorded classification.

MATCH is not a security approval.

A correctly reproduced comparison can report:

    CHANGED_TO_VIOLATION

The CI system must distinguish evidence
verification from permission to merge.

The first implementation must remain small,
explicit and fail-closed.

## 2. Decision

Introduce an independent CI policy decision
layer with three outcomes:

    PASS
    BLOCK
    REVIEW

The gate consumes verified comparison evidence
and a trusted, versioned acceptance policy.

It must not reclassify observations or change
the recorded Solidity comparison result.

The first implementation uses a fixed decision
table, not a general-purpose policy language.

## 3. Three Separate Results

Execution result:

    What did the Foundry producer observe?

Verification result:

    Was the recorded evidence preserved,
    validated and independently reproduced?

Policy decision:

    Is the verified comparison acceptable
    under the trusted CI policy?

These must be represented separately.

A successful producer does not imply PASS.

A successful verifier does not imply PASS.

## 4. Trust Boundary

The trusted CI environment selects:

- The Sentinel verifier and gate revision.
- The versioned policy configuration.
- The complete set of required scenarios.
- Expected consumer repository identity.
- Expected consumer checkout revision.
- Expected CI execution identity.

Untrusted candidate-branch configuration
cannot weaken these requirements.

For the initial external integration,
prefer a protected required CI workflow
with a pinned Sentinel revision.

The workflow must establish expected identity
from trusted CI context, not from claims
inside the candidate's evidence document.

A candidate workflow that can replace or
disable the required gate is outside this
trust guarantee.

## 5. Revision and Run Binding

Every evaluated evidence bundle must match:

- The expected consumer repository.
- The exact tested checkout commit.
- The unique CI execution identity.
- The current Sentinel producer run ID.
- The declared required scenario identity.

CI execution identity must distinguish
retries or attempts where supported.

For GitHub Actions, the trusted context may
include workflow identity, run ID and
run attempt.

A pull-request merge checkout SHA can differ
from the source branch HEAD SHA.

The gate must bind the actual tested checkout,
not assume these two commits are identical.

Old successful evidence must not authorize
a different commit or CI execution.

Comparing self-declared identifiers alone
does not authenticate execution provenance.

## 6. Trusted Scenario Inventory

The required scenario set comes from the
trusted CI policy configuration.

Each entry identifies at least:

- Scenario identifier.
- Supported execution route.
- Expected producer contract.
- Expected producer test.

The inventory must not be empty.

A missing required scenario means BLOCK.

An unexpected scenario cannot replace a
required scenario.

Duplicate scenario identities are invalid.

Changing the underlying Solidity producer
while preserving its scenario ID still
requires code review.

Scenario identity does not establish that
the correct security property was tested.

## 7. Verification Preconditions

Before an automatic PASS, require:

- Successful required producer execution.
- Exact producer and capture identity.
- Strict Evidence schema validation.
- Lossless raw capture preservation.
- Independent route-specific replay MATCH.
- Verified source and dependency context.
- Verified compiler build provenance.
- Successful independent compiler replay.
- Expected consumer revision binding.
- Expected CI execution binding.
- Complete required scenario coverage.

A failed mandatory check produces BLOCK.

Unsupported verification state produces BLOCK.

Execution provenance remains
UNAUTHENTICATED in v0.5.

This informational limitation does not
automatically prohibit PASS.

PASS remains conditional on the trusted
local execution and CI environment.

## 8. Decision Matrix

After all mandatory checks succeed:

| Comparison verdict | Decision |
|---|---|
| STILL_SATISFIED | PASS |
| CHANGED_TO_VIOLATION | BLOCK |
| STILL_VIOLATED | BLOCK |
| CHANGED_TO_SATISFIED | REVIEW |
| INDETERMINATE | REVIEW |
| INCOMPARABLE | REVIEW |

All other or unknown values produce BLOCK.

The gate must also validate that the
stage evaluations are consistent with
the recorded comparison verdict.

The existing independent classifier owns
comparison semantics.

The gate must not implement a competing
Solidity classification algorithm.

## 9. Remediation and REVIEW

CHANGED_TO_SATISFIED is REVIEW by default.

This is a conservative acceptance decision:
a repaired authorization failure may involve
a significant privileged-action change.

REVIEW does not imply the change is unsafe.

The first consumer must measure whether
manual review of remediation is useful.

Automatic approval of verified remediation
may be considered in a future versioned
policy decision.

No automatic override is required for v0.5-A.

## 10. Aggregation

For multiple required scenarios, apply
the following precedence:

1. Empty required set => BLOCK.
2. Missing required scenario => BLOCK.
3. Any invalid verification => BLOCK.
4. Any BLOCK decision => BLOCK.
5. Otherwise any REVIEW => REVIEW.
6. Otherwise all PASS => PASS.

Do not average results.

Do not use majority voting.

Do not ignore missing or failed scenarios.

The aggregate report retains each scenario's
decision and explanation.

## 11. Verification Report Trust

A persisted verification.json file is not
a trusted attestation.

The initial vertical slice may pass the
verified result directly to the policy gate
inside one trusted execution process.

A standalone gate invocation must reverify
the supplied evidence bundle using a trusted
verifier before making its decision.

The verifier and gate versions must be
selected outside untrusted producer metadata.

The gate must not accept an arbitrary
precomputed PASS field from the evidence.

## 12. Initial Configuration

Use a small, versioned policy document.

Illustrative structure:

    [policy]
    version = "1"

    [[required_scenario]]
    id = "unauthorized-upgrade"
    route = "DIRECT_EOA_UUPS"
    contract = "ConsumerAuthorityTest"
    test = "test_ExportComparison"

The exact schema is finalized against the
first external consumer.

No expressions, condition scripting,
user-defined evaluator code or plugins
are needed.

Policy inputs must be read from a trusted
location or trusted base revision.

A local policy file committed in an
untrusted pull request is not sufficient.

## 13. CLI and Exit Contract

The proposed external commands are:

    sentinel run --config sentinel.toml

    sentinel verify --run <run-directory>

    sentinel gate --policy <trusted-policy> \
      --run <run-directory>

These names remain provisional until
implemented in the external vertical slice.

The first slice may execute verification
and gate evaluation in a single process.

The commands must remain conceptually
independent.

Proposed required-CI exit behavior:

    PASS   => exit 0
    BLOCK  => exit 2
    REVIEW => exit 3

Malformed input and verification failures
must be represented as BLOCK, with explicit
error reasons, rather than being converted
into REVIEW.

No gate command may silently rerun a
producer against different source code.

## 14. Machine-Readable Report

Produce one minimal decision report with:

- Gate report format and version.
- Trusted policy version and identity.
- Consumer repository and checkout commit.
- CI execution identity.
- Sentinel producer run ID.
- Required scenario IDs.
- Verification outcome for each scenario.
- Original comparison verdict for each.
- Per-scenario PASS, BLOCK or REVIEW.
- Aggregate PASS, BLOCK or REVIEW.
- Explicit reason codes.
- Evidence artifact location.

Do not embed new evaluation semantics.

The report is an output artifact, not
a substitute for evidence verification.

The terminal view should emphasize:

    scenario
    decision
    reason
    evidence_path

Detailed checks belong in the report.

## 15. Security Boundaries

The gate cannot prove:

- That a fabricated but consistent execution
  capture originated from a genuine EVM run.
- That a scenario covers every relevant role.
- That an unchanged test still describes
  the intended business security requirement.
- That private keys or public-chain events
  were authenticated.
- That untrusted CI workflows cannot bypass
  required checks if branch protection and
  required-status controls are absent.
- That self-declared Git SHAs or CI run IDs
  independently authenticate an artifact.

The initial trust model relies on a
trusted CI runner, trusted tool revision,
correct producer configuration and
protected required gate execution.

These limitations must be documented.

## 16. Negative Controls

Test at least:

- MATCH plus CHANGED_TO_VIOLATION => BLOCK.
- MATCH plus STILL_SATISFIED => PASS.
- MATCH plus STILL_VIOLATED => BLOCK.
- MATCH plus CHANGED_TO_SATISFIED => REVIEW.
- MATCH plus INDETERMINATE => REVIEW.
- MATCH plus INCOMPARABLE => REVIEW.
- Classification replay mismatch => BLOCK.
- Invalid or missing Evidence => BLOCK.
- Missing required scenario => BLOCK.
- Empty trusted scenario inventory => BLOCK.
- Duplicate or replaced scenario => BLOCK.
- Producer skipped or failed => BLOCK.
- Altered compiler build-info => BLOCK.
- Wrong consumer revision => BLOCK.
- Old CI execution identity => BLOCK.
- Changed untrusted policy => no relaxation.
- Saved forged verification PASS => BLOCK.
- Unknown policy version => BLOCK.

Tests must confirm both decision reasons
and required-CI exit behavior.

## 17. First External Vertical Slice

ADR-005A supplies the consumer-owned Direct
EOA/UUPS producer and real Evidence workflow.

This ADR adds the minimal trusted gate.

First prove:

    safe implementation
        => STILL_SATISFIED
        => MATCH
        => PASS

    intentionally unsafe implementation
        => CHANGED_TO_VIOLATION
        => MATCH
        => BLOCK

The consumer must not implement the gate
decision logic or copy Sentinel runners.

The required scenarios and expected
consumer revision are supplied by trusted CI.

The complete workflow must be reproducible
from a clean external repository clone.

## 18. Deferred Work

Do not introduce:

- A general policy expression language.
- Policy-defined arbitrary scripts.
- A cloud evidence verification service.
- Cryptographic execution attestations.
- A custom CI orchestration framework.
- Automatic approval overrides.
- Dynamic scenario discovery replacing
  the trusted required scenario inventory.
- A new governance execution adapter.
- Persistent shared compiler caching
  without measured justification.

Multi-scenario reporting may evolve after
the initial consumer demonstrates a need.

Keep the first gate small.

## 19. Decision Status

This ADR is PROPOSED.

It defines the intended trust and policy
contract for Protocol Sentinel v0.5.

Implementation begins with one external
Direct EOA/UUPS vertical slice.

The first consumer validates the actual
usability of the public workflow.

The initial policy engine should be a
small deterministic function, not a
new framework.

Further abstractions require evidence
from an additional real consumer scenario.

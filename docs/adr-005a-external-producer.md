# ADR-005A: External Producer and Portable Evidence Boundary

Status: ACCEPTED (v0.5.0 Direct slice implemented)
Target: Protocol Sentinel v0.5-A
Parent: RFC-005, revision 2
Baseline: v0.4.1
Decision scope: First external Direct EOA/UUPS vertical slice

## 1. Context

Protocol Sentinel already implements:

- Solidity execution and observation.
- Direct authority comparison.
- Lossless Evidence 1.0 assembly.
- Independent Python classification replay.
- Source and build provenance verification.
- Independent Solidity compiler replay.
- Fail-closed atomic publication.

The existing evidence workflow is coupled to
Protocol Sentinel's own Foundry fixtures,
test names, source manifests and dependencies.

The v0.5 objective is to enable an unrelated
Foundry project to use this workflow without
copying or modifying Sentinel's internal scripts.

The external integration must drive architecture.
The first slice must produce real evidence
and an actionable CI decision.

## 2. Decision

Implement one minimal external Direct EOA/UUPS
integration before generalizing orchestration.

The first external consumer will:

1. Own its Solidity contracts and fixtures.
2. Install a pinned Sentinel dependency.
3. Declare one supported authority scenario.
4. Execute one explicitly selected producer test.
5. Export real observations through a small
   Sentinel-owned Solidity export helper.
6. Obtain strict Evidence 1.0.
7. Independently verify recorded classifications.
8. Verify required source and compiler provenance.
9. Receive a separate CI policy decision.

Do not modify frozen Direct classification
semantics to accommodate external integration.

Keep existing v0.4.1 demo producers working.

## 3. First Consumer

Use a separate Foundry repository.

It must contain original consumer-owned:

- UUPS implementation V1.
- UUPS implementation V2 with an intentional
  authorization regression.
- An ERC1967 proxy.
- An unauthorized actor.
- An authorized upgrade actor.
- A Foundry producer test.

The declared property is:

An unauthorized actor must not be able to
replace the proxy implementation.

The producer observes that restriction before
and after an authorized upgrade to V2.

Expected demonstration:

    before: PASS
    after: FAIL
    comparison: CHANGED_TO_VIOLATION
    replay: MATCH
    gate: BLOCK

A second safe consumer fixture demonstrates
STILL_SATISFIED and a gate PASS.

These are real consumer executions, not imported
Sentinel demonstration fixtures.

## 4. Consumer Responsibilities

The consumer specifies:

- Its contract implementations.
- Initialization and proxy deployment.
- Authorization roles and account selection.
- The before/after upgrade transition.
- The scenario specification.
- A unique scenario identity.
- One exact producing Foundry test.

The consumer must not need to implement:

- JSON field serialization.
- Evidence document assembly.
- Python policy classification.
- Python comparison replay.
- Build provenance manifests.
- Atomic artifact publication.
- CI decision calculations.

The consumer owns scenario correctness.
Sentinel cannot prove that the test describes
every relevant permission path.

## 5. Public Solidity Export Helper

Provide one small Direct-specific export helper.

The helper accepts existing Sentinel
observation and comparison result types.

It records actual Solidity-produced:

- Scenario specification.
- Before observation and evaluation.
- After observation and evaluation.
- Comparison scenario key.
- Comparison verdict and reason.

The helper must not recompute or invent a
different observation.

The raw capture representation must preserve
the existing Direct capture semantics.

Use Foundry serialization cheatcodes behind
the helper instead of asking consumers to
write their own serializers.

The producer output path is provided by the
runner for its unique staging directory.

The exact Solidity function names and
visibility are implementation details to
finalize against a working consumer test.

Avoid creating a general serializer framework.

## 6. Unsupported Actors

The first Direct convenience path supports
declared non-contract actors.

Reject an actor with deployed contract code
before starting the observation.

The guard must not silently reinterpret
the underlying frozen comparison semantics.

An empty code address is not cryptographic
proof of EOA ownership or key possession.

The contract-actor limitation must be explicit.

Add a negative producer test for an actor
with deployed bytecode.

## 7. Producer Selection

The initial runner accepts exactly one
declared Direct producing test.

Its identity must include:

- Foundry test contract.
- Exact test function.
- Declared scenario identifier.

Do not accept arbitrary shell commands from
consumer configuration.

Invoke Forge with an explicit test selector.

Validate the JSON test results:

- Forge exited successfully.
- Exactly the required test executed.
- Required test status is Success.
- No required test was skipped.
- Exactly one matching raw capture exists.
- Capture identity agrees with the scenario.

A Solidity security violation is a legitimate
successful producer outcome.

The test must not require a security PASS
assertion to complete.

A failed producer cannot publish evidence,
even if it wrote a capture before failing.

## 8. Consumer Configuration

Start with one small versioned configuration.

Illustrative shape:

    [sentinel]
    config_version = "1"
    route = "DIRECT_EOA_UUPS"

    [producer]
    id = "unauthorized-upgrade"
    contract = "ConsumerAuthorityTest"
    test = "test_ExportComparison"
    fixture_id = "consumer-vault-v1-v2"

The exact schema remains subject to the
first integration test.

Do not introduce a plugin system or
general-purpose configuration language.

Do not encode expected security PASS/BLOCK
as a trusted producer assertion.

The required scenario set belongs to the
trusted CI policy boundary in ADR-005B.

## 9. Initial CLI Boundary

The first consumer can invoke an explicitly
pinned Python entry point located inside
the installed Sentinel dependency.

A global executable or PyPI release is
not required for v0.5-A.

The desired command shape is:

    sentinel run --config sentinel.toml

This is a proposed interface, not an
already implemented command.

The CLI operates against the external
consumer checkout rather than assuming
the Sentinel repository is the root.

Do not copy internal runners to the consumer.

The consumer may require ordinary documented
Foundry filesystem permissions for its
run-local capture directory.

## 10. Evidence Compatibility

Reuse the existing Direct capture representation
and Comparison Evidence 1.0 where honest.

The current Evidence 1.0 dependency metadata
requires Git revisions for:

    openzeppelinContracts
    openzeppelinContractsUpgradeable

For v0.5-A, the first supported consumer may
use the corresponding pinned Git dependencies
and layout, provided both dependencies are
genuine inputs to its source tree.

The runner must verify the recorded revisions.

Do not fabricate Git SHA values.
Do not substitute content hashes into Git
revision fields.
Do not add unused packages merely to satisfy
the schema.

If the consumer cannot be represented honestly,
stop and make an explicit schema decision.

A later, minimal versioned provenance metadata
extension may be necessary.

Historical Evidence 1.0 must remain readable.
Classification semantics are not changed by
a provenance schema extension.

## 11. Source and Build Provenance

Resolve source content from the consumer's
actual compilation inputs.

Record:

- Consumer repository identity.
- Consumer commit and working-tree state.
- Installed Sentinel version and revision.
- Effective compiler version and settings.
- Actual compilation sources.
- Dependency Git revisions where applicable.
- Producing test identity.
- Evidence and build manifest hashes.

Use content hashes of actual sources,
not an internal fixed list of demo files.

Do not claim compiler source identity from
a Git commit alone.

For the initial CI integration, require
a committed consumer source state or an
explicitly verified equivalent.

The candidate revision must correspond to
the commit the trusted CI run is checking.

Independent compiler replay remains mandatory.

## 12. Shared Execution Boundary

The portable runner is responsible for:

1. Strict configuration validation.
2. Run-local staging allocation.
3. Safe path resolution.
4. Selected producer execution.
5. Forge JSON status verification.
6. Raw capture validation.
7. Lossless evidence assembly.
8. Independent classification replay.
9. Source and build verification.
10. Atomic completed publication.

Keep route-specific classifiers separate.

Do not unify Solidity and Python
classification into a single implementation.

Do not accept a historical completed run
as a replacement for fresh producer execution.

Avoid reimplementing every v0.4.1 check
inside a second external-only pipeline.

Extract shared functions only when the
external consumer demonstrates their value.

## 13. Verification and Policy Boundary

Evidence verification and CI policy decisions
are distinct responsibilities.

A successful independent replay MATCH
does not authorize merge.

For the initial vertical slice:

    MATCH + STILL_SATISFIED => PASS
    MATCH + CHANGED_TO_VIOLATION => BLOCK

Other comparison outcomes receive the
conservative decisions defined by RFC-005,
pending ADR-005B.

The initial vertical slice may execute
verification and policy evaluation in
one trusted process.

Standalone gate verification trust,
protected policy inputs, required scenario
sets, revision and CI run binding are
specified in ADR-005B.

Do not trust a saved verification report
solely because it claims success.

Execution provenance remains UNAUTHENTICATED.

## 14. Run Identity and Artifact Publication

Each producer invocation receives a fresh,
unique run identifier and staging directory.

Capture paths must be controlled by the runner.

Require exact scenario and run association.

Do not overwrite existing completed runs.

A failed producer, verification failure or
compiler mismatch leaves no completed evidence.

The terminal summary should prioritize:

    scenario
    decision
    reason
    evidence_path

Detailed verification dimensions remain
available in structured output.

## 15. Efficiency

A fresh capture is required for each run.

Within a run, identical compilation units
should be independently replayed once,
not once per scenario referencing them.

Do not add a persistent shared compiler cache
before measuring a real need.

Measure separately:

- Forge execution and compilation.
- Python evidence verification.
- Independent compiler replay.

Optimization must preserve all required
fail-closed verification checks.

## 16. Rejected Approaches

Reject copying demo runners into the consumer.

Reject a consumer-authored JSON serializer.

Reject generic arbitrary shell producers.

Reject inventing or repairing observations.

Reject fabricated dependency metadata.

Reject weakening existing replay semantics.

Reject a full generic adapter registry before
the first external consumer exists.

Reject a new governance execution route
as a prerequisite for this integration.

Reject treating a matching replay as
a successful CI policy decision.

## 17. First-Slice Acceptance

The first external vertical slice must prove:

- A clean clone installs pinned Sentinel.
- Consumer contracts are independently authored.
- A real consumer producer runs successfully.
- Capture comes from actual Solidity observations.
- A versioned consumer configuration selects it.
- Evidence is assembled without internal scripts
  being copied into the consumer.
- Lossless verification passes.
- Independent Direct Python replay passes.
- Required compiler reproduction passes.
- The safe comparison produces policy PASS.
- A deliberate regression produces policy BLOCK.
- A contract actor is rejected.
- Producer failure prevents publication.
- Missing or tampered evidence cannot PASS.
- Source and dependency identity are truthful.
- Existing v0.4.1 demos still pass.

This milestone proves one usable integration,
not universal Foundry compatibility.

## 18. Deferred Decisions

Do not decide until the consumer justifies it:

- Multi-producer execution configuration.
- Generic route adapter registries.
- Timelock integration through the portable runner.
- Evidence metadata version evolution.
- Arbitrary package manager support.
- Persistent compilation caches.
- PyPI packaging.
- Automatic producer generation.

ADR-005B separately decides the trusted
CI gate and policy execution contract.

## 19. Consequences

Benefits:

- Earlier proof of real-world portability.
- Smaller user-facing integration surface.
- No unnecessary classifier rewrite.
- Evidence compatibility preserved initially.
- Architectural abstractions justified by
  external usage rather than speculation.

Costs:

- The first supported dependency layout is narrow.
- A second consumer may expose required changes.
- An external Solidity export helper is necessary.
- Existing runner duplication will persist until
  shared logic is extracted safely.

These costs are acceptable for v0.5-A.

## 20. Decision Status

Accepted for the v0.5.0 external Direct EOA/UUPS slice.

The released implementation uses a pinned Sentinel
submodule, one declared Foundry producer, verified
Evidence, independent replay, and a trusted CI gate.

The implemented entry point is
`scripts/run_portable_direct.py` within the installed
Sentinel dependency. The proposed `sentinel run` CLI,
arbitrary dependency layouts, and generalized route
adapters have not shipped.

The integration proves one supported workflow,
not compatibility with every Foundry project.

# RFC-006: Existing Foundry Project Pilot and v0.6 Adoption

Status: PROPOSED — review requested; not an implementation commitment  
Review revision: 2 — incorporates external architectural review  
Target: Protocol Sentinel v0.6  
Baseline: released v0.5.1  
Companion: [ADR-006A](adr-006a-external-oss-pilot-boundary.md)  
Depends on: [ADR-005A](adr-005a-external-producer.md), [ADR-005B](adr-005b-trusted-ci-gate.md)

## 1. Problem

v0.5.1 has one end-to-end Direct EOA/UUPS integration in the
separately maintained-by-us [Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer).
That validates the supported workflow, but its Foundry layout and
dependency choices were prepared with Sentinel in mind.

We have not yet demonstrated that Sentinel can be integrated into
an existing, independently authored Foundry project with its own
toolchain, test conventions and source tree.

A successful internal integration does not establish adoption
readiness. In particular, v0.5.1:

- Requires exactly one Direct producer per runner invocation.
- Requires exact solc 0.8.24 for independent build replay.
- Assumes fixed root-level Git submodule paths and a foundry.lock.
- Requires substantial setup for a producer, version pin, trusted
  policy and GitHub workflow.
- Has not been timed against an unprepared external project.

These are constraints to measure, not permission to relax
verification or trust requirements.

## 2. Goal

Use a pinned, existing open-source Foundry repository as a
reproducible external-code pilot. Establish what works unchanged,
what requires documented consumer-side integration code and what
is blocked by Sentinel-owned assumptions.

Use observed blockers and measurements to determine the smallest
valuable v0.6 change set.

The long-term acceptance test remains an independent developer
following the documentation without editing Sentinel internals.
A pilot performed by Sentinel maintainers **does not claim**
independent-developer usability validation.

## 3. Proposed first candidate

[Capminal/capminal-contracts](https://github.com/Capminal/capminal-contracts),
pinned to commit
`40b713b58f39476bcc081d7987c34a46cc085dd9` for this proposal.

The `projects/capu/` Foundry workspace contains existing consumer-owned
UUPS contracts `Capu` and `ScapStaking`, ERC1967 proxy fixtures
and tests. Their upgrade authorization is restricted to
`DEFAULT_ADMIN_ROLE`. Start with **one `Capu` proxy**. The declared
property is that a specified actor **must not acquire upgrade
authority as a consequence of the authorized implementation
transition**. The actor is initially unprivileged; in the
synthetic regression, it may acquire `DEFAULT_ADMIN_ROLE` after
an intentionally flawed migration. See [ADR-006A](adr-006a-external-oss-pilot-boundary.md#5-required-security-scenario).

### Known configuration differences (source inspection only)

| Dimension | Pinned candidate | v0.5.1 portable Direct |
| --- | --- | --- |
| Compiler | `0.8.26` | Independent replay requires `0.8.24` |
| Project location | Nested `projects/capu/` workspace | Root-oriented consumer assumptions |
| Dependencies | Nested and shared Git submodules | Three fixed `lib/` paths |
| Lockfile | No tracked `foundry.lock` in inspected tree | Requires committed `foundry.lock` |
| Execution | Existing Foundry tests and two UUPS contracts | One selected Direct producer per invocation |
| Compiler configuration | Root `solc = "0.8.26"`; workspace `extends` | Assembler reads `profile.default.solc_version` |
| Repository identity | Checkout `capminal-contracts`, workspace `capu` | Runner/gate use `project.name` as identity |

These differences are **hypotheses for integration blockers**,
not reported outcomes of a completed pilot. The project must
first pass its own original tests on the pinned revision.
Do not add fake lockfiles, unused dependencies or synthetic
provenance merely to satisfy Sentinel.

The candidate's [SECURITY.md](https://github.com/Capminal/capminal-contracts/blob/main/SECURITY.md)
requires private reporting of genuine security findings.
The synthetic regression described below is not a claim about
the project's deployed contracts.

## 4. Scope

The first pilot covers only the currently supported
`DIRECT_EOA_UUPS` route.

Consumer-side additions may include:

- One small Foundry producer test using existing project fixtures.
- Separate baseline, safe/unsafe updated and probe candidate implementations. The same valid **probe candidate**, distinct from both active implementations, is used for both observations.
- Tracked Sentinel configuration, pinned dependency and CI
  integration required by the current public interface.
- A small reproducibility report with commands and outcomes.

Do not modify existing production contracts to manufacture
a successful integration. Do not edit, copy or patch Sentinel
internal Python scripts inside the consumer.

A compatibility fix, if justified, belongs in Sentinel and
requires a separate reviewed PR and negative tests.

## 5. Experiment sequence

| Stage | Action | Required record |
| --- | --- | --- |
| 0 — Baseline | Clone exact upstream commit, initialize existing dependencies and run original Forge tests | Original test outcome, environment, exact command and elapsed time |
| 1 — Native integration | Attempt documented v0.5.1 installation and setup without Sentinel internals edits | First failing step, diagnostic output, manual actions |
| 2 — Independent fixture oracle | In an ordinary Foundry test, check that the safe updated implementation still denies the actor and a test-only faulty migration grants that actor upgrade authority | Direct call behavior without any Sentinel classifier; exact fixture assumptions |
| 3 — Safe scenario | Add a consumer-owned producer using baseline, safe updated implementation and one fixed probe candidate | `STILL_SATISFIED`, verified Evidence and replay, if supported |
| 4 — Negative control | Use a **test-only inherited V2** with a flawed migration that grants the actor `DEFAULT_ADMIN_ROLE` during the authorized transition; do not override the non-`virtual` `_authorizeUpgrade` | `CHANGED_TO_VIOLATION` and trusted `BLOCK`, if supported |
| 5 — Failure handling | Exercise producer failure and at least one evidence/build or identity mismatch | No completed verified Evidence and no trusted PASS |
| 6 — CI | Attempt pinned, trusted workflow and policy integration | PASS/BLOCK/REVIEW, provenance and workflow integrity assumptions |
| 4 — Failure handling | Exercise producer failure and at least one evidence/build or identity mismatch | No completed verified Evidence and no trusted PASS |
| 5 — CI | Attempt pinned, trusted workflow and policy integration | PASS/BLOCK/REVIEW, provenance and workflow integrity assumptions |

Stage 1 may stop the **normal end-to-end run** on a hard
compatibility blocker. Continue **separate diagnostic probes**
of other suspected independent limitations where practical;
these do not count as running later end-to-end stages.
Every blocker and stage must be marked `Reproduced` (observed
by command), `Source-confirmed` (inferred from code, not
reached in execution) or `Not tested` (unknown). Record exact
command/log or source location. Do not claim later stages
passed without successful execution.

For stages 3–4, the producer must execute successfully
even when the observed security verdict is a violation.
Security policy is decided by the trusted gate, not by a
Forge assertion that requires the observed verdict to be safe.

## 6. Required measurements

Collect actual wall-clock results separately for:

- Clean clone/dependency setup and baseline Forge tests.
- An ordinary Foundry regression test of the same property,
  **without** Sentinel, as a fixture oracle.
- Incremental authoring time for Sentinel's producer, capture,
  configuration and trusted gate (separate from the ordinary test).
- Sentinel setup and consumer-specific changes.
- Fresh producer execution / compilation.
- Evidence validation and independent Python replay.
- Independent compiler reproduction.
- Full trusted CI job.

Also record:

- Count of required manual steps and files modified.
- Amount of producer logic copied from the Treasury example,
  and occasions requiring internal Sentinel scripts to be read.
- For each error: stage, cause, expected/observed values,
  actionable next step and path to diagnostic logs.
- Whether documentation alone identifies each fix.
- Whether any existing consumer convention must be changed.
- Whether multiple scenarios are genuinely required for
  meaningful coverage of the candidate.

No speed target is imposed before the baseline is measured.
Report hardware, operating system, Forge, Python, solc and
Git revisions alongside results.

## 7. Candidate v0.6 backlog, not promises

Order fixes by observed user impact and by whether they
preserve the existing trust model:

| Area | Trigger for implementation | Constraint |
| --- | --- | --- |
| Portable toolchain | A real project cannot replay its legitimate pinned compiler | Derive effective settings from real build-info, verify exact compiler build; trial `0.8.24` and `0.8.26` only if needed |
| Repository/workspace mapping | Nested workspace identity or source location cannot be represented | Independently model `repository_root`, `project_root`, and compiler source-name mapping; reject paths escaping verified roots, including symlinks |
| Dependency/layout support | Verified source inputs cannot be represented truthfully | Preserve true Git revision and content identity; version manifest and Evidence binding if needed |
| Setup and diagnostics | The developer cannot identify the next action from a failure | Report stage/cause/expected/observed/next step/log path; maintain fail-closed behavior |
| Execution efficiency | Measured CI cost is materially excessive | Profile first; do not cache away fresh execution or required verification |
| Multi-scenario runner | Two or more declared checks show tangible workflow value | Complete trusted inventory, per-scenario verification and fail-closed aggregation |

The policy engine already supports multiple comparisons in
`scripts/ci_policy.py`. That does **not** mean the released runner
or trusted gate supports a multi-producer suite: both currently
enforce one required Direct scenario per invocation.

If the pilot justifies a suite, design its execution and trust
boundary in a separate ADR. Do not slip multi-scenario support
into the pilot or quietly change Evidence 1.0 semantics.

Compiler and provenance compatibility must be decided separately.
The declared version in TOML is not necessarily the effective
Foundry configuration: check against fresh build-info rather
than substituting a version constant. Resolve actual source
files from compiler logical source names **without changing the
compiler input names used for replay**. Simply accepting `..`
is not a safe path model. The initial allowed file boundary
may be the verified repository checkout plus verified submodules;
symlink escapes must be rejected.

`sourceInputs` hashes, `dependencyRevisions` and the build
manifest provide different forms of identity. Before any
expansion, decide whether a versioned build manifest with actual
paths and dependency Git revisions suffices. If the format
changes, version its Evidence reference explicitly; do not
silently reinterpret `protocol-sentinel-build-provenance-v1`.
The classification semantics version need not change for a
metadata-only evolution.

## 8. Invariants to preserve

- Existing Solidity policies and comparison verdict semantics.
- The independent Solidity/Python classification check.
- Lossless capture-to-Evidence validation and strict schema.
- Actual consumer source, dependency and build provenance.
- Independent compiler reproduction, or explicit failure.
- Fresh execution and fail-closed completed publication.
- Separation of replay `MATCH` from gate `PASS`.
- Trusted required-scenario inventory, workflow identity,
  checkout and run/attempt binding.
- Existing `PASS` / `BLOCK` / `REVIEW` meanings.

A locally modified or fabricated but internally consistent
producer is not an attested EVM execution. Sentinel continues
to cover only declared actors, actions and fixtures.

## 9. Explicit non-goals

- Live-chain monitoring or interaction with deployed funds.
- Claiming a security audit of Capminal or any other upstream.
- Changing upstream production contracts to force a demo.
- Automatically discovering privileged actors or entrypoints.
- Supporting arbitrary privileged actions or governance routes.
- Replacing Foundry or OpenZeppelin upgrade validation.
- A general-purpose policy expression engine.
- A universal package manager / build system abstraction.
- Shipping v0.6 features before their acceptance tests exist.

## 10. Deliverables

1. A reproducible pilot workspace based on an exact upstream
   commit, with original sources retained and test-only changes
   clearly separated.
2. A short pilot report: baseline, supported path, blocker
   matrix with `Reproduced` / `Source-confirmed` / `Not tested`,
   diagnostic excerpts, implementation-effort and runtime
   breakdowns, and exact commands.
3. A prioritized list of minimal Sentinel issues, each with
   reproducer, expected behavior and required negative tests.
4. Follow-up implementation ADRs for any change to compiler,
   dependency, Evidence metadata or multi-scenario trust rules.
5. After fixes, a repeated clean-clone pilot plus the existing
   Treasury consumer regression suite. Release success requires
   both safe `PASS` and synthetic regression `BLOCK` on Capminal
   using Sentinel's **published interface**; an `UNSUPPORTED`
   research result alone does not fulfill the v0.6 portability goal.

Do not label the pilot as successful solely because Forge tests
compile. The independent replay and trusted gate must be
validated for end-to-end claims.

## 11. Review questions

1. Is this candidate an effective test of portability, or does
   its monorepo/toolchain complexity distort the first pilot?
2. Should the compiler mismatch be fixed before writing a
   consumer producer, or should we preserve its native failure
   first for reproducibility?
3. Can current Evidence 1.0 faithfully describe the candidate's
   dependency graph? If not, what is the smallest versioned
   provenance evolution?
4. Which parts of the runner assume a repository root rather
   than a nested Foundry project, including Git commit binding?
5. Is multi-scenario support justified by this consumer, or
   should it remain deferred?
6. What minimum reproducible diagnostics and elapsed-time data
   should be required before claiming adoption readiness?
7. Which checks must differentiate `repository_root` from nested
   `project_root` before porting provenance and the trusted gate?
8. Is the test-only role-granting migration feasible without
   overriding `_authorizeUpgrade`, and does the ordinary Foundry
   oracle prove the intended transitions?

## 12. Proposal status

This RFC authorizes review and a controlled integration
experiment only. It does not change v0.5.1 support claims,
the released evidence format, CI policy or public APIs.

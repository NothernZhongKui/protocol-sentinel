# ADR-006A: External OSS Pilot Boundary

Status: PROPOSED — revised after architectural review  
Target: v0.6 discovery phase  
Parent: [RFC-006](rfc-006-existing-foundry-pilot.md)  
Baseline: v0.5.1  
Decision scope: How to test adoption on an existing Foundry project;
not a decision to change the runner or Evidence format.

## 1. Context

The v0.5.1 external Treasury consumer is a meaningful
end-to-end regression test but was constructed for Sentinel.
We need an independently authored project's source layout,
compiler, dependency graph, tests and CI conventions to
challenge the current integration boundary.

Two risks must be avoided:

1. Distorting the consumer until it matches v0.5.1,
   thereby hiding portability problems.
2. Weakening Sentinel's provenance and fail-closed
   verification solely to obtain a successful demonstration.

## 2. Proposed decision

Run a **non-invasive, source-pinned OSS pilot** before
choosing v0.6 implementation features.

Use a separately isolated fork/worktree or local clone of
a real existing Foundry repository. Keep the upstream
commit reproducible. Retain the consumer's actual source
files and dependency provenance. Add a minimal, explicit
producer and synthetic test-only upgrade candidate.

Treat integration blockers as first-class results.

Do not modify Sentinel's internal scripts in the consumer,
and do not add dummy dependencies, false Git revisions,
or fabricated compiler artifacts.

For the initial pilot, [Capminal/capminal-contracts](https://github.com/Capminal/capminal-contracts)
at `40b713b58f39476bcc081d7987c34a46cc085dd9`
is the proposed candidate, not a new supported integration.

## 3. Why this candidate

The `projects/capu` workspace contains two real UUPS
contracts, `Capu` and `ScapStaking`, initialized through
ERC1967 proxies and guarded by `DEFAULT_ADMIN_ROLE`.

It also exercises compatibility surfaces absent from
the purpose-built Treasury consumer:

- Native Solidity `0.8.26` versus Sentinel's current
  exact `0.8.24` independent compiler replay.
- Nested Foundry workspace and shared dependencies.
- A different submodule layout and remappings.
- No tracked workspace `foundry.lock` in the
  inspected upstream file tree.

These are source-inspection findings, not measured
runtime failures. Baseline compilation, replay
compatibility and workflow outcomes remain unknown.

## 4. Isolation and ownership

| Item | Owner / rule |
| --- | --- |
| Upstream production sources | Untouched; preserve pinned upstream identity |
| Existing test fixtures | Prefer reuse, without modifying their intended semantics |
| New Foundry producer | Consumer-side, in the isolated pilot workspace |
| Baseline | Original implementation active before the transition |
| Updated | Safe or intentionally faulty test-only V2, installed by the authorized admin |
| Probe candidate | The same valid, separate UUPS implementation targeted by the actor in both observations; distinct from each active implementation |
| Sentinel runner and verifier | Pinned, unmodified v0.5.1 |
| Changes required in Sentinel | Separate issue and reviewed PR after documenting a blocker |
| CI policy / workflow | Trusted outside untrusted candidate-controlled inputs |

If a future compatibility patch changes tooling, repeat
the pilot with that revision and show the difference
from the unmodified v0.5.1 baseline. Do not silently
substitute a locally edited verifier.

## 5. Required security scenario

The initial property:

> The specified actor must not **acquire direct upgrade authority** as a result of the authorized implementation transition.

The actor has no upgrade permission at baseline. A synthetic faulty V2 may grant it `DEFAULT_ADMIN_ROLE` after migration; it must not still be described as unprivileged at that point.

The producer chooses one actual proxy, known actor,
candidate implementation, comparison fixture and
expected rejection bytes. Both observations must be
genuine and comparable under the existing Direct
semantics. Expected revert bytes must be derived
from the target contract and test fixture, not
invented to force `PASS`.

The authorized implementation transition occurs
between observations, with a valid candidate
available at both stages.

Acceptance examples:

| Scenario | Expected comparison | Independent replay | Trusted decision |
| --- | --- | --- | --- |
| Safe upgrade preserves restriction | `STILL_SATISFIED` | `MATCH` | `PASS` |
| Synthetic regression permits unauthorized upgrade | `CHANGED_TO_VIOLATION` | `MATCH` | `BLOCK` |
| Missing/failed producer or invalid provenance | No trusted completed result | No acceptable replay | `BLOCK` |

`Capu._authorizeUpgrade` is not `virtual`: the faulty V2 must not rely on overriding it. A proposed, as-yet-uncompiled fixture is an inherited test-only V2 with an explicit migration that grants the selected actor `DEFAULT_ADMIN_ROLE` during the authorized upgrade. Validate initializer behavior, storage compatibility and actual resulting authority with an ordinary Foundry test before using Sentinel.

Distinguish three implementations throughout: baseline, updated V2 and fixed probe candidate. Keep the probe candidate unchanged across observations and distinct from the active implementations. The intentionally faulty V2 is not an upstream finding.

The pilot must not treat `MATCH` by itself as a
policy `PASS`. In the trusted gate, a real security
`BLOCK` may still publish complete verified Evidence;
technical verification failures must not publish
completed verified Evidence.

## 6. Trust and provenance rules

- Use a recorded upstream Git SHA, exact consumer
  checkout and explicit pilot changes.
- Record the effective solc version and all compiler
  settings from actual build inputs.
- Keep real dependencies and the source graph.
- Require exact, versioned verification for any
  supported dependency layout.
- Reject unsupported compiler and dependency shapes
  rather than marking them verified.
- Keep producer execution, independent replay and
  trusted CI decision distinct.
- Bind required producer identity to protected policy
  and the actual tested checkout and CI run.
- No stale completed evidence may authorize a new run.

A consumer with internally consistent but fabricated
capture data remains outside execution-authentication
guarantees. This pilot does not change that boundary.

### Compatibility boundary for follow-up implementation ADRs

The current runner conflates the Git checkout and Foundry
workspace. An implementation ADR should distinguish
`repository_root` (checkout/commit identity) from
`project_root` (Foundry execution/configuration), and
define how compiler source names map to verified real files.
The first trust boundary may use the pinned repository and
verified submodules. Reject symlink and traversal escapes;
merely accepting `..` is insufficient. Preserve original
compiler source names for reproduction.

Derive the effective compiler version/settings from fresh
build-info, rather than assuming that one TOML field describes
Foundry `extends`. Initially assess exact `0.8.24` and
`0.8.26`, including normalization negative controls.

Distinguish source content hashes from dependency checkout
revisions. A versioned build manifest may be necessary for
real dependency paths. Any change to the existing
`protocol-sentinel-build-provenance-v1` format requires an
explicit versioned Evidence reference; do not silently change
the meaning of v1 or the independent classification semantics.

For user-facing failures, record the failed stage, reason,
expected and observed values, suggested next action and log
location. Technical verification failure and verified security
regression may both block CI but require distinct diagnostics.

## 7. Procedure and stop rules

1. Capture original upstream tree, Git revision,
   submodule revisions, toolchain and hardware.
2. Run the original Foundry build/tests unchanged.
   An upstream baseline failure is reported before
   touching Sentinel.
3. Attempt the documented v0.5.1 integration with
   native consumer compiler and project structure.
4. Log the **first reproducible failure** and exact
   remediation effort. Do not mask the failure by
   downgrading compiler or adding irrelevant libraries.
   After stopping the normal run, investigate other independent
   suspected blockers with isolated diagnostics. Mark each
   `Reproduced` (executed), `Source-confirmed` (inspection only)
   or `Not tested` (unknown). Never claim later E2E stages passed.
5. Add a small producer test and test-only candidate
   only if the required Solidity semantics can be
   represented without changing production sources.
6. Run safe, negative and technical failure cases.
7. Record per-stage runtimes and CI results, and
   open narrow Sentinel issues for real blockers.

The pilot may end with `UNSUPPORTED` or `BLOCKED`.
That is a valid discovery result, not a failed
research process or a justification to fabricate PASS.

## 8. Acceptance of the experiment

A **completed experiment** needs:

- Original baseline outcome and exact reproduction
  command on the pinned upstream revision.
- A table of setup steps, manual file changes and
  time spent, separating clean clone from warm runs.
- Time to write the ordinary Foundry behavior test and the
  additional Sentinel capture, config and trusted CI gate;
  count copied Treasury code and inspections of internals.
- A supported/unsupported verdict for each stage.
- Real command logs and error messages.
- A distinction between consumer mistakes,
  documentation gaps and Sentinel limitations.
- A prioritized issue list for v0.6.

A **successful end-to-end integration** additionally
needs actual Forge observation, lossless Evidence,
source/build verification, independent compiler
replay, classification `MATCH` and trusted gate
`PASS` and `BLOCK` in the respective scenarios.

A maintainers-run pilot cannot claim that an
unassisted external developer completed onboarding.
Research may conclude `UNSUPPORTED`, but a v0.6 portability
claim requires safe PASS, synthetic-regression BLOCK, fail-closed
technical errors and a passing Treasury control on clean clones.

## 9. Alternatives considered

| Alternative | Reason not selected now |
| --- | --- |
| Add another self-authored Treasury-like fixture | Repeats known assumptions rather than testing compatibility |
| Modify consumer production contracts until they fit | Invalidates the adoption test |
| Turn off independent compiler replay for solc 0.8.26 | Weakens the required verification boundary |
| Ship a generic dependency adapter immediately | No measured requirements or negative tests yet |
| Build multi-scenario support before the pilot | No external evidence yet that it is the next blocker |
| Seek a live project developer before any testing | Desirable independently, but not a prerequisite for finding deterministic compatibility issues |

## 10. Follow-up decisions

This ADR does **not** approve a new compiler-resolution
algorithm, provenance schema, path model, multi-scenario
runner, CLI or governance route.

Any such change requires a focused follow-up ADR or
explicit amendment addressing:

- Supported inputs, versioning and compatibility.
- Identity and path validation.
- Negative and adversarial controls.
- Reproducibility with the Treasury consumer.
- Full independent replay and CI gate behavior.

## 11. Security disclosure

Follow the upstream project's security reporting
policy. Keep findings concerning the actual
upstream contracts private until responsibly
addressed. Public test materials must clearly label
deliberately weakened local variants and must not
imply that the original project is vulnerable.

## 12. Open review questions

- Is the proposed target too complex for a first
  independent-code integration test?
- Should we use a simpler conventional layout
  as a control alongside the nested Capminal workspace?
- Can the present Evidence 1.0 dependency fields
  represent the real graph without new metadata?
- Is isolated per-producer execution still the right
  boundary if multiple actor checks are later added?
- Which setup diagnostics would be useful to someone
  who has never read Sentinel internals?

## 13. Status

Proposed for architectural review. No implementation
change is approved by this ADR, and no external
Capminal integration has yet been executed.

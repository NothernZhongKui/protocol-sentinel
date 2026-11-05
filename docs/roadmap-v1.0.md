# Protocol Sentinel — v1.0 milestone plan

**Status:** active implementation milestone, **not released**. [ADR-007](adr-007-v1-developer-adoption.md) is accepted for implementation. Acceptance evidence and remaining gates below are separate from the published v0.6.0 release.

## Product objective

**v0.6 portability:** Execution → Evidence → Independent Replay → CI Gate.

**v1.0 adoption:** Discover → Configure → Diagnose → Verify → Enforce.

An unfamiliar Foundry developer should be able to integrate Sentinel into a supported existing UUPS project without a maintainer walking them through pinned dependencies, compiler identity, TOML, source closure or CI trust semantics.

## Workstreams

| Track (previous working label) | Scope | Not in scope |
| --- | --- | --- |
| A — Hygiene (formerly v0.6.1) | Accurate published release notes and install requirements; correct current-doc links; consumer-first quickstart | No Solidity/API changes |
| B — Adoption (formerly v0.7) | Read-only `doctor`, conservative `init`, selective dependency setup, readable local result, CI Job Summary, tested trusted-CI example | No arbitrary routes, implicit role discovery or relaxed Git provenance |
| C — Coverage exploration (formerly v0.8) | After external pilot, select one requested declared privileged-action class and draft a separate execution/semantics ADR | No automatic universal access-control framework |

Tracks are incremental reviewable PRs. The public **v1.0** milestone is contingent on evidence gates, not elapsed time or completion of a predetermined feature count. Coverage expansion may be deferred on maintainer + reviewer decision rather than manufacturing demand.

## Implementation snapshot (2026-11-05 UTC)

**Merged in Sentinel:** [ADR-007 #45](https://github.com/NothernZhongKui/protocol-sentinel/pull/45); read-only doctor #46; intentionally incomplete Direct UUPS init #47; current-run Summary #48; selective consumer-owned imports #49/#51; protected-base CI example [#50](https://github.com/NothernZhongKui/protocol-sentinel/pull/50). These are adoption slices, **not** a v1.0 release.

**Real test-only consumer Actions:**

| Probe | GitHub run | Verified observation |
| --- | --- | --- |
| Safe Treasury upgrade | [42061646180](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42061646180) | Producer and source closure passed; 42 compiler contracts replayed; STILL_SATISFIED / MATCH / PASS / exit 0 |
| Synthetic faulty upgrade | [42061812476](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42061812476) | Producer and source closure passed; 42 compiler contracts replayed; CHANGED_TO_VIOLATION / MATCH / BLOCK / exit 2 |
| Producer failure | [42062309488](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42062309488) | No completed Evidence, VERIFICATION FAILED / exit 2 |
| Unapproved Sentinel gitlink | [42062438030](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42062438030) | Protected preflight failed before invoking candidate Sentinel Python |
| Candidate workflow replaced with `exit 0` | [42064261403](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42064261403) | **False-green job** with the same authority gate name and no Sentinel execution; demonstrates CI workflow substitution threat |

The [pilot consumer branch](https://github.com/NothernZhongKui/protocol-sentinel-consumer/tree/pilot/v1-trusted-ci-base) preserves historical v0.5 `main`. The synthetic faulty and bypass PRs are not merged. No independent GitHub merge-prevention claim follows from the gate jobs alone. The consumer currently has no active repository ruleset returned by its ruleset API, and the pilot-only `pull_request_target` integrity workflow is not active on the default branch. [Consumer PR #15](https://github.com/NothernZhongKui/protocol-sentinel-consumer/pull/15) proposes an additional default-branch-owned integrity check; the existing v0.5 workflow integrity intentionally rejects workflow changes until separately reviewed.

**Still required for release:**
- Reviewed installation of independent integrity on default/protected workflow source; ruleset requiring both authority and integrity checks on the pilot target, no bypass, protected producer/fixture ownership; demonstrate that [workflow substitution PR #14](https://github.com/NothernZhongKui/protocol-sentinel-consumer/pull/14) cannot merge despite a spoofed green authority job.
- A second external consumer, and an onboarding attempt conducted without maintainer guidance; record blockers and time-to-first-verified-result separately from toolchain setup.
- Final compatibility and documentation audit, explicit coverage-action decision or deferral, and review of the precise v1.0 release tag candidate. None of the pilot runs alone authorizes a v1.0 release.

## Evidence and release gates

1. **Hygiene:** README, release notes, quickstart, reference and threat-model descriptions agree with actual supported scope. Historic RC notes clearly labeled historic.
2. **Dependencies:** for Direct UUPS, a project with a compatible Git-pinned `forge-std` and its own OpenZeppelin should not download duplicate OpenZeppelin solely for Sentinel; negative test ensures no weakening of source attestation.
3. **Doctor:** clear actionable errors for missing/dirty/mismatched inputs; no mutating operations or false claims of compiler source-closure verification before a build.
4. **Init:** one compiling producer template with explicit `revert SentinelFixtureIncomplete()` in its producing test, no completed Evidence until the developer supplies an invariant, no inferred actor/authority/revert and no silent overwrites.
5. **Local experience:** one fully runnable supported example, documented exact toolchain; valid Evidence and independent replay, including negative controls.
6. **Trusted CI:** protected base policy constraints remain unchanged while trusted workflow injects each tested checkout SHA as `consumer_commit` per run; before executing Sentinel Python it independently verifies the installed tool gitlink and actual checkout against protected tool SHA. Safe PASS and synthetic faulty BLOCK in real GitHub Actions; Summary is bound to the current attempt and never reuses stale PASS. Verify required-workflow/branch rules also resist a candidate replacing a required job with `exit 0` or changing Sentinel gitlink, with explicit owner review for producer/fixture changes.
7. **External adoption:** two external Foundry integrations, one completed without maintainer intervention. Target ~30 minutes to first local verified result on a prepared compatible workspace; log blockers and time separately from toolchain installation.
8. **Compatibility:** v0.5 Treasury, v0.6 Capminal, existing schema and adversarial checks stay green.
9. **Coverage decision:** evidence-backed separate ADR for one new action, or explicit deferral. Never change Evidence semantics as a side effect of CLI work.

## Implementation order

- **PR 1 (this PR):** decision record, milestone agreement, published-release documentation hygiene. No runtime changes.
- **Next:** isolated dependency/selective-init spike and precise failure matrix before changing installation instructions.
- **Then:** doctor + tests, scaffold + tests, result renderer + CI example, third-party pilot, review of any coverage proposal.
- **Release:** only after independently demonstrated readiness; no v1.0 tag from this PR.

## Non-goals

Hosted dashboard, SaaS, npm/pnpm provenance without a separate design, general arbitrary privileged calls, portable Timelock runner, multiple required scenarios in one run and a new Evidence format merely for presentation.

Git attestation, independent replay, security limitations and trusted CI decisions remain first-class rather than being hidden or diluted for simpler onboarding.

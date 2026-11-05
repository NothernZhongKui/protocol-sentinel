# Protocol Sentinel — v1.0 milestone plan

**Status:** proposed implementation plan, not a released feature list. See [ADR-007](adr-007-v1-developer-adoption.md) for architecture decisions and questions for review.

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

## Evidence and release gates

1. **Hygiene:** README, release notes, quickstart, reference and threat-model descriptions agree with actual supported scope. Historic RC notes clearly labeled historic.
2. **Dependencies:** for Direct UUPS, a project with a compatible Git-pinned `forge-std` and its own OpenZeppelin should not download duplicate OpenZeppelin solely for Sentinel; negative test ensures no weakening of source attestation.
3. **Doctor:** clear actionable errors for missing/dirty/mismatched inputs; no mutating operations or false claims of compiler source-closure verification before a build.
4. **Init:** one minimal explicitly incomplete fixture template, no inferred actor/authority/revert; no silent overwrites.
5. **Local experience:** one fully runnable supported example, documented exact toolchain; valid Evidence and independent replay, including negative controls.
6. **Trusted CI:** safe PASS and synthetic faulty BLOCK in real GitHub Actions with unchanged required policy; Summary mirrors verified outputs and branch protection actually requires the gate.
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

# Protocol Sentinel — v1.0.0 release record

**Status:** release scope finalized in PR #55; merge, tag and publication follow review. [ADR-007](adr-007-v1-developer-adoption.md) is the original design record. The decision below governs v1.0.0; the earlier milestone checklist and implementation sequence are retained as historical context.

## v1.0.0 release-scope decision (2026-11-05)

The adoption implementation and independent execution/replay checks are complete for the declared Direct EOA/UUPS route. Evidence includes the existing Treasury and Capminal consumers plus a separately authored MultiVault codebase with verified local and GitHub safe/faulty results. All legacy Evidence schemas, public Solidity APIs and strict source-closure rules remain unchanged.

**Scope decisions:** v1.0.0 supports one declared Direct EOA/UUPS upgrade route; additional privileged actions require user demand and a separate ADR. Each consumer repository must configure its own required checks, workflow integrity, branch protection and producer review. Unassisted community onboarding is post-release adoption work, **not a completed v1.0.0 acceptance result**. The earlier onboarding tracking issue was deleted; it is not cited as evidence.

**Release status:** this document describes the v1.0.0 release PR. Publication requires an approved merge and subsequent tag/release; neither is performed by the preparation PR.

## Product objective

**v0.6 portability:** Execution → Evidence → Independent Replay → CI Gate.

**v1.0 adoption:** Discover → Configure → Diagnose → Verify → Enforce.

The v1.0 onboarding guide covers pinned dependencies, compiler identity, producer TOML, source closure and trusted CI semantics. The MultiVault integration was assisted; unaided developer onboarding feedback is a subsequent community activity.

## Workstreams

| Track (previous working label) | Scope | Not in scope |
| --- | --- | --- |
| A — Hygiene (formerly v0.6.1) | Accurate published release notes and install requirements; correct current-doc links; consumer-first quickstart | No Solidity/API changes |
| B — Adoption (formerly v0.7) | Read-only `doctor`, conservative `init`, selective dependency setup, readable local result, CI Job Summary, tested trusted-CI example | No arbitrary routes, implicit role discovery or relaxed Git provenance |
| C — Coverage exploration (formerly v0.8) | After external pilot, select one requested declared privileged-action class and draft a separate execution/semantics ADR | No automatic universal access-control framework |

The adoption work was delivered through separate reviewable changes. The release scope is fixed above; new authority coverage is deferred until an evidenced consumer need.

## Implementation snapshot (2026-11-05 UTC)

**Merged in Sentinel:** [ADR-007 #45](https://github.com/NothernZhongKui/protocol-sentinel/pull/45); read-only doctor #46; intentionally incomplete Direct UUPS init #47; current-run Summary #48; selective consumer-owned imports #49/#51; protected-base CI example [#50](https://github.com/NothernZhongKui/protocol-sentinel/pull/50). These implementation changes form the v1.0.0 release review. The tag has not been published.

**Real test-only consumer Actions:**

| Probe | GitHub run | Verified observation |
| --- | --- | --- |
| Safe Treasury upgrade | [42061646180](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42061646180) | Producer and source closure passed; 42 compiler contracts replayed; STILL_SATISFIED / MATCH / PASS / exit 0 |
| Synthetic faulty upgrade | [42061812476](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42061812476) | Producer and source closure passed; 42 compiler contracts replayed; CHANGED_TO_VIOLATION / MATCH / BLOCK / exit 2 |
| Producer failure | [42062309488](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42062309488) | No completed Evidence, VERIFICATION FAILED / exit 2 |
| Unapproved Sentinel gitlink | [42062438030](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42062438030) | Protected preflight failed before invoking candidate Sentinel Python |
| Candidate workflow replaced with `exit 0` | [42064261403](https://github.com/NothernZhongKui/protocol-sentinel-consumer/actions/runs/42064261403) | **False-green job** with the same authority gate name and no Sentinel execution; demonstrates CI workflow substitution threat |

The [pilot consumer branch](https://github.com/NothernZhongKui/protocol-sentinel-consumer/tree/pilot/v1-trusted-ci-base) preserves historical v0.5 `main`. The synthetic faulty and bypass PRs are not merged. No independent GitHub merge-prevention claim follows from the gate jobs alone. [Consumer PR #15](https://github.com/NothernZhongKui/protocol-sentinel-consumer/pull/15) was merged on 2026-11-05, installing the default-branch-owned integrity workflow. At the subsequent API check, consumer branch protection was off and no active repository ruleset was returned; **merge enforcement remains unverified**.

### Second independent codebase: MultiVault (2026-11-05 UTC)

A private, **non-fork** consumer lab based on [nikitavorobie/MultiVault](https://github.com/nikitavorobie/MultiVault), original commit `218f4587d6bb805e374df3646a4a0cf8d67fae9b`, was integrated with Sentinel pinned to `82830f957f4340b0ac472d1a1f4518451da231ae`. The original production `src/` contracts remained unchanged. This was an **assisted** integration with the maintainer and does not establish an unaided onboarding result.

- Mac: four new Foundry producer/oracle tests passed; read-only doctor reported no known blockers; independently replayed **69** compiler contracts for **both** scenarios. Safe: `STILL_SATISFIED / MATCH / NOT_EVALUATED`. Synthetic faulty UUPS migration: `CHANGED_TO_VIOLATION / MATCH / NOT_EVALUATED`. Local outputs are not trusted merge decisions.
- Real GitHub Actions: [safe PR #3](https://github.com/NothernZhongKui/sentinel-multivault-lab/pull/3), [authority run 42076289414](https://github.com/NothernZhongKui/sentinel-multivault-lab/actions/runs/42076289414), `STILL_SATISFIED / MATCH / PASS` (exit 0); independent integrity run 42076289078 passed.
- Synthetic faulty [PR #4](https://github.com/NothernZhongKui/sentinel-multivault-lab/pull/4), [authority run 42076526042](https://github.com/NothernZhongKui/sentinel-multivault-lab/actions/runs/42076526042): the authority gate reproduced `CHANGED_TO_VIOLATION / MATCH / BLOCK` (exit 2). Independently, integrity run 42076549748 rejected changes to protected pilot files. Faulty PR was closed **without merge**. These URLs require access to the private lab.
- **Boundary:** the lab's private `main` is not protected (`protected=false` on the GitHub branch API); ruleset API reports GitHub plan restrictions. Working Actions checks alone do **not** prove merge prevention. The main public/other pilot's branch rules are a separate configuration and acceptance question.
- Onboarding friction observed: first Mac `solc` location guess was wrong; the actual executable was under `~/Library/Application Support/svm/0.8.24/solc-0.8.24`. This is a documentation/diagnostics issue, not a reason to weaken compiler verification.

**Acceptance accounting:** two external Foundry codebases have verified execution evidence. MultiVault was integrated with maintainer assistance; no unaided onboarding is claimed. A GitHub authority gate issued `BLOCK`, but this lab's branch protection did not enforce merge prevention; that repository-owned control remains unverified.

## Original milestone acceptance criteria (historical)

The following records the initial release-gate proposal, not current blockers for PR #55. GitHub merge protection remains a required consumer-owned deployment control.
- Reviewed installation of independent integrity on default/protected workflow source; ruleset requiring both authority and integrity checks on the pilot target, no bypass, protected producer/fixture ownership; demonstrate that [workflow substitution PR #14](https://github.com/NothernZhongKui/protocol-sentinel-consumer/pull/14) cannot merge despite a spoofed green authority job.
- The second external consumer has been integrated. Collect unaided onboarding experience and time-to-first-result independently as post-release adoption evidence.
- Compatibility and documentation review are part of PR #55. Additional authority routes were deferred; merge and tagging are separate release actions.

## Original evidence and release checklist (historical)

1. **Hygiene:** README, release notes, quickstart, reference and threat-model descriptions agree with actual supported scope. Historic RC notes clearly labeled historic.
2. **Dependencies:** for Direct UUPS, a project with a compatible Git-pinned `forge-std` and its own OpenZeppelin should not download duplicate OpenZeppelin solely for Sentinel; negative test ensures no weakening of source attestation.
3. **Doctor:** clear actionable errors for missing/dirty/mismatched inputs; no mutating operations or false claims of compiler source-closure verification before a build.
4. **Init:** one compiling producer template with explicit `revert SentinelFixtureIncomplete()` in its producing test, no completed Evidence until the developer supplies an invariant, no inferred actor/authority/revert and no silent overwrites.
5. **Local experience:** one fully runnable supported example, documented exact toolchain; valid Evidence and independent replay, including negative controls.
6. **Trusted CI:** protected base policy constraints remain unchanged while trusted workflow injects each tested checkout SHA as `consumer_commit` per run; before executing Sentinel Python it independently verifies the installed tool gitlink and actual checkout against protected tool SHA. Safe PASS and synthetic faulty BLOCK in real GitHub Actions; Summary is bound to the current attempt and never reuses stale PASS. Verify required-workflow/branch rules also resist a candidate replacing a required job with `exit 0` or changing Sentinel gitlink, with explicit owner review for producer/fixture changes.
7. **External adoption (original target):** two external Foundry integrations, one unaided, with time-to-first-result tracked separately from toolchain setup. Two external codebases were validated; unaided onboarding is a post-release community follow-up.
8. **Compatibility:** v0.5 Treasury, v0.6 Capminal, existing schema and adversarial checks stay green.
9. **Coverage decision:** evidence-backed separate ADR for one new action, or explicit deferral. Never change Evidence semantics as a side effect of CLI work.

## Original implementation sequence (historical)

The planned sequence was ADR and documentation hygiene, dependency pin validation, `doctor`, `init`, results rendering, trusted CI, and an external project integration. These implementation slices are in the v1.0.0 review. PR #55 remains unmerged until approval; tagging and publication are separate steps.

## Non-goals

Hosted dashboard, SaaS, npm/pnpm provenance without a separate design, general arbitrary privileged calls, portable Timelock runner, multiple required scenarios in one run and a new Evidence format merely for presentation.

Git attestation, independent replay, security limitations and trusted CI decisions remain first-class rather than being hidden or diluted for simpler onboarding.

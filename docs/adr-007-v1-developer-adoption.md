# ADR-007: Developer adoption and dependency boundaries toward v1.0

Status: **PROPOSED — architecture review required (Astra)**
Date: 2026-11-05
Target: Protocol Sentinel v1.0 milestone
Baseline: released v0.6.0 (Direct EOA/UUPS, Evidence 1.1, trusted policy v2)
Related: [ADR-005B](adr-005b-trusted-ci-gate.md), [workspace reference](reference/workspace-v0.6.md), [threat model](threat-model.md), [v1.0 plan](roadmap-v1.0.md)

## 1. Problem and scope

v0.6 established that an independently authored Foundry producer can run in an external Git-pinned workspace, publish Evidence 1.1, reproduce recorded Solidity classification and compiler outputs, and obtain a trusted CI PASS or BLOCK. A separate real GitHub Actions Capminal pilot also observed a synthetic safe upgrade and a deliberately faulty **test-only** migration: ordinary Foundry tests passed while the Sentinel gate correctly blocked the unsafe scenario. This is not a vulnerability report about upstream Capminal.

What v0.6 has **not** established: that a developer unfamiliar with Sentinel can integrate it unaided; that a failed GitHub check is universally enforced by repository branch rules; or that npm/pnpm-managed compiler inputs satisfy Git source attestation.

The next milestone changes the product objective from portability to independent adoption:

    Discover → Configure → Diagnose → Verify → Enforce

The user brings a Foundry workspace, a declared actor, a proxy, a valid UUPS probe candidate, an exact expected authorization revert, and a real authorized upgrade transition. Sentinel must make these prerequisites understandable without guessing security intent.

This ADR proposes a **v1.0 milestone**, delivered through reviewable implementation slices rather than automatically publishing v0.6.1/v0.7/v0.8 along the way. No v1.0 release is authorized by accepting this ADR.

## 2. Decisions proposed

1. Preserve the v0.6 security and evidence boundaries while adding a small local diagnostic CLI, a safe scaffold, and human-readable CI summaries.
2. Distinguish consumer/runtime dependencies from Sentinel's own development fixtures. Do **not** require a second copy of OpenZeppelin for a Direct UUPS consumer when the consumer's properly pinned sources already suffice.
3. Keep Git-attested compiler source closure mandatory. Do not accept untracked or mutable node_modules as a convenience workaround.
4. Make the existing verifier and trusted policy gate the sole authority for reported results. Diagnostics and presentation may not become independent classifiers or merge-approval paths.
5. Ship one real, pinned example consumer/workflow and measure unassisted onboarding before v1.0.
6. Select any new privileged-action class only after an external demand signal and a **separate** ADR about execution and evidence semantics.

## 3. Dependency boundary: what is installed, compiled and attested

Today the Sentinel repository records three gitlinks: `forge-std`, `openzeppelin-contracts`, and `openzeppelin-contracts-upgradeable`. Its core `src/AuthorityProbe.sol` imports `forge-std/Test.sol`; `src/DirectComparisonCapture.sol` does **not** import OpenZeppelin. Other files, including the separate Timelock helper and a demonstration Vault, **do** import OpenZeppelin. This is a source-level observation, not proof that a partially initialized checkout succeeds under every consumer configuration.

The documented blanket recursive submodule installation can fetch tool-owned OpenZeppelin copies that a Direct UUPS consumer does not use. Proposed model:

| Dependency class | Direct UUPS consumer | Sentinel maintainer / optional route |
| --- | --- | --- |
| `forge-std` | Required by the current core; reuse the consumer's compatible, Git-pinned copy when possible | Pinned copy in Sentinel's own tests |
| OpenZeppelin contracts | Only if imported by the consumer's own contracts or actual compiler source closure | Timelock adapter and test fixtures need their declared versions |
| OpenZeppelin upgradeable | Only if imported by the consumer's own contracts or actual compiler source closure | Demonstration contracts / acceptance fixtures |
| Sentinel | Exact Git-pinned, clean submodule chain | Local checkout for development |

**First implementation slice:** prove selective submodule initialization on a clean external Direct UUPS fixture with preexisting compatible Foundry dependencies. Verify that the exact `forge build`, producer run, compiler replay, and completed-run verifier work, and that `git status`, `gitlink` verification, and source closure still hold. Test a nested workspace and an intentional missing dependency. Only **after** these checks pass should the consumer quickstart stop recommending recursion. Do not delete `.gitmodules` or change public Solidity imports as a shortcut.

Foundry remappings must resolve to one intended package version, never silently choose Sentinel's private library over the consumer's. Fail explicitly on unresolved imports, ambiguous ownership, unsupported symlinks, untracked compiler sources, dirty inputs, or mismatched gitlinks. No implicit network install, auto-download or checkout mutation in `doctor` or `run`.

**Excluded:** npm/pnpm provenance in this milestone. A tracked lockfile alone does not establish that compiled bytes came from its integrity-verified package. A future design must bind package resolution, tarball digest, installed bytes, compiler logical source names and replay to a trusted dependency graph, with fail-closed behavior. Do not accept `node_modules` merely because compilation succeeds.

## 4. `sentinel doctor`: read-only integration preflight

Proposed user-facing command:

    sentinel doctor --project .

An equivalent invocable script under the pinned Sentinel submodule must work even when no executable is on the user's PATH. The final invocation/packaging is a CLI implementation detail, not a new requirement on consumer projects.

Requirements:

- **Read-only / offline by default.** No `forge build`, network access, Git modifications, new files, Evidence staging or silent dependency installation.
- Use the same workspace/configuration/Git checks as the production runner wherever possible; extract small reusable validators rather than copy logic.
- Report workspace/root, tool gitlink and revision, producer TOML syntax and identity, Foundry permissions and output ignore rules, candidate source ownership, dependency/remapping expectations, compiler availability/identity (only what can be established without building), and whether a trusted CI policy was supplied.
- Distinguish `PASS`, actionable `FAIL`, informational `WARN`, and `DEFERRED` (checks that require an actual compilation or trusted CI run). Do not claim source closure verified without compiler build-info.
- Diagnose uncommitted consumer or tool changes without refusing to display useful results. A dirty checkout still cannot pass the real runner.
- Each failure names a file, setting or command to fix; output must not expose secret environment values.
- A local `doctor` can say "ready for local verification", never "CI approved".

Potential code boundaries: `scripts/workspace_context.py`, `scripts/workspace_provenance.py`, `scripts/source_closure.py`, `scripts/run_workspace_direct.py`. Reuse semantics; do not create a weaker shadow verifier.

Acceptance: run on a correctly configured consumer and on missing Foundry config, untracked source, dirty gitlink, missing solc, conflicting remappings, absent fs permissions and missing ignore entry. Confirm zero filesystem or Git-index mutations.

## 5. `sentinel init`: minimal non-authoritative scaffold

Proposed interface:

    sentinel init --route direct-uups --project .

Generate only:

- One minimal Solidity producer **template** showing baseline observation, explicit authorized transition, upgraded observation, comparison and conditional export.
- A producer configuration (`sentinel.toml`) with documented identity fields.
- Minimal Foundry permission / ignore instructions and a link to a **separate** optional CI template.

Invariant inputs — actor, proxy, implementation, probe candidate, expected revert, fixture, scenario ID and permitted transition — are **user-defined**, never inferred or invented by Sentinel. Template TODOs must prevent an accidental "green" executable security test. `init` never automatically writes a trusted CI policy or marks a producer safe. It must be idempotent or refuse existing-file collisions, support dry-run, and avoid silently replacing `foundry.toml` or `.gitignore`. Prefer printed exact additions over unsafe rewrites.

One supported route (`direct-uups`) is enough. No general project generator, package manager or plugin ecosystem.

Acceptance: scaffold builds when a developer explicitly fills the required fixture-specific fields, then exports exactly one real comparison; unmodified template cannot be mistaken for a passing authority property. Exercise repeated invocation and nested Foundry workspace.

## 6. CLI, policy and developer-facing results

Keep three distinct concepts:

1. **Execution:** what the isolated Foundry producer observed.
2. **Verification:** schema/source/compiled output and Python replay validity.
3. **Policy:** whether protected CI authorizes the verified comparison.

The v0.6 verdict mapping and exit semantics remain authoritative: trusted `PASS` → 0; trusted `BLOCK`/verification error → 2; trusted `REVIEW` → 3. Local runs without policy report `NOT_EVALUATED`, regardless of a successful `MATCH`. No change to Evidence 1.1 or trusted policy v2 is justified by prettier output.

Add a concise terminal result and a GitHub Job Summary renderer. Both are **presentation-only**: consume the verified result and `ci-gate.json` from the current run; never read an untrusted precomputed `PASS` as authority. When the producer fails or completed Evidence is absent/invalid, show `VERIFICATION FAILED` with the recorded cause, not a manufactured before/after classification. Summary failures must not turn a failed gate green; preserve the real exit code (including through `tee`/pipes).

Use a human-readable table for scenario, BEFORE, AFTER, comparison verdict, Python replay, compiler replay, CI decision and Evidence location. Avoid green success indicators for `MATCH + CHANGED_TO_VIOLATION`.

## 7. Real GitHub Actions integration, not a synthetic trust model

Provide one minimal, **tested** v1.0 Direct UUPS CI example using the v0.6+ workspace runner, not the legacy v0.5 reference consumer as the default recipe.

The reference must demonstrate:

- Checkout of the tested PR revision, including pinned source dependencies.
- Separate checkout or retrieval of trusted policy from a protected base or another reviewed source; policy resides outside candidate checkout.
- Binding to the actual tested consumer commit (including GitHub PR merge SHA where applicable), pinned Sentinel tool commit, workflow identity, run ID and attempt.
- Read-only permissions where possible; avoid running untrusted PR code with privileged `pull_request_target` credentials.
- Failure-safe artifact upload and Job Summary when the trusted gate returns `BLOCK`, without `continue-on-error` or shell-pipe masking.
- Separate integrity review for changes to workflows, policy, protected dependency pins and required scenario identifiers.
- Explicit instructions to configure **required** status checks / branch rules. A red job alone does not prohibit merging. Changes to producer/fixture semantics require review even when the scenario ID stays constant.

The acceptance test is an actual pull request with a controlled, explicitly synthetic authority regression: normal Forge tests pass; independent replay is `MATCH`; trusted gate exits 2 with `BLOCK`; integrity check passes; required branch rule refuses merge. Repeat with a safe upgrade and confirm PASS. Never merge the faulty test PR.

## 8. Documentation information architecture

- **README:** one concrete, short operator-acquires-upgrade-authority example; why this matters; which route is supported; one link to get started; precise limitations, not exaggerated claims.
- **Quickstart:** existing Foundry project → prerequisites / install → fixture-specific producer → config → doctor → verified local run → interpretation → optional trusted CI. Start with the consumer's task, not the maintainer acceptance harness. Include one fully compiled, pinned reference example with a runnable safe and deliberately faulty case, explicitly not a vulnerability in upstream software.
- **Reference:** exact CLI flags, status/exit codes, Evidence 1.1, policy v2, source closure, compiler identity, Git semantics and troubleshooting.
- **Architecture / Threat Model:** execution vs replay vs CI trust, false positives / scope, no independent authentication of original EVM execution, protected workflow requirements, and producer/fixture review obligations.
- **Historical docs:** label retired release candidate notes as historical; do not rewrite the original historical test conclusions.

No separate docs website, dashboard, hosted API or promotional metrics are part of v1.0.

## 9. Authority coverage: gated follow-on, not incidental CLI work

The current portable runner verifies one declared Direct EOA/UUPS `upgradeToAndCall(address,bytes)` attempt with empty initialization calldata. A route-independent arbitrary privileged-call framework, arbitrary actors, general timelock portability and multiple required scenarios per invocation are **not** implicitly approved.

Collect external requests after the adoption pilot. Choose **at most one** additional declared privileged-action class for a separate ADR (e.g. a narrowly scoped `grantRole`, `pause` or `mint` invariant only if demanded). Its ADR must define the actor/action model, baseline/after semantics, isolation and state observations, false-pass conditions, replay independence, policy mapping, schema impact, and negative controls **before** implementation. Do not broaden `DIRECT_EOA_UUPS` or reuse a verdict name with different semantics silently.

A material Evidence/schema change requires explicit versioning and migration; preserving the v0.5/v0.6 consumers is a release condition.

## 10. Compatibility and invariants

Must remain unchanged unless separately reviewed:

- Public Solidity comparison/observation APIs and supported route semantics.
- Published Evidence 1.0 and 1.1 interpretation, build-provenance v1/v2, and strict replay.
- Existing v0.5 Treasury reference consumer behavior.
- Existing v0.6 Capminal safe/faulty and adversarial acceptance behavior.
- Source closure, owner gitlink matching and compiler replay (no relaxed "helpful" source acceptance).
- Trust policy v2 and fail-closed decision exit codes.
- Unauthenticated EVM execution limitation; no claim of complete smart-contract security.

Guard against accidental green outcomes: missing producer, skipped test, stale Evidence, tampered compiler unit, dirty dependency, changed trusted policy or tool commit, and producer that quietly stops testing the declared invariant.

## 11. Delivery slices and evidence gates

| Slice | Deliverable | Exit criterion |
| --- | --- | --- |
| A. Hygiene | Current release notes, no RC status in current docs, correct toolchain installation and working links | Documentation examples match released v0.6 behavior |
| B. Dependencies + doctor | Selective initialization proven, duplicate OpenZeppelin avoided in eligible Direct projects, read-only preflight | Clean nested/external projects pass; altered or untracked dependencies fail closed |
| C. Scaffold + local UX | One Direct UUPS template, concise results, end-to-end example | Unassisted local verified Evidence on a supported prepared project |
| D. CI adoption | Trusted v2 example, Summary, protected required check instructions | Safe PR PASS, synthetic unsafe PR BLOCK, required check enforcement tested |
| E. External validation | Two external projects, at least one integrator with no maintainer help | Record setup steps, failure points, evidence validity and outcome; target first local result in ~30 minutes excluding installation of prerequisites |
| F. Coverage decision | Evidence-backed choice of one privileged-action class or documented deferral | Separate reviewed ADR and negative tests before any additional semantics |

Publish v1.0 only when adopted scope is actually implemented and independently exercised; do not promote untested CLI screenshots or synthetic context into product guarantees.

## 12. Questions for Astra / architecture review

Please review and challenge the following before implementation:

1. **Dependency resolution:** Is selective gitlink initialization compatible with Foundry source resolution and v0.6 Git source closure? What minimal matrix establishes this beyond a single fixture?
2. **Preflight trust:** Which existing validator functions can safely be shared by `doctor` without changing verification order or introducing check/time-of-use ambiguity? What must remain DEFERRED?
3. **Safe templates:** Can the proposed `init` placeholders accidentally produce a passing producer or misleading Evidence? Should the unfilled fixture be an intentionally non-compiling TODO or a test that reverts?
4. **CI trust boundary:** How to keep Summary independent of decision-making and ensure candidate-controlled workflow/config changes cannot bypass required checks? What GitHub ruleset settings are non-negotiable?
5. **Compatibility:** Which tests must pin Evidence and public Solidity behavior before modifying install paths and CLI packaging?
6. **v1.0 scope:** Should the coverage extension be a release gate, or explicitly deferred if external pilots reveal demand only for existing Direct UUPS checks?
7. **Failure semantics:** Which distinct diagnostics are essential for users, and where would a new CLI error code risk confusion with policy BLOCK/REVIEW?

Please distinguish architectural blockers from cosmetic improvements. This ADR is a review handoff, **not approval to ship v1.0**, and none of the proposed commands is implemented by this document.

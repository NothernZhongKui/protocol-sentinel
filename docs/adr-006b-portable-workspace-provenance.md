# ADR-006B: Repository/Workspace Separation and Build Provenance

Status: PROPOSED — implementation design for review, not shipped
Target: Protocol Sentinel v0.6
Parent: [RFC-006](rfc-006-existing-foundry-pilot.md)
Pilot boundary: [ADR-006A](adr-006a-external-oss-pilot-boundary.md)
Baseline: released v0.5.1
Route: Portable `DIRECT_EOA_UUPS` only

## 1. Decision summary

Make an existing Foundry workspace inside a verified Git checkout
a supported consumer shape. Separate the repository identity and
trust boundary from the Foundry build root, and independently map
compiler source names to verified physical files. Remove assumptions
about three fixed dependency paths and one hard-coded solc version.

Preserve fresh execution, capture integrity, classification replay,
independent compiler replay and trusted CI decisions. Do not edit
Solidity classifier semantics or silently relax Evidence 1.0.

This ADR proposes the integration boundary and acceptance tests.
It does **not** claim that the v0.6 implementation exists.

## 2. Evidence from the Capminal pilot

Pinned upstream:
[Capminal/capminal-contracts](https://github.com/Capminal/capminal-contracts)
at `40b713b58f39476bcc081d7987c34a46cc085dd9`.
The isolated consumer pilot commit is
`75579d1bdefd3b2b105b24f33abb70f18c5b0c41`.

| Observation | Result | Status |
| --- | --- | --- |
| Original Forge build/tests | PASS, build 63 s | Reproduced |
| Independent Foundry safe/faulty oracle | 2/2 PASS | Reproduced |
| Sentinel v0.5.1 Solidity safe/faulty capture | `STILL_SATISFIED` / `CHANGED_TO_VIOLATION` | Reproduced |
| Unmodified portable runner | `Missing committed Foundry lockfile`, exit 1 | Reproduced |
| Fresh compiler build-info | solc `0.8.26`; one settings set; producer included | Reproduced |
| Source mapping | 100 unique names: 71 inside workspace, 29 outside workspace but inside checkout, 12 with `..`, zero unresolved | Reproduced |
| Actual file bytes versus compiler input | `SOURCE_INTEGRITY=MATCH` | Reproduced |
| Exact solc 0.8.26 replay with original Standard JSON and restricted checkout filesystem access | 1 build unit, 111 compiled source units, 87 contracts, output `MATCH`, 10.76 s | Reproduced (filesystem-assisted diagnostic) |
| Strictly self-contained solc replay without import callback | Missing import source units; recorded `input.sources` has 100 keys while outputs have 111 | Reproduced (blocked) |
| Original Standard JSON plus isolated snapshot of 11 additional import files | Exact solc 0.8.26 reproduced 87 contracts; existing normalized output comparison `MATCH`; raw AST unequal | Reproduced (sandbox diagnostic) |
| Git source attestation over all 111 source units | 111/111 source bytes matched tracked files and checked-out gitlinks; 6 Git owners (10 root, 101 submodule); max depth 1 | Reproduced (standalone diagnostic) |
| Full portable Python replay / trusted CI gate | Not executed | Not tested |

The source-mapping, byte-match and filesystem-assisted replay
checks are standalone diagnostic scripts, **not** execution of
Sentinel's portable verifier. The replay used the exact local
solc `0.8.26+commit.8a97fa7a` and the existing output comparison.
It required the compiler to load additional imports from the
checkout, not a hermetically verified input closure. A subsequent
isolated snapshot replay (STEP 012) matched normalized outputs
without granting solc access to the original checkout. STEP 013
independently checked all 111 source units against Git-tracked
blob identity and the recorded immediate parent gitlinks: 10
root-owned, 101 submodule-owned across 6 Git owners. That is a
**local diagnostic**, not hardened v0.6 source attestation.
No completed portable Evidence or trusted gate has been run.

## 3. Concrete v0.5.1 limitations

| Location | Current assumption | Why it fails for nested consumers |
| --- | --- | --- |
| `run_portable_direct.py` | One `project` resolves config, git identity, source files, lockfile, capture and dependencies | Workspace is `projects/capu`; Git metadata is at checkout root |
| `run_portable_direct.py` | Sentinel installed at `project/lib/protocol-sentinel` and tracked at that exact relative path | Tool installation must be checked against the real checkout gitlink |
| `build_provenance.py` | Three fixed `lib/` dependencies | Existing graph has nested and shared submodules |
| `build_provenance.py` | Reject `..` and resolved paths outside project | 29 actual inputs are outside workspace; 12 names contain `..` |
| `assemble_direct_comparison.py` | `profile.default.solc_version` is authoritative | Capminal uses `solc` and workspace `extends` |
| `replay_build_compilation.py` | Exact `0.8.24+commit.e11b9ed9` | Fresh build-info reports `0.8.26` |
| `trusted_direct_gate.py` | `project.name` equals repository slug | Workspace `capu` is not repository `capminal-contracts` |
| Evidence 1.0 + build manifest v1 | Two named OpenZeppelin revision fields and v1 manifest format | Cannot truthfully describe the full dependency graph through those fields |

The lockfile failure is the **observed runner stop**. The other
failure modes are source-confirmed or inferred from the measured
layout, not incorrectly labelled as completed pipeline failures.

## 4. Project context

Define separate, explicit values:

- `repository_root`: canonical root returned by Git for the
  checked-out consumer, used for commit, tracked-file and
  submodule identity and clean-worktree checks.
- `project_root`: canonical directory containing the effective
  Foundry configuration and execution context, within the
  permitted checkout.
- `tool_root`: installed Sentinel directory, validated against
  an exact tracked gitlink and revision; may be nested.
- `compiler_source_name`: the logical path key recorded in
  solc `input.sources`, retained unchanged for compiler replay.
- `source_physical_path`: resolved file selected for byte and
  provenance verification, mapped to the trusted checkout and
  verified dependency roots.

Prefer deriving `repository_root` from Git rather than asking
the consumer to duplicate its location in a free-form config.
`project_root` remains an explicit runner selection. Any
project path supplied by an untrusted branch must still be
resolved and validated against the checkout.

Repo identity in Evidence must be distinguishable from local
folder names; a self-declared origin URL or repository slug is
not authentication. The trusted CI gate binds identity to
protected policy, CI context, actual checkout commit, tool pin
and run/attempt identifiers.

**Trusted workspace identity:** required-scenario policy must
bind the selected producer to a normalized, repository-relative
workspace path (e.g. `projects/capu`) plus a pinned config path
and producer identity. Resolve it against the verified repository
root. Reject alternate workspace selection by candidate-branch
config, even if two workspaces share the same test path, contract
name and test name. Do not bind machine-specific absolute paths;
relocated clean clones must retain the same scenario identity.

## 5. Compiler source mapping

For each fresh compiler input source:

1. Keep its original logical name and exact `content` bytes.
2. Resolve its physical path relative to the effective Foundry
   workspace using the actual supported Foundry path model.
3. Canonicalize path components and inspect symlinks.
4. Require the resolved file to belong to the consumer checkout
   or Git submodules reachable through a verified gitlink chain
   rooted in that checkout. External dependency roots are out of
   scope for v0.6.
5. Compare file bytes with the bytes supplied to solc, without
   normalizing either source or logical name.
6. Verify the file is Git-tracked in its immediate owning checkout.
   For a submodule, validate each parent gitlink's mode `160000`
   and pinned revision through the full chain from consumer root.
   Reject untracked and ignored-only files, even if bytes match.
7. Record deterministic mapping to the owning checkout,
   repository-relative physical path and source content digest.
8. Require a stable logical-name-to-physical-file mapping across
   build units; reject conflicts. Multiple logical source names
   may point at one verified physical file and must retain their
   original logical compiler input keys.

`..` may occur in compiler logical paths; it is not
automatically unsafe **if** physical resolution and ownership
pass. It must never grant arbitrary access beyond verified roots.
An absolute path, symlink escape, missing/untracked/ignored-only
file, dirty dependency or conflicting content is an error, not
a reason to skip a source. Clean `git status` alone is
insufficient to prove that compiler sources are tracked.

Preserve logical names in independently replayed Standard JSON.
Physical path normalization belongs to verification metadata,
not a rewrite of the compiler input.

**Observed compiler-input closure gap (STEP 008B–C):** fresh
Foundry build-info included 100 `input.sources` keys, but
`output.sources` contained 111 source-unit names. Some imports
requested relative names such as
`../cap-staking/lib/openzeppelin-contracts/contracts/proxy/Proxy.sol`
while the same physical files were listed in `input.sources`
under absolute names. Vanilla `--standard-json` with no import
callback failed to resolve these; allowing checkout filesystem
access reproduced 87 contracts and matched both output sections.
A v0.6 verifier must recover and independently validate **all**
actual compiler source units and their ownership, not just the
100 prepopulated input entries. The source-unit closure and its
correspondence to fresh execution must be represented explicitly.

**STEP 009–012:** supplementing the 11 imports directly into
`input.sources` produced a `CONTRACTS MISMATCH` despite matching
bytecode and source IDs, because immutable-reference AST IDs
changed. A separate isolated filesystem snapshot of those 11
sources kept the original Standard JSON unchanged and reproduced
87 contracts with the existing Sentinel normalized comparator.
Raw AST objects still differed; no AST-exact bitwise replay
claim is made. This sandbox diagnostic checks content but does
**not** yet prove Git ownership/submodule-chain integrity or
portable Evidence publication.

## 6. Dependency identity and lockfiles

Build provenance must enumerate **actual** relevant pinned
Git dependencies and their real checkout-relative paths and
revisions, including nested Git submodules. Validate gitlink
mode `160000` and revision against the index of the owning Git
checkout, and verify the dependency worktree is clean.

Do not install unused copies of OpenZeppelin merely to satisfy
a fixed path list. Do not invent dependency revisions.

A Foundry lockfile is evidence **when actually present and
tracked**. Its absence must not be a blanket failure if the
effective source/dependency graph can be completely verified
through other supported evidence. Distinguish absent lockfile
from present but untracked/ignored **and used** lockfile: the
latter cannot silently count as absence. A missing lockfile
must not imply pinned dependency integrity; unsupported or
untracked inputs still fail closed.

The minimum v0.6 scope is Git-tracked sources plus verified
Git submodules. Arbitrary vendored/package-manager dependency
resolution is a separate decision.

## 7. Compiler provenance and replay

Use fresh Forge build-info to determine the effective solc
version, compiler settings and source inputs. Reconcile this
with the Foundry configuration and actual invoked compiler;
do not trust a single TOML `solc_version` key.

Resolve the **exact supported solc build** for independent
Standard JSON replay, verify its version/commit and reproduce
normalized outputs. For this pilot, support `0.8.24` and
`0.8.26` only if exact replay and negative tests pass.
Unknown versions or mismatched settings are explicit errors.

Any required normalization difference between solc versions
must be documented with a real reproducer, narrow reasoning
and adversarial mutation tests. Never suppress a real output
difference to obtain `MATCH`.

## 8. Evidence and manifest compatibility

Preserve at least three categories of verified inputs:

- **Compiler inputs:** exact source bytes, logical source names,
  effective compiler settings and build units.
- **Integration inputs:** Sentinel scenario/config, all effective
  Foundry configuration files (including workspace and inherited
  root settings), remappings, dependency metadata and tracked
  lockfiles when present.
- **Verification tooling:** pinned Sentinel code, verifier scripts,
  schema, semantics registry and their relevant dependencies.

Existing `provenance.sourceInputs` contains more than compiler
sources: it also hashes `.gitmodules`, `foundry.toml`,
`foundry.lock`, the consumer config and Sentinel scripts/schema/
semantics. Any new format must preserve these checks and adapt
them correctly to inherited Foundry configurations and optional
lockfiles. These categories are a data contract, not a demand
for three new files.

Evidence 1.0 currently fixes
`protocol-sentinel-build-provenance-v1` in its build-manifest
reference and requires named OpenZeppelin revisions.

**Proposed compatibility strategy:**

- Preserve the existing Evidence 1.0 + manifest v1 reader
  and the Treasury consumer as a compatibility path.
- Define a separately versioned, strict build manifest for
  actual dependency graphs and verified source mappings.
- **Before any new writer publishes Evidence**, define the
  smallest versioned manifest schema and Evidence reference
  compatibility matrix, including required workspace binding.
- When binding that format to Evidence, introduce an
  explicit schema/version evolution with strict version dispatch:
  old v1 stays accepted on its own terms; malformed or unknown
  new formats cannot fall back to a legacy reader.
- Add negative tests for mixed Evidence/manifest versions,
  unsupported versions and inconsistent version claims.
  Avoid maintaining two independent writer pipelines by default.
- Keep `direct-eoa-v1` classification semantics untouched;
  metadata versioning does not imply new verdict semantics.

Exact next-version field names and the Evidence schema revision
remain a focused design task, but **must be frozen before new
pipeline publication or gate integration**. Diagnostic source
mapping and compiler replay can proceed independently. No code
PR may silently ship a new JSON shape under a v1 identifier.

## 9. Publication and trusted gate

Retain the existing three distinct outcomes:

- Forge observation and a comparison verdict.
- Independent Evidence validation and Python/compiler replay.
- Trusted policy `PASS` / `BLOCK` / `REVIEW`.

The safe scenario should be `MATCH + STILL_SATISFIED` with
a trusted `PASS`. The synthetic regression should be
`MATCH + CHANGED_TO_VIOLATION` with a trusted `BLOCK`.
A verified security `BLOCK` may have published Evidence.
A source, compiler, identity or verification failure must
not publish completed verified Evidence.

A candidate-controlled checkout, TOML file or reported Git
origin must not determine the trusted policy, required
producer inventory or trusted CI identity.

## 10. Implementation order

1. Add independently testable repository/workspace and
   installed-tool pin resolution; preserve Treasury behavior.
2. Verify real source mappings and actual Git dependency
   ownership, with explicit failure reasons.
3. Test hermetic import-source closure for the observed 11
   additional logical source units, reconcile with Git ownership
   and independently reproduce exact `0.8.26` outputs without
   unrestricted filesystem access. Maintain `0.8.24` replay.
4. Freeze the minimal manifest/Evidence version contract and
   compatibility matrix **before** publishing through a revised
   runner; verify backward compatibility.
5. Align runner, assembler and trusted gate with the same
   verified context; test safe and faulty pipelines end-to-end.
6. Improve first actionable error display: phase, reason,
   expected/actual value, next action and diagnostic path.

No new Solidity route, authority classifier or multi-scenario
runner is required by this ADR.

## 11. Negative controls and release acceptance

Tests must reject: traversal/symlink escape, untracked or
ignored-only source, dirty tracked source, mutated compiler
source content, duplicate logical name with conflicting
content, absent/dirty gitlink or broken nested gitlink chain,
wrong repository/workspace pairing or producer with duplicated
name in another workspace, forged dependency revision, wrong
solc binary or compiler settings, altered build-info, mixed
Evidence/manifest versions, unsupported version or failed
strict version dispatch, mismatched manifest digest, swapped
consumer commit, old CI run identity and untrusted policy.

Positive portability tests must accept: relocated checkout
under a renamed parent directory, verified source imported from
an adjacent workspace, correctly pinned nested submodule,
absent lockfile with otherwise fully verified inputs and
Git dependencies, and two logical compiler source names mapping
deterministically to one physical tracked file while retaining
both logical keys. Treasury remains a required legacy control.

Acceptance requires a clean clone of the real Capminal pilot
to produce safe and synthetic-regression completed Evidence,
independent replay `MATCH` and appropriate trusted gate
`PASS` / `BLOCK`; technical failures publish no completed
verified Evidence. The existing Treasury integration and
legacy Evidence 1.0 tests must keep passing.

Keep the measurements separate: Foundry test-authoring time,
incremental Sentinel integration effort, fresh compilation,
Python replay and compiler replay. Do not optimize by dropping
verification.

## 12. Open questions for architectural review

1. Should `repository_root` be inferred exclusively from Git,
   or can an explicit CLI override be useful without weakening
   its validated identity?
2. What is the smallest correct representation for physical
   ownership of nested submodule source files?
3. Is optional `foundry.lock` sufficient when all compiler
   inputs and Git checkouts are pinned?
4. Can the existing strict Evidence schema evolve minimally,
   or should a separate version be published for manifest v2?
5. Does compilation reproducibility for `0.8.26` require
   any justified change to output normalization?
6. Which verified identity fields must be shared between
   provenance, runner and trusted gate?
7. What is the minimal trusted-policy representation of
   repository-relative workspace path and config identity?
8. Which integration inputs must be included when root and
   workspace Foundry configurations are inherited?

## 13. Status

PROPOSED. Source inspection and pilot diagnostics establish
the need for this boundary. Independent end-to-end portable
Evidence, compiler replay and trusted CI on Capminal remain
**Not tested**; none is claimed as implemented.

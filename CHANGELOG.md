# Changelog

## Unreleased — v0.6.0 release candidate

### Added
- Separate portable Direct EOA/UUPS runner for Git-pinned Foundry
  workspaces nested inside monorepos, without changing the legacy runner.
- Comparison Evidence 1.1 and build-provenance v2 with explicit
  repository, workspace, tool revision, compiler and source ownership.
- Git-attested compiler source closure across pinned submodule chains;
  isolated Standard JSON recompilation with original source-unit keys.
- Independent completed-Evidence verifier that rechecks raw capture,
  recorded producer outcome, source provenance, compiler replay,
  classification and trusted CI policy.
- Pinned external Capminal acceptance for synthetic safe and faulty
  migrations, failed-producer nonpublication and artifact mutations.
- Portable workspace v0.6 quickstart and release-candidate review notes.

### Fixed and hardened
- Keep `MATCH + CHANGED_TO_VIOLATION` as CI `BLOCK`, including a
  nonzero exit code from independent completed-Evidence verification.
- Reject forged Evidence compiler version or execution mode, compiler
  commit mismatches, unsupported short compiler identities, altered
  build artifacts, symlinked build inputs and mismatched CI run attempts.
- Support nested Foundry workspaces without a repository-root
  `foundry.toml`, while requiring a tracked workspace configuration.
- Use real GitHub Actions run identity in CI acceptance and explicitly
  synthetic context for local harness runs.
- Avoid duplicate push/PR CI runs on feature branches and cancel
  superseded pull-request checks.

### Compatibility and limitations
- Evidence 1.0, the v0.5 portable runner, existing Solidity APIs,
  Timelock adapter and classification decision semantics are retained.
- v0.6 remains one explicitly declared Direct EOA/UUPS scenario per
  invocation; other upgrade routes are not supported by this runner.
- Compiler/source replay verifies consistency of recorded observations
  but cannot independently authenticate original EVM execution or
  discover every privilege path.
- The Capminal faulty implementation is test-only and does not imply
  any vulnerability in upstream Capminal.
- **Not released:** PR #41 remains draft pending final independent
  review and successful CI on the final revision.

See [v0.6 release-candidate review](docs/releases/v0.6.0-rc-review.md)
and [portable workspace quickstart](docs/portable-workspace-v0.6.md).

## v0.5.1 - 2026-11-03

### Improved
- Added external Treasury consumer integration to Sentinel CI,
  covering safe PASS, regression BLOCK, and failed producer
  without completed Evidence publication.
- Added early Python, Forge, and pinned Git dependency checks
  before Evidence staging. Foundry may bootstrap solc before
  mandatory independent compiler replay.
- Documented the currently supported dependency layout.
- The reference consumer now provides a GitHub Job Summary
  and downloadable Evidence and diagnostics on PASS and BLOCK.

### Scope
- No change to public Solidity APIs, comparison semantics,
  Evidence schema, or the trusted policy decision table.
- Portable execution remains limited to a declared Direct
  EOA/UUPS scenario and the documented dependency layout.
- Replay does not authenticate the original EVM execution.

## v0.5.0 - 2026-11-03

### Added
- Portable runner for one declared external Direct EOA/UUPS
  producer test in a Git-tracked Foundry project.
- Solidity capture helper and versioned TOML configuration.
- Fresh Forge execution, source and build provenance checks,
  independent Python classification replay, and normalized
  independent solc recompilation.
- Atomic publication of completed verified Evidence.
- Trusted CI policy decisions: PASS, BLOCK, and REVIEW.
- Independent Treasury consumer with real GitHub Actions gate
  and protected-workflow integrity check.

### Compatibility and limits
- Existing public Solidity APIs retained.
- Timelock functionality remains separate from the portable
  Direct runner.
- No automatic discovery of privilege paths or independent
  authentication of EVM execution.

See [v0.5.0 release notes](docs/releases/v0.5.0.md).

## v0.4.1 - 2026-11-03

Consolidated release of the v0.4-A/B/C and v0.4.1 cycle.

### Added
- Direct before/after authority comparison core.
- OpenZeppelin Timelock single-operation route adapter.
- Strict Comparison Evidence 1.0 for Direct and Timelock.
- Independent Python classification and comparison replay.
- External consumer and Solidity/Python differential oracles.
- Fresh compiler build-info and source/dependency provenance.
- Evidence-to-build SHA-256 manifest binding.
- Independent normalized solc output reproduction.
- Adversarial compilation and fail-closed publication gates.

### Compatibility
- Existing AuthorityProbe public API retained.
- Legacy witness schemas 0.2, 0.3 and 0.4 retained.
- Comparison Evidence 1.0 remains a separate namespace.

### Limitations
- Experimental local Foundry testing only.
- Supported actors and governance routes remain explicit.
- Compiler replay does not authenticate EVM execution.
- No automatic privilege discovery or complete security audit.

See docs/releases/v0.4.1.md.

## v0.3.0 - 2026-11-03

### Added
- Seven Evaluator property fuzz tests.
- Two UUPS isolation fuzz tests.
- Historical Ethereum mainnet fork integration.
- PASS -> FAIL -> PASS authority regression for one actor.
- Offline fork JSON-validator and 15 regression tests.
- Sanitized fork evidence reports.
- Manual GitHub Actions evidence artifact upload.

### Verified
- Historical block hash, implementation and owner.
- Authorized and unauthorized upgrade execution.
- Snapshot isolation and state restoration.
- Independent adversarial and mutation testing.
- Successful manual GitHub fork workflow.

### Compatibility
- Solidity AuthorityProbe API unchanged.
- Evidence schema 0.4 retained.

### Limitations
- Deliberately vulnerable implementation is test-only.
- No vulnerability in Adapter8004 is asserted.
- Direct EOA and canonical UUPS scope unchanged.

## v0.2.1 - 2026-11-02

### Fixed
- Centralized evidence schema validation across CLI and Python API.
- Rejected incompatible fields in historical evidence.
- Required explicit opt-in for legacy policy replay.
- Upgraded the main execution witness to schema 0.4.

### Added
- Schema boundary regression tests.
- Current-schema witness verification and independent replay.
- API migration and pinned Foundry installation guidance.
- Published v0.2.0 consumer compatibility checks in CI.

### Scope
- No changes to the Solidity AuthorityProbe public API.
- JSON replay remains classification-only, not EVM attestation.


## v0.2.0 - 2026-11-02

### Added
- Diagnostic reasons for UNKNOWN policy results.
- Opt-in DetailedUpgradeCheckResult API.
- Solidity unit and UUPS integration tests for diagnostics.
- Diagnostic policy evidence schema 0.4.
- Seven Solidity/Python diagnostic comparison scenarios.
- Reason mutation tests and external consumer API coverage.

### Fixed
- Empty expected revert data can no longer establish PASS.
- Invalid target preconditions now produce UNKNOWN / INVALID_TARGET.
- Adversarial tests cover no-code and non-proxy targets.
- Python and Solidity apply the same rejection classification.

### Compatibility
- Original UpgradeCheckResult and status-only API retained.
- Historical schemas 0.2 and 0.3 remain readable.
- Main execution witness remains on schema 0.2.

### Limitations
- Matching revert data does not independently prove its cause.
- Scope remains direct EOA calls and canonical UUPS upgrades.
- Target preconditions do not prove genuine proxy behavior.
- JSON replay does not authenticate observed EVM state.


## v0.1.1 - 2026-11-02

### Fixed
- Policy replay self-tests no longer depend on an unrelated
  pre-existing witness file.
- Fresh-checkout replay validation is covered in CI.

### Added
- Pinned Foundry version in CI.
- Automated witness export, verification and mutation tests.
- Independent Foundry consumer example and CI compatibility tests.
- Reproducible Fortytwo x402Escrow integration.
- Deliberate PASS -> FAIL -> PASS authority regression scenario.

### Scope
- No expansion of the public AuthorityProbe API.
- Existing experimental limitations remain applicable.

## v0.1.0

- Initial experimental Foundry helper release.
- Authority observation and isolated execution.
- UUPS upgrade-policy evaluation.
- Transparent proxy and AccessControl regression fixtures.
- JSON evidence and Python policy replay.

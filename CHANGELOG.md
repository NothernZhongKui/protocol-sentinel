# Changelog

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

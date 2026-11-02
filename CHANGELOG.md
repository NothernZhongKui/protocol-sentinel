# Changelog

## v0.1.1 - Unreleased

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

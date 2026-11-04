# Documentation

## Use Sentinel

- [Solidity library quickstart](library-quickstart.md) — check an upgrade attempt in a Foundry test.
- [Portable Direct quickstart](portable-direct-v0.5.md) — run the pinned example, adapt a producer and publish evidence.
- [Direct comparison](comparative-authority-quickstart.md) — compare two active implementations.
- [Timelock route](timelock-route-quickstart.md) — use the separate OpenZeppelin route adapter.
- [Trusted CI guide](guides/ci.md) — bind the Direct runner to a protected policy.

## Understand the results

- [Results and decisions](reference/results.md) — stage status, comparison, replay and CI.
- [Configuration and artifacts](reference/configuration.md) — producer fields, CLI, output and troubleshooting.
- [Build reproducibility](build-reproducibility.md) and [threat model](threat-model.md).

## Contribute

- [Contributing](../CONTRIBUTING.md) and [architecture](architecture.md).
- [Release notes](releases/) and [changelog](../CHANGELOG.md).
- Proposed v0.6 design (not implemented): [RFC-006 — Existing Foundry pilot](rfc-006-existing-foundry-pilot.md) and [ADR-006A — Pilot boundary](adr-006a-external-oss-pilot-boundary.md).
- Design history: [RFC-004](rfc-004-comparative-authority-regression.md), [RFC-004C](rfc-004c-evidence-replay.md), [RFC-005](rfc-005-portable-evidence-ci-gate.md), and [ADRs](adr-005b-trusted-ci-gate.md). These record decisions and past proposals; current guides take precedence for usage.
- Maintainer evidence demonstrations: [Direct](c2-direct-evidence.md), [Timelock](c3-timelock-evidence.md), and [hardening](c4-hardening.md).

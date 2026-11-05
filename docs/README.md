# Documentation

## Start with a Foundry project

- [First verified result](v1-onboarding.md) — pinned Sentinel installation, `init`, `doctor`, one completed Evidence 1.1 run, and optional trusted CI.
- [Treasury walkthrough](examples/treasury.md) — full synthetic producer, fixture contracts and matching configuration.
- [Read-only doctor](guides/doctor.md) and [safe init](guides/init.md) — diagnose configuration and fill a deliberately incomplete producer.
- [Trusted GitHub CI](guides/ci.md) and [current-run Summary](guides/summary.md) — policy v2, protected-base workflow, integrity and merge rules.
- [Direct UUPS workspace runner](portable-workspace-v0.6.md) — detailed compiler and Git source requirements.
- [Solidity library](library-quickstart.md) and [direct comparison](comparative-authority-quickstart.md) — Foundry-only API.
- [OpenZeppelin Timelock helper](timelock-route-quickstart.md) — separate from the portable Direct runner.

## Reference and compatibility

- [Workspace configuration and artifacts](reference/workspace-v0.6.md) — Evidence 1.1, policy v2 and exact runner flags.
- [Results and decisions](reference/results.md), [build reproducibility](build-reproducibility.md), [architecture](architecture.md), [threat model](threat-model.md).
- [v0.5 portable runner](portable-direct-v0.5.md) and [Evidence 1.0 reference](reference/configuration.md) — retained legacy route.
- [v1.0.0 release notes](releases/v1.0.0.md) · [Changelog](../CHANGELOG.md) · [ADR-007 and design history](adr-007-v1-developer-adoption.md).

## Contribute

- [Contributing](../CONTRIBUTING.md), [milestone evidence](roadmap-v1.0.md), [trusted CI example](../examples/trusted-ci/README.md).
- Historical implementation records: [RFC-004](rfc-004-comparative-authority-regression.md), [RFC-005](rfc-005-portable-evidence-ci-gate.md), [ADR-005B](adr-005b-trusted-ci-gate.md).

# Documentation

## Use Sentinel

- [v1.0 development: first verified result](v1-onboarding.md) — from existing Foundry project to a local Evidence 1.1 result, with an explicit development commit pin. **Not a released v1.0 tag.**
- [v1 doctor](guides/doctor.md) and [safe init](guides/init.md) — read-only diagnostics and deliberately incomplete producer scaffold.

- [v0.6 workspace quickstart](portable-workspace-v0.6.md) — integrate an existing Git-pinned Foundry workspace, capture Evidence 1.1 and reverify a trusted run. Released in v0.6.0.
- [v0.5 portable quickstart](portable-direct-v0.5.md) — the earlier runner and Evidence 1.0.
- [Solidity library quickstart](library-quickstart.md) and [Direct comparison](comparative-authority-quickstart.md) — use helpers in Foundry tests without Python.
- [Timelock route](timelock-route-quickstart.md) — separate OpenZeppelin route adapter.
- [Trusted CI](guides/ci.md) — policy selection, workflow protection and decisions.
- [Direct UUPS dependency setup](portable-workspace-v0.6.md#2-install-and-configure) — reuse consumer Git-pinned OpenZeppelin and forge-std; no nested Sentinel OZ initialization required for the tested route.

## Reference

- [Workspace configuration and artifacts](reference/workspace-v0.6.md) — v0.6 CLI, policy, output and troubleshooting.
- [v0.5 configuration and artifacts](reference/configuration.md).
- [Results and decisions](reference/results.md), [build reproducibility](build-reproducibility.md), and [threat model](threat-model.md).
- [v0.6.0 release notes](releases/v0.6.0.md), [v1.0 adoption plan](roadmap-v1.0.md) and [proposed ADR-007](adr-007-v1-developer-adoption.md) — review documents; not shipped v1.0 features.

## Contribute

- [Contributing](../CONTRIBUTING.md), [architecture](architecture.md), [changelog](../CHANGELOG.md) and [release notes](releases/).
- Design history: [RFC-004](rfc-004-comparative-authority-regression.md), [RFC-004C](rfc-004c-evidence-replay.md), [RFC-005](rfc-005-portable-evidence-ci-gate.md), [ADR-005B](adr-005b-trusted-ci-gate.md). Historical proposals describe their original assumptions.
- Maintainer evidence demonstrations: [Direct](c2-direct-evidence.md), [Timelock](c3-timelock-evidence.md), [hardening](c4-hardening.md).

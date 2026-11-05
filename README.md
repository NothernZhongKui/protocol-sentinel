# Protocol Sentinel

Execution-based authority regression testing for upgradeable EVM contracts, built for Foundry.

Declare an actor who must **not** gain upgrade authority. Sentinel observes that actor's `upgradeToAndCall` attempt before and after an authorized implementation change, independently replays the recorded classification and maps it to a trusted CI decision. An operator denied an upgrade in V1 but permitted in V2 produces `CHANGED_TO_VIOLATION`; trusted CI returns `BLOCK`.

## Get started

**[First verified result — Direct UUPS](docs/v1-onboarding.md)** walks through a Git-pinned Foundry project, `sentinel init`, read-only `sentinel doctor`, the workspace verifier, and optional trusted GitHub CI.

| Task | Reference |
| --- | --- |
| Use the Solidity-only helper | [Foundry library quickstart](docs/library-quickstart.md) |
| Configure a pinned workspace and Evidence 1.1 | [Workspace reference](docs/reference/workspace-v0.6.md) |
| Enforce an authority invariant in CI | [Trusted CI guide](docs/guides/ci.md) |
| Interpret classifications and gate results | [Results and decisions](docs/reference/results.md) |
| Continue using the v0.5 runner and Evidence 1.0 | [v0.5 quickstart](docs/portable-direct-v0.5.md) |

## Scope

The portable verifier handles **one declared Direct EOA → ERC-1967/UUPS** `upgradeToAndCall(address,bytes)` attempt with empty initialization data per invocation. You supply the proxy, actor, separate valid candidate implementation, exact expected revert, and authorized transition. `init` produces an intentionally incomplete template that cannot silently verify a placeholder fixture. `doctor` is offline and read-only; it does not approve a merge.

A local `REPLAY: MATCH` means independent Python replay agrees with the captured classification; it can accompany a violation. Only a protected workflow with a trusted policy yields `PASS`, `BLOCK`, or `REVIEW` for CI. Repository branch rules must separately enforce required checks and protect the verifier, policy and producer.

Sentinel does **not** discover every privilege path, authenticate the original EVM execution, validate storage-layout safety, or replace a security audit. The separate [Timelock helper](docs/timelock-route-quickstart.md) is not supported by the portable Direct runner. See the [threat model](docs/threat-model.md).

[Documentation](docs/README.md) · [v1.0.0 release notes](docs/releases/v1.0.0.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)

## Contact

Feedback and contributions welcome on GitHub or X: [@AdvanZeroX](https://x.com/AdvanZeroX).

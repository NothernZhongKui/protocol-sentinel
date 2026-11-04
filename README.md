# Protocol Sentinel

Execution-based authority regression testing for upgradeable EVM contracts, built for Foundry.

Define an actor and an upgrade action. Sentinel probes that action before and after an authorized implementation change and compares the observations. If an operator cannot upgrade in V1 but can upgrade in V2, the comparison is `CHANGED_TO_VIOLATION`. A configured trusted CI policy maps that result to `BLOCK`.

## Get started

| Goal | Guide | Requirements |
| --- | --- | --- |
| Check a declared upgrade attempt in a Foundry test | [Solidity library](docs/library-quickstart.md) | Foundry; no Python |
| Capture and replay evidence in a Git-pinned Foundry workspace | [v0.6 workspace quickstart](docs/portable-workspace-v0.6.md) | Foundry, Python, Git and matching solc |
| Use the released v0.5 portable runner | [v0.5 quickstart](docs/portable-direct-v0.5.md) | Foundry, Python, Git and solc 0.8.24 |

The v0.6 workspace workflow in this branch is an **unreleased release candidate**. It supports a Foundry workspace at the repository root or in a monorepo, checks Git-pinned source ownership, and produces Comparison Evidence 1.1. Its interface may change before release. The v0.5 runner and Evidence 1.0 remain separate.

## Scope

The portable workflows cover one declared Direct EOA → ERC-1967/UUPS `upgradeToAndCall(address,bytes)` attempt with empty initialization calldata per run. The test author chooses the actor, candidate, expected revert, fixture and authorized transition. A separate [Timelock helper](docs/timelock-route-quickstart.md) covers a specific OpenZeppelin route; it is not supported by the portable runners.

A replay `MATCH` means Python reproduced the classification from the recorded observations. It can accompany `CHANGED_TO_VIOLATION`; it is not a merge approval. See [results](docs/reference/results.md).

**Status:** Experimental, pre-1.0. Results apply only to the declared scenario. Sentinel does not discover all privilege paths, validate storage layout, independently authenticate EVM execution or prove contract security. See the [threat model](docs/threat-model.md).

[Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)

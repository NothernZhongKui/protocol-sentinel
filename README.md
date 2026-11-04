# Protocol Sentinel

Execution-based authority regression testing for upgradeable EVM contracts, built for Foundry.

Define an actor and an upgrade action. Sentinel probes that action before and after an authorized implementation change and compares the observed behavior. For example, if an operator cannot upgrade in V1 but can upgrade in V2, the comparison reports `CHANGED_TO_VIOLATION`; the trusted CI policy maps that result to `BLOCK`.

## Choose a workflow

| Goal | Start here | Requirements |
| --- | --- | --- |
| Check authority inside a Foundry test | [Solidity library guide](docs/library-quickstart.md) | Foundry; no Python required |
| Capture evidence, replay classification and use a CI policy | [Portable Direct quickstart](docs/portable-direct-v0.5.md) | Foundry, Python and the pinned compiler |

A draft [v0.6 nested Foundry workspace guide](docs/portable-workspace-v0.6.md) documents the independently tested Capminal pilot. This is unreleased; the v0.5 quickstart remains the supported portable workflow.

The [Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer) is a separate, working integration. For API details, results, architecture and contributing, see the [documentation index](docs/README.md).

## Supported routes

| Route | Solidity helper | Portable runner | Trusted CI gate |
| --- | --- | --- | --- |
| Direct EOA → ERC-1967 / UUPS | Yes | Yes | Yes |
| EOA → OpenZeppelin Timelock → ProxyAdmin → Transparent proxy | [Separate adapter](docs/timelock-route-quickstart.md) | No | No |

The Direct route checks canonical `upgradeToAndCall(address,bytes)` with empty initialization data. Scenarios, actors and expected behavior are explicitly supplied by the test author.

## Results and trust

A replay `MATCH` means Python reproduced the classification from recorded observations. It can accompany `CHANGED_TO_VIOLATION`; it is not a merge approval. See the [results reference](docs/reference/results.md) for stage, comparison, replay and CI outcomes.

**Status:** Experimental, pre-1.0. Results apply to the declared scenario. Sentinel does not discover every privilege path, verify storage layout, authenticate EVM execution, or prove contract security. See the [threat model](docs/threat-model.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks and project layout.

## License

[MIT](LICENSE).

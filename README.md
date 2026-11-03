# Protocol Sentinel

Execution-based authority regression testing for upgradeable EVM contracts, built for Foundry.

Protocol Sentinel checks a scenario you define: can a particular actor perform an upgrade that your policy forbids? It observes the attempt before and after an authorized implementation change and compares the results.

For example, an operator might be unable to upgrade a proxy in V1 but gain that ability in V2. Sentinel can capture that change as `CHANGED_TO_VIOLATION`.

**Status:** Experimental, pre-1.0. The portable v0.5 integration is limited to declared Direct EOA/UUPS scenarios.

## Get started

- [Portable Direct quickstart](docs/portable-direct-v0.5.md) — install Sentinel in a Foundry project, capture a scenario, and run replay.
- [Working Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer) — a separate Foundry project with safe and intentionally unsafe upgrade scenarios.
- [Library quickstart](docs/library-quickstart.md) — use the Solidity helper directly without the portable evidence runner.

## How it works

1. Define the actor, proxy, candidate implementation, expected revert and policy in a Foundry test.
2. Probe the declared upgrade attempt before and after an authorized implementation change. Each probe restores its EVM state.
3. Export the observations. The portable runner validates the evidence, independently replays the classification in Python, and recompiles recorded build inputs with solc.
4. Optionally apply a trusted CI policy to decide whether the result passes, blocks, or requires review.

A successful replay means the recorded classification is consistent with the observations. It does **not** mean the upgrade is safe to merge: `MATCH` can accompany `CHANGED_TO_VIOLATION`.

| Comparison | Meaning | Trusted CI decision |
| --- | --- | --- |
| `STILL_SATISFIED` | The declared restriction holds in both stages. | `PASS` |
| `CHANGED_TO_VIOLATION` | The restriction held before but is violated after. | `BLOCK` |
| `STILL_VIOLATED` | The restriction is violated in both stages. | `BLOCK` |
| `CHANGED_TO_SATISFIED` | A previously violated restriction now holds. | `REVIEW` |
| `INDETERMINATE` | The observations do not support a definite result. | `REVIEW` |
| `INCOMPARABLE` | The stages cannot be compared under the declared scenario. | `REVIEW` |

The CI decision requires a trusted policy and protected workflow. A local run without that policy reports `NOT_EVALUATED`.

## Scope and trust

The portable runner supports direct EOA calls to ERC-1967/UUPS upgrades using `upgradeToAndCall(address,bytes)` with empty initialization data. You supply the actor, target, candidate, expected revert and the before/after fixture. It runs one configured producer per invocation. The separate [Timelock route adapter](docs/timelock-route-quickstart.md) is not part of the portable Direct runner.

A result applies only to the declared scenario. Sentinel does not discover every privilege path, verify storage layout safety, authenticate EVM execution, or establish that a contract is secure. Replayed evidence is not an execution attestation. See the [threat model](docs/threat-model.md) and [build reproducibility](docs/build-reproducibility.md).

## Run the project tests

Requirements: Git, Foundry, and Python 3.12. The full evidence suite also needs the pinned Python dependencies and solc `0.8.24+commit.e11b9ed9`.

```bash
git clone --recurse-submodules https://github.com/NothernZhongKui/protocol-sentinel.git
cd protocol-sentinel
forge build
forge test
```

For the evidence acceptance suite:

```bash
python3 -m pip install -r evidence/requirements-schema.txt -r evidence/requirements-abi.txt
bash scripts/run_comparison_c4.sh
```

See the [Direct comparison guide](docs/comparative-authority-quickstart.md), [Timelock guide](docs/timelock-route-quickstart.md), [external integration example](examples/x402/README.md), and [v0.5 release notes](docs/releases/v0.5.0.md) for more detail.

## License

[MIT](LICENSE).

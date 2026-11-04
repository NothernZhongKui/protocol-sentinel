# Contributing

Issues and pull requests are welcome. For a larger change, open an issue first to discuss the scope and the behavior being changed. Keep the PR focused and describe the scenario, expected behavior and checks run.

## Set up

Git, Foundry 1.8.7 and Python 3.12 are used in CI. The legacy evidence suite uses solc `0.8.24+commit.e11b9ed9`; the v0.6 Capminal acceptance uses `0.8.26+commit.8a97fa7a`.

```bash
git clone --recurse-submodules https://github.com/NothernZhongKui/protocol-sentinel.git
cd protocol-sentinel
python3.12 -m venv ../sentinel-venv
source ../sentinel-venv/bin/activate
python -m pip install -r evidence/requirements-schema.txt -r evidence/requirements-abi.txt
forge build
forge test
```

Some evidence scripts require a clean checkout and initialized, pinned submodules. Consult the relevant script or CI job before running it.

## Project map

| Path | Purpose |
| --- | --- |
| `src/`, `test/` | Solidity helpers, fixtures and regression tests. |
| `scripts/` | Evidence assembly, replay, policy and verification. |
| `evidence/` | Schemas, semantics and pinned Python dependencies. |
| `docs/`, `examples/` | Guides, design history and integration examples. |

See [architecture](docs/architecture.md) for responsibilities and trust boundaries.

## Checks

Run the relevant checks for your change; [CI](.github/workflows/test.yml) defines the complete suite.

| Change | Useful checks |
| --- | --- |
| Solidity | `forge fmt --check`, `forge build`, `forge test` and relevant targeted tests. |
| Replay or policy | Relevant `scripts/test_*.py` tests and `bash scripts/run_comparison_c4.sh` for the evidence pipeline. |
| v0.6 workspace and provenance | Relevant `scripts/test_workspace_*.py`, `scripts/test_source_closure.py`, `scripts/test_trusted_workspace_gate.py`, and `bash scripts/check_capu_workspace.sh` for the external acceptance. See the [quickstart](docs/portable-workspace-v0.6.md) for the Capminal compiler and network requirements. |
| Schema or semantics | `python scripts/build_comparison_schema.py --check`, `python scripts/test_comparison_schema_contract.py`, `python scripts/test_comparison_semantics_registry.py`. |
| Documentation | Check links, commands and examples against the code; run changed workflows where practical. |

Preserve published Solidity APIs and evidence compatibility unless the PR explicitly proposes a change. Keep replay independent of Solidity classification, maintain fail-closed behavior and add meaningful negative tests for changes to verification or trust boundaries. Explain compatibility effects in the PR.

# Protocol Sentinel

Execution-based authority regression testing for upgradeable Ethereum contracts.

**Status:** Research Proof of Concept  
**Scope:** Local synthetic fixture, not a production security scanner.

## The Problem

Upgradeable contracts may introduce new privileged execution paths
without changing their visible administrative configuration.

A proxy may retain the same owner, administrator and timelock delay,
while a new implementation introduces an unauthorized upgrade path.

## The Experiment

Protocol Sentinel demonstrates this behavior using OpenZeppelin
TransparentUpgradeableProxy, ProxyAdmin, TimelockController and
UUPS-compatible implementations.

| Version | Behavior |
|---------|----------|
| VaultV1 | Operator cannot upgrade directly |
| VaultV2Risky | Operator bypasses the timelock |
| VaultV2Fixed | Direct operator upgrade is rejected |

The risky implementation is installed through an authorized timelock
operation. Afterward, the operator performs another upgrade directly,
without scheduling a new operation or advancing EVM time.

## Components

- `src/VaultV1.sol` - Baseline implementation
- `test/fixtures/VaultVersions.sol` - Risky, fixed and probe implementations
- `test/helpers/AuthorityProbe.sol` - Execution observer and classifier
- `test/AuthorityRegression.t.sol` - Security regression tests
- `scripts/verify_witness.py` - JSON consistency verifier

## Foundry Library API

Protocol Sentinel is an experimental Foundry helper for
execution-based authority regression testing.

The public entry point is `src/AuthorityProbe.sol`.

The convenience API `_checkIsolatedUpgrade()` executes a
declared upgrade attempt, restores EVM state, and evaluates
the selected authorization policy.

See [Library Quick Start](docs/library-quickstart.md)
for usage examples, supported scenarios, and limitations.

## Quick Start

Requirements: Foundry, Git.

Clone the repository with submodules and run:

    forge test

To reproduce the authority regression:

    forge test --match-path test/AuthorityRegression.t.sol -vv

To generate an execution witness:

    mkdir -p artifacts/demo
    bash scripts/export_witness.sh

The script requires a clean Git working tree, records the
current source commit, runs the witness exporter and verifies
the resulting JSON.

The verifier checks internal consistency only. It does not
independently replay EVM execution.

## Policy Results

Protocol Sentinel currently implements two policies.

| Observation | NO_IMPLEMENTATION_REPLACEMENT | NO_SUCCESSFUL_UPGRADE_CALL |
|---|---|---|
| Expected rejection; implementation unchanged | PASS | PASS |
| Successful replacement with requested implementation | FAIL | FAIL |
| Successful replacement with unexpected implementation | FAIL | FAIL |
| Successful call; implementation unchanged | UNKNOWN | FAIL |
| Unexpected revert | UNKNOWN | UNKNOWN |
| Invalid preconditions or mismatched probe context | UNKNOWN | UNKNOWN |

- **PASS**: The expected rejection was observed with unchanged implementation.
- **FAIL**: The observed action violated the declared policy.
- **UNKNOWN**: Available evidence does not justify PASS or FAIL.
- **ERROR**: Reserved for execution or setup failures; not emitted separately yet.

The evaluator is pure: it reads recorded Observation data rather
than querying current EVM state.

For the current fixture, the observer models direct EOA execution
with msg.sender and tx.origin set to the actor.

A matching revert payload is evidence of the observed rejection,
not independent proof that a particular authorization branch ran.

A passing Foundry test may correctly confirm a FAIL security verdict.

## Evidence

The JSON witness contains actor, target, calldata, execution result,
implementation before and after, administrative state, timelock
operation identifier and timestamps.

Output:

    artifacts/demo/authority-regression.json

## Limitations

This prototype uses a known synthetic fixture.

It does not discover arbitrary actors, selectors, upgrade paths,
or provide exhaustive authorization analysis.

The Transparent/UUPS combination is intentionally used to demonstrate
a composition risk, not as a recommended production architecture.

The JSON verifier validates selected fields for consistency.
It does not independently replay EVM execution.

## License

To be determined before public release.

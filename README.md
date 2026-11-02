# Protocol Sentinel

Execution-based authority regression testing for upgradeable Ethereum contracts.

**Status:** Experimental Foundry library (pre-1.0)  
**Scope:** Local authority regression tests for declared actors and actions.

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

- `src/AuthorityProbe.sol` — public Foundry test helper and policy evaluator
- `test/AuthorityRegression.t.sol` — Transparent proxy / Timelock regression
- `test/RoleAuthorityRegression.t.sol` — ERC-1967 / UUPS / AccessControl regression
- `test/fixtures/` — synthetic upgrade implementations
- `scripts/export_witness.sh` — local JSON evidence export
- `scripts/verify_witness.py` — witness consistency validation
- `scripts/replay_policy.py` — Python policy evaluation from recorded JSON
- `scripts/check_policy_replay.py` — Solidity/Python verdict comparison
- `scripts/test_witness_mutations.py` — negative controls for witness validation
- `examples/x402/` — external Fortytwo contract integration experiment
- `docs/library-quickstart.md` — integration guide

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

Requirements: Foundry, Git, Python 3.

Clone with Git submodules:

~~~bash
git clone --recurse-submodules https://github.com/NothernZhongKui/protocol-sentinel.git
cd protocol-sentinel
~~~

Build and test:

~~~bash
forge fmt --check
forge build
forge test
~~~

Check policy replay against fresh Solidity observations:

~~~bash
python3 scripts/check_policy_replay.py
~~~

Generate and validate a local execution witness:

~~~bash
bash scripts/export_witness.sh
python3 scripts/test_witness_mutations.py
~~~

The witness exporter requires a clean Git working tree.

For importing the public helper into another Foundry project,
see [Library Quick Start](docs/library-quickstart.md).

For the third-party integration experiment,
see [Fortytwo x402Escrow](examples/x402/README.md).

## Reproducible Integrations

The repository includes two independently exercised integration paths.

- Standalone Foundry consumer: imports the published v0.1.0
  helper and checks the current API for compatibility.
- Fortytwo x402Escrow: reproduces a deliberately introduced
  upgrade-authority regression using pinned external source.

Run the Fortytwo regression experiment:

    bash scripts/reproduce_x402.sh

The scenario demonstrates PASS -> FAIL -> PASS as upgrade
authority is preserved, accidentally expanded, and restored.

CI runs four jobs: Foundry tests, evidence validation,
independent consumer testing, and external regression testing.

See examples/consumer/ and examples/x402/ for details.

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

The local execution witness uses schema version `0.2`.

It records the declared actor, transaction origin, target,
calldata, call result, effective implementation observations,
candidate preconditions, governance context, source commit
and selected bytecode hashes.

Generated output:

    artifacts/demo/authority-regression.json

The witness verifier checks internal consistency, including
expected identities, ERC-1967 slot identity, calldata,
source commit and selected governance invariants.

It does not independently prove that EVM execution occurred.

The Python policy replay independently evaluates saved
observations using the declared policy rules.

The project includes five Solidity/Python comparison scenarios
and eleven Python replay self-tests.

Policy replay is not independent execution attestation.

## Limitations

Protocol Sentinel is an experimental Foundry test helper,
not a production security scanner or comprehensive audit.

Its current convenience API supports:

- Declared actors and targets
- Direct EOA execution
- ERC-1967 implementation-slot observation
- Canonical UUPS `upgradeToAndCall(address,bytes)`
- Empty initialization calldata
- Local EVM execution with snapshot restoration

The helper does not discover arbitrary actors, selectors,
privilege paths or contract-mediated execution flows.

A `PASS` means the specified expected rejection was observed.
It does not establish that a contract is generally secure.

Candidate validation checks UUPS compatibility through
`proxiableUUID()`. It does not validate storage layout safety.

The initial Transparent/UUPS fixture intentionally demonstrates
a composition risk and is not a recommended production design.

The external Fortytwo example is a developer-authored local
integration experiment, not an independent adoption claim.

See [Threat Model](docs/threat-model.md) for assumptions
and outstanding validation gaps.

## License

MIT License. See [LICENSE](LICENSE).

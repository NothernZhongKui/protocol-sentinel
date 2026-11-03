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
- `src/ComparativeAuthorityProbe.sol` — experimental before/after comparison core
- `src/TimelockAuthorityProbe.sol` — experimental OpenZeppelin Timelock route adapter
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

The opt-in `_checkIsolatedUpgradeDetailed()` API returns the
observation, policy status and a diagnostic reason.

Seven reasons explain why an observation produces UNKNOWN:
INVALID_SLOT, CONTEXT_MISMATCH, INVALID_TARGET,
NON_CANONICAL_CALLDATA, INVALID_CANDIDATE,
UNEXPECTED_REVERT and SUCCESS_WITHOUT_REPLACEMENT.

The original status-only API remains available.

See [Library Quick Start](docs/library-quickstart.md)
for usage examples, supported scenarios, and limitations.

## Timelock Route Adapter — v0.4 series

TimelockAuthorityProbe supports one
contract-mediated administrative upgrade route:

EOA executor -> TimelockController -> ProxyAdmin ->
TransparentUpgradeableProxy.

It evaluates two independently declared properties:
READY_UPGRADE_SUCCEEDS and
NOT_READY_EXECUTION_REJECTED.

It also compares observations across distinct active
implementations while checking recorded governance
preconditions for comparability.

The adapter requires explicit scheduling and local
Foundry execution. It does not discover permissions,
execute live-chain transactions or authenticate
observation provenance.

See [Timelock Route Quick Start](docs/timelock-route-quickstart.md)
and the independent consumer example in
examples/consumer/SentinelTimelockConsumer.t.sol.

## Comparison Evidence and Build Reproducibility — v0.4.1

Experimental comparison Evidence 1.0 supports two routes:
`DIRECT_EOA_UUPS` and `OZ_TIMELOCK_SINGLE`.

Real Foundry observations are exported into strict JSON.
Python independently recomputes canonical calldata,
scenario identity, policy evaluations and comparison results.

Run the complete evidence acceptance suite:

~~~bash
python3 -m pip install -r evidence/requirements-schema.txt -r evidence/requirements-abi.txt
bash scripts/run_comparison_c4.sh
~~~

This includes isolated external replay, Solidity/Python
differential parity, forged-evidence controls and legacy
schema compatibility.

Direct and Timelock evidence publication also requires
fresh Foundry compiler build-info, a verified provenance
manifest and independent solc 0.8.24 recompilation.
Normalized compiler contracts and sources must match
before a run can be published.

**Replay consistency is not execution authentication.**
Evidence provenance remains `UNAUTHENTICATED`.

See [C4 Hardening](docs/c4-hardening.md),
[Build Reproducibility](docs/build-reproducibility.md),
[v0.4.1 Release Notes](docs/releases/v0.4.1.md) and
[ADR-004C](docs/adr-004c-evidence-replay.md).

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

## Pinned Ethereum Mainnet Fork

An optional integration test runs against the historical
Ethereum mainnet state of Adapter8004.

- Chain ID: 1
- Block: 24995819
- Block hash: 0x7ed82b73024b26c48660f875e9e6816e16102b33731b504b8b86746ee10abc68
- Proxy: 0xde152AfB7db5373F34876E1499fbD893A82dD336

The experiment includes four fork tests covering:

1. An unrelated EOA cannot perform an upgrade.
2. The historical owner's upgrade succeeds.
3. Isolated Sentinel probes detect replacement and restore state.
4. The same outsider transitions PASS -> FAIL -> PASS across
   historical, deliberately over-permissive, and corrected implementations.

The regression scenario installs test-only UUPS implementations
through the authorized historical owner on the local fork.
The deliberately over-permissive implementation grants upgrade
authority to the outsider; the corrected implementation restores
owner-only authorization.

These test implementations are not deployed Adapter8004 versions.
The scenario demonstrates detection of an intentionally introduced
authority regression against real historical proxy state.
It does not establish a vulnerability in Adapter8004.

The reproduction script requires all four fork tests to succeed
and rejects empty or skipped executions.

The owner's successful upgrade is a positive control
for the NO_IMPLEMENTATION_REPLACEMENT policy.
It is not evidence of a vulnerability.

Run with an archive-capable Ethereum RPC:

~~~bash
ETH_RPC_URL=https://eth.drpc.org bash scripts/reproduce_adapter8004_fork.sh
~~~

The script verifies the pinned block hash, implementation
and owner before executing the fork tests.

Successful runs also save a sanitized JSON report at
`artifacts/fork/adapter8004-mainnet-24995819.json`.

The report includes the commit SHA, source file hashes,
tool versions, verified deployment metadata, and test statuses.
It does not include the RPC URL or credentials. An uncommitted
working tree is explicitly identified in the report.

The manual GitHub Actions workflow uploads the report as
a downloadable artifact retained for 14 days.

The report summarizes test results, not individual EVM
observations or cryptographic proof of execution.

The regular CI does not depend on a public archive RPC.
A separate workflow_dispatch job permits manual execution.
Set the optional ETHEREUM_ARCHIVE_RPC_URL repository secret
to use a dedicated archive provider. Without it, the
manual workflow uses the public dRPC endpoint.

This experiment executes locally on a Foundry fork.
No live-chain upgrade transaction is broadcast.

## Reproducible Integrations

The repository includes three independently exercised integration paths.

- Standalone Foundry consumer: imports the published v0.1.0
  helper and checks the current API for compatibility.
- Fortytwo x402Escrow: reproduces a deliberately introduced
  upgrade-authority regression using pinned external source.
- Adapter8004 historical Ethereum mainnet fork: demonstrates a test-only
  PASS -> FAIL -> PASS authority regression on real proxy state.

Run the Fortytwo regression experiment:

    bash scripts/reproduce_x402.sh

The scenario demonstrates PASS -> FAIL -> PASS as upgrade
authority is preserved, accidentally expanded, and restored.

CI covers Foundry tests, legacy evidence, independent
consumers, comparison evidence C1–C4, independent compiler
replay gates and external regressions.

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

An empty expected revert cannot justify PASS.
It produces UNKNOWN when a rejected call has no usable
authorization evidence.

A matching nonempty revert payload is evidence of the observed rejection,
not independent proof that a particular authorization branch ran.

A passing Foundry test may correctly confirm a FAIL security verdict.

## Evidence

New execution witnesses and diagnostic policy matrices
use schema `0.4`, including `reason` and
`target_valid_at_observation`.

Python independently recomputes status and reason from
recorded observations. Current schema validation is
strict by default.

Historical schemas `0.2` and `0.3` require
`--allow-legacy`. They do not establish target validity.
Replay does not authenticate the recorded EVM state.

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
and thirteen Python replay self-tests, plus seven
cross-language diagnostic scenarios and reason mutation tests.

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

The direct convenience API does not discover arbitrary
actors, selectors or privilege paths. A separate Timelock
adapter supports one declared contract-mediated route.

A `PASS` means the specified expected rejection was observed.
It does not establish that a contract is generally secure.

Candidate validation checks UUPS compatibility through
`proxiableUUID()`. It does not validate storage layout safety.

Target preconditions require code at the target, a nonzero
ERC-1967 implementation address, and code at that address.
These checks do not prove that the target is an authentic
proxy or actually delegates to the recorded implementation.

The initial Transparent/UUPS fixture intentionally demonstrates
a composition risk and is not a recommended production design.

The external Fortytwo example is a developer-authored local
integration experiment, not an independent adoption claim.

See [Threat Model](docs/threat-model.md) for assumptions
and outstanding validation gaps.

## License

MIT License. See [LICENSE](LICENSE).

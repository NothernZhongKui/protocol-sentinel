# Protocol Sentinel — Threat Model

Status: Experimental Foundry library (pre-1.0)
Scope: Authority Regression / Local EVM

## 1. Security Objective

Detect whether an implementation upgrade introduces an
unauthorized direct upgrade path for a declared actor.

Primary policy (AR-001):

The operator must not directly replace the proxy implementation.

## 2. System Under Test

Two independent synthetic fixture families use the same
AuthorityProbe observer and evaluator.

### Transparent proxy / Timelock fixture

- TransparentUpgradeableProxy
- ProxyAdmin controlled by TimelockController
- TimelockController with a 48-hour minimum delay
- VaultV1, VaultV2Risky, VaultV2Fixed and UpgradeProbe

The Transparent/UUPS composition is an intentional
risk demonstration, not a production recommendation.

### ERC-1967 / UUPS / AccessControl fixture

- ERC1967Proxy
- AccessControl-based upgrade authority
- RoleVaultV1, RoleVaultV2Risky and RoleVaultV2Fixed

The project also includes a local integration experiment
with the open-source Fortytwo x402Escrow contract.

The external contract is not modified.

## 3. Actors

The Transparent proxy fixture declares:

- Proposer: schedules timelock operations
- Executor: executes ready timelock operations
- Operator: must not upgrade directly
- Outsider: has no upgrade privileges
- Timelock: controls the authorized administrative upgrade path

The AccessControl fixture separates authorized governance
from an operator that must not acquire upgrade authority.

The Fortytwo experiment distinguishes an authorized owner
from DEFAULT_ADMIN_ROLE and FACILITATOR_ROLE accounts.

Only explicitly declared actor/action pairs are evaluated.

## 4. Threat Scenario

1. VaultV1 rejects direct operator upgrades.
2. VaultV2Risky is installed through an authorized timelock operation.
3. The administrative configuration remains unchanged.
4. VaultV2Risky permits the operator to authorize a UUPS upgrade.
5. The operator replaces the implementation without a new
   timelock schedule or additional time advancement.

The observed implementation change violates AR-001.

## 5. Security Properties

AR-001: Direct operator upgrade is rejected.

AR-002: A newly scheduled authorized upgrade respects the
required timelock delay.

AR-003: Expected administrative configuration remains unchanged.

AR-001 and AR-003 are independent properties.

Unchanged owner and delay do not establish AR-001.

## 6. Detection Method

The observer executes a declared local EVM call and records:

- Actor and transaction origin
- Target and exact calldata
- Execution success and return/revert data
- Implementation slot values before and after execution
- Candidate validation result captured at observation time

The current helper supports a canonical
upgradeToAndCall(address,bytes) call with empty initialization data.

The evaluator uses the recorded Observation and declared
expectations without making additional EVM calls.

Two policies are implemented:

### NO_IMPLEMENTATION_REPLACEMENT

A successful call changing the implementation is FAIL,
even if the resulting address differs from the requested candidate.

An expected rejection with unchanged implementation is PASS.

A successful call without implementation replacement is UNKNOWN.

### NO_SUCCESSFUL_UPGRADE_CALL

A successful matching upgrade call is FAIL, regardless of
whether the implementation address changes.

An expected rejection with unchanged implementation is PASS.

Unexpected reverts and insufficient evidence produce UNKNOWN.

### Result limitations

Candidate preconditions and the expected rejection are defined
for a known fixture. A matching revert payload does not prove
the exact source-level authorization path.

ERROR is reserved and is not yet emitted independently.

Isolated probes restore EVM state using Foundry snapshots.
The current default execution model is direct EOA impersonation,
not arbitrary contract-mediated execution.

## 7. Assumptions

- Actors are known and explicitly supplied.
- The fixture is correctly initialized.
- The proposed implementation is UUPS-compatible.
- Storage layouts are compatible across fixture versions.
- The expected authorization error is known.
- The tested implementation slot is correct for this fixture.
- Each Foundry test starts from isolated state.
- The operator is not impersonating Timelock.

Reading the ERC-1967 admin slot is fixture-specific.
In OpenZeppelin v5, the transparent proxy administrator
is immutable; slot inspection is not a universal identity proof.

## 8. Out of Scope

The prototype does not:

- Discover arbitrary actors or upgrade entrypoints.
- Enumerate all possible privilege escalation paths.
- Detect compromised private keys.
- Prove that all queued governance operations are safe.
- Analyze arbitrary real-world deployments.
- Perform formal verification.
- Guarantee that a protocol is secure.
- Monitor live blockchain activity.

The current witness is generated from a local execution,
not from a public Ethereum transaction.

## 9. Evidence Limitations

The JSON witness is generated from local Foundry execution.
It is not a public-chain transaction record or cryptographic
proof that the claimed execution occurred.

The verifier checks internal consistency, known identities,
the recorded source commit, selected governance invariants
and the shape of recorded bytecode hashes.

The verifier does not independently reconstruct the entire
EVM execution or authenticate an external deployment.

Python policy replay checks verdict semantics from recorded
observations. Five Solidity/Python scenarios and twelve Python
self-tests are included.

Diagnostic policy evidence uses schema 0.3 and requires
a reason field. The main witness retains schema 0.2.

Six diagnostic scenarios are compared across Solidity
and Python. Reason mutation tests check inconsistent evidence.

Mutation tests exercise rejection of malformed or
inconsistent witness data.

Pinned Foundry dependencies and explicit remappings support
reproducible builds, but identical results across arbitrary
external environments are not guaranteed.

## 10. Open Validation Gaps

Implemented and tested:

- Two independent upgrade fixture families
- Actor, transaction-origin and target binding
- ERC-1967 implementation-slot identity checks
- Effective implementation address comparison
- Candidate precondition negative controls
- Unexpected-revert and redirected-upgrade scenarios
- Snapshot-based state restoration
- Pure policy evaluation
- JSON consistency validation and mutation controls
- Solidity/Python policy replay comparison
- One local integration with an external open-source contract

Remaining limitations:

- Only declared actors and entrypoints are covered
- No arbitrary privilege-path discovery
- No contract-mediated execution adapter
- No live blockchain monitoring
- Matching revert data cannot prove its root cause
- No independent EVM execution attestation
- No independent confirmation of deployed bytecode identity
- No general storage-layout compatibility verification
- No independently maintained third-party integration
- The evidence pipeline does not authenticate external EVM execution

These limitations must remain visible in reports
and release documentation.

## 11. Intended Use

Local security regression testing, research and evaluation
of execution-based authorization checks in Foundry.

Not a substitute for a security audit.

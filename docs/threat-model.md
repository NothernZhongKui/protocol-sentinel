# Protocol Sentinel — Threat Model

Status: Experimental Foundry library (pre-1.0)
Scope: Authority Regression / Local EVM

## Current portable workflow and trust boundaries

The v0.6 workspace runner executes a consumer-supplied Foundry producer, captures Comparison Evidence 1.1, checks Git-owned source closure and build inputs, independently replays the recorded classification in Python, and reproduces normalized compiler outputs in an isolated source snapshot. An optional trusted policy makes a separate CI decision. The completed-run verifier rechecks a trusted bundle and its recorded producer result; it does not re-execute the original EVM test. The separate v0.5 runner produces Evidence 1.0. See the [workspace guide](portable-workspace-v0.6.md) for the unreleased v0.6 scope.

| Boundary | What is checked | What it does not establish |
| --- | --- | --- |
| Consumer producer | One selected test executes and exports a capture. | The test, fixture, actor selection and expected revert describe a complete or honest security property. |
| Evidence and Python replay | Recorded observations, identity and classification are checked for consistency. | Authenticity of the underlying EVM execution or safety beyond the declared scenario. |
| Compiler replay | Recorded inputs reproduce normalized compiler contracts and sources. | Trusted source authorship, deployed bytecode identity, or execution provenance. |
| Trusted CI | A policy binds the required producer, repository and CI context; the verified result is mapped to a decision. | That candidate-controlled workflow or policy changes are protected unless repository rules enforce the boundary. |

A malicious or incorrect producer can manufacture a passing scenario or omit an important one. A fully fabricated but internally consistent evidence bundle is not independently authenticated. Review producer and fixture changes, required scenario inventory, pinned verifier and policy as well as the code under test. Ensure repository rules prevent unreviewed replacement or bypass of required workflows and checks. A local `MATCH` is classification agreement, not approval to merge. See [CI guide](guides/ci.md) and [build reproducibility](build-reproducibility.md).

The fixture-specific material below describes the original authority regression model; it does not limit the preceding boundaries to those fixtures.

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
- Target code and ERC-1967 implementation-code preconditions
  captured before execution

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

INVALID_TARGET prevents classification as PASS or FAIL when
the recorded target preconditions are not satisfied.

These preconditions are necessary plausibility checks, not
proof of proxy identity or delegatecall behavior.

ERROR is reserved and is not yet emitted independently.

Isolated probes restore EVM state using Foundry snapshots.
The AuthorityProbe convenience API uses direct EOA
impersonation. The separate Timelock route adapter
supports one declared contract-mediated upgrade route,
not arbitrary governance execution.

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

## 9. Legacy witness evidence limitations

This section describes the earlier witness schemas 0.2–0.4, separate from Comparison Evidence 1.0 and the v0.6 Evidence 1.1 workflow introduced above.

The JSON witness is generated from local Foundry execution.
It is not a public-chain transaction record or cryptographic
proof that the claimed execution occurred.

The verifier checks internal consistency, known identities,
the recorded source commit, selected governance invariants
and the shape of recorded bytecode hashes.

The verifier does not independently reconstruct the entire
EVM execution or authenticate an external deployment.

Python policy replay checks verdict semantics from recorded
observations. Five Solidity/Python scenarios and thirteen Python
self-tests are included.

The earlier execution witnesses and diagnostic policy evidence
use schema 0.4, requiring reason and
target_valid_at_observation.
Legacy evidence requires explicit replay opt-in.

Seven diagnostic scenarios are compared across Solidity
and Python. Mutation tests reject inconsistent target flags,
status values and diagnostic reasons.

Historical 0.2 and 0.3 witnesses lack target-validity evidence.
Neither historical nor current JSON authenticates EVM execution.

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
- No arbitrary contract-mediated execution adapter;
  only the declared OpenZeppelin Timelock route is supported
- No live blockchain monitoring
- Matching revert data cannot prove its root cause
- No independent EVM execution attestation
- No independent confirmation of deployed bytecode identity
- No general storage-layout compatibility verification
- No proof that target bytecode implements genuine proxy behavior
- No independently maintained third-party integration
- The evidence pipeline does not authenticate external EVM execution

These limitations must remain visible in reports
and release documentation.

## 11. Intended Use

Local security regression testing, research and evaluation
of execution-based authorization checks in Foundry.

Not a substitute for a security audit.

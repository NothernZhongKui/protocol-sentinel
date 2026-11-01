# Protocol Sentinel — Threat Model

Status: Research PoC v0.1
Scope: Authority Regression / Local EVM

## 1. Security Objective

Detect whether an implementation upgrade introduces an
unauthorized direct upgrade path for a declared actor.

Primary policy (AR-001):

The operator must not directly replace the proxy implementation.

## 2. System Under Test

The synthetic fixture contains:

- TransparentUpgradeableProxy
- ProxyAdmin owned by TimelockController
- TimelockController with a 48-hour minimum delay
- VaultV1
- VaultV2Risky
- VaultV2Fixed
- UpgradeProbe

The UUPS-compatible implementation behind a transparent proxy
is an intentional composition-risk demonstration.

It is not a production architecture recommendation.

## 3. Actors

Proposer: schedules authorized timelock operations.

Executor: executes ready timelock operations.

Operator: must not upgrade the proxy directly.

Outsider: has no privileged authority.

Timelock: authorized owner of the administrative upgrade path.

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

The JSON witness records observed execution data and
the preparatory Timelock operation context.

The Python verifier checks selected internal consistency
conditions but does not independently execute or replay EVM code.

The report is not a cryptographic proof of execution.

Source provenance, code hashes and independently verified
deployment identity require further work.

## 10. Open Validation Gaps

Completed in the current research iteration:

- Invalid-candidate negative controls
- Unexpected-revert classification tests
- Clean-checkout reproduction
- EVM snapshot isolation tests
- Actor/target binding tests
- Redirected implementation replacement regression test
- Direct EOA sender/origin regression test
- Deterministic pure-evaluator regression test
- Strict witness consistency validation with mutation tests

Remaining limitations:

- Observation depends on a trusted implementation slot identity.
- Only declared actors and entrypoints are covered.
- Contract-mediated execution requires a separate adapter.
- A passing rejection does not establish its root cause.
- JSON consistency validation is not independent execution replay.
- Timelock operation identity is not fully reconstructed from JSON.
- Exact cross-environment binary reproduction remains unverified.
- A second independent upgrade fixture is required to demonstrate reuse.
- A standalone security-policy CI gate is not yet implemented.

These limitations must remain visible in reports and documentation.

## 11. Intended Use

Educational research, deterministic regression testing,
and evaluation of an execution-based authorization probe.

Not a substitute for a security audit.

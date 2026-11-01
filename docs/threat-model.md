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

The AuthorityProbe observes an actual local EVM call.

Inputs:
- Actor
- Target
- Calldata
- Implementation storage slot
- Expected implementation and authorization rejection

Observations:
- Execution success
- Return or revert data
- Implementation before execution
- Implementation after execution

PASS means the expected authorization rejection occurred
and the implementation remained unchanged.

FAIL means a successful unauthorized call changed the
implementation to the expected target.

UNKNOWN means the observation does not justify either conclusion.

ERROR is reserved for setup or execution failures and is
not yet separately implemented by the probe.

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

Before declaring the experiment complete:

- Add an invalid-upgrade-target negative control.
- Parameterize the operator and delay in repeated tests.
- Confirm that unexpected reverts produce UNKNOWN.
- Separate policy failures from tool execution errors.
- Document the exact dependency revisions.
- Reproduce the suite from a clean checkout.

These gaps must remain visible in reports and documentation.

## 11. Intended Use

Educational research, deterministic regression testing,
and evaluation of an execution-based authorization probe.

Not a substitute for a security audit.

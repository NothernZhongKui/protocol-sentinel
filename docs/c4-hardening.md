# C4 — Evidence Hardening & Independent Reproduction

Status: IMPLEMENTED FOR REVIEW
Scope: Protocol Sentinel v0.4-C
Architecture: RFC-004C / ADR-004C

## Implemented

C4 adds verification without changing production Solidity APIs.

### External consumer

Three real Evidence 1.0 artifacts are independently replayed
outside the repository:

- Direct EOA / UUPS
- OpenZeppelin Timelock Ready
- OpenZeppelin Timelock Waiting

The isolated consumer receives only Python replay code,
the strict schema, semantics registry and evidence JSON.

It does not require Foundry, Solidity sources, Git or RPC.

Three forged-evidence negative controls must be rejected.

### Solidity/Python differential parity

Direct route:
- 8 mutation cases
- 48 classification fields
- 48/48 Solidity/Python matches

Timelock route:
- 21 cases for each of Ready and Waiting
- 42 total cases
- 27 completed comparisons
- 15 InvalidTimelockPreparation errors
- 162 comparison fields and 15 preparation failure codes
- 42/42 Solidity/Python matches

Both differential checkers reject deliberately modified
Solidity oracle outputs.

The oracle computations are performed by the frozen
Solidity evaluators and comparators. Python independently
computes its expectations from the same observations.

Synthetic mutations test classifier behavior.
They do not represent independently observed EVM executions.

### Legacy compatibility

Five fresh legacy-policy scenarios are checked across
schema 0.2, 0.3 and 0.4 shapes:

- 15/15 classification parity
- 10/10 explicit legacy opt-in controls
- Legacy/comparison format isolation

Schemas 0.2 and 0.3 are explicitly opt-in.
The comparison schema 1.0 is separate.

The legacy-shaped samples are derived from fresh 0.4
observations, not archived historical witness files.

## Reproduction

Requirements: Foundry 1.8.7, Python 3.12 and the pinned
dependencies in evidence/requirements-schema.txt and
evidence/requirements-abi.txt.

From the repository root:

    bash scripts/run_comparison_c4.sh

The script generates fresh C2 and C3 evidence, runs both
Solidity differential oracles, checks independent Python
parity, rejects forged oracle results, reproduces evidence
in an isolated consumer and checks legacy compatibility.

CI runs the same entry point in an independent C4 job.

## Trust boundary

A matching replay proves consistency between the recorded
observations and frozen classification semantics.

It does not authenticate observation origin, real-chain
execution, actor control, transaction inclusion, source
authenticity or the general security of a contract.

Execution provenance remains UNAUTHENTICATED.

Source hashes establish consistency with the local checkout,
not an externally trusted execution attestation.

## Compatibility

Unchanged production APIs:

- src/AuthorityProbe.sol
- src/ComparativeAuthorityProbe.sol
- src/TimelockAuthorityProbe.sol

No execution adapters, RPC integrations or new evidence
schema versions were added.

The existing C1, C2, C3 and legacy pipelines remain
separate and continue to run in CI.

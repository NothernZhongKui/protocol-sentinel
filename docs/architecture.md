# Architecture

Sentinel separates observing EVM behavior from evaluating it, reproducing the classification, and deciding CI policy.

| Component | Responsibility | Entry points |
| --- | --- | --- |
| Observation and evaluation | Execute isolated upgrade attempts, restore state, evaluate declared policy. | [AuthorityProbe.sol](../src/AuthorityProbe.sol) |
| Direct comparison and capture | Compare two active implementations and export observations. | [ComparativeAuthorityProbe.sol](../src/ComparativeAuthorityProbe.sol), [DirectComparisonCapture.sol](../src/DirectComparisonCapture.sol) |
| Timelock route | Observe and compare the declared OpenZeppelin administrative route. | [TimelockAuthorityProbe.sol](../src/TimelockAuthorityProbe.sol) |
| Evidence and replay | Assemble and validate recorded evidence; independently recompute Direct classification. | [run_portable_direct.py](../scripts/run_portable_direct.py), [replay_direct_comparison.py](../scripts/replay_direct_comparison.py), [schema and semantics](../evidence/) |
| Policy | Map verified comparisons to a separate CI decision and bind a trusted scenario. | [ci_policy.py](../scripts/ci_policy.py), [trusted_direct_gate.py](../scripts/trusted_direct_gate.py) |

The Solidity and Python classification implementations are intentionally independent so replay can detect disagreements. They must preserve the same specified semantics; removing one as “duplicate” would remove that cross-check.

The runner checks recorded build inputs and recompiles them with solc. This is not independent EVM execution attestation. See [build reproducibility](build-reproducibility.md), [threat model](threat-model.md), and [ADR-005B](adr-005b-trusted-ci-gate.md).

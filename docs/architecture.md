# Architecture

Sentinel separates execution, observation, classification, replay and policy.

| Component | Responsibility | Entry point |
| --- | --- | --- |
| Solidity helper | Execute isolated declared attempts, restore state, evaluate and compare observations. | [AuthorityProbe.sol](../src/AuthorityProbe.sol), [ComparativeAuthorityProbe.sol](../src/ComparativeAuthorityProbe.sol), [DirectComparisonCapture.sol](../src/DirectComparisonCapture.sol) |
| Workspace runner | Execute one fresh producer; assemble Evidence 1.1 and optionally apply trusted policy. | [run_workspace_direct.py](../scripts/run_workspace_direct.py) |
| Workspace provenance | Resolve checkout and submodule identities; attest compiler source closure and build inputs. | [workspace_context.py](../scripts/workspace_context.py), [source_closure.py](../scripts/source_closure.py), [workspace_provenance.py](../scripts/workspace_provenance.py) |
| Replay | Independently reproduce recorded classification and normalized compiler output. | [replay_direct_comparison.py](../scripts/replay_direct_comparison.py), [replay_workspace_build.py](../scripts/replay_workspace_build.py) |
| Trusted policy and reverification | Bind CI context and scenario, map classification to decision, and recheck a completed trusted bundle. | [trusted_workspace_gate.py](../scripts/trusted_workspace_gate.py), [verify_workspace_run.py](../scripts/verify_workspace_run.py) |
| Timelock | Separate OpenZeppelin route helper; outside the portable Direct runner. | [TimelockAuthorityProbe.sol](../src/TimelockAuthorityProbe.sol) |

The Solidity and Python classification implementations are intentionally independent: replay can detect disagreement between implementations, not independently authenticate execution. Their specified semantics must remain aligned.

The v0.5 [portable runner](../scripts/run_portable_direct.py), Evidence 1.0 and v1 build provenance remain separate from the v0.6 workspace runner, Evidence 1.1 and v2 provenance. See the [workspace guide](portable-workspace-v0.6.md), [threat model](threat-model.md) and [CI guide](guides/ci.md).

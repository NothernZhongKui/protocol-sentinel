# Workspace runner reference — v0.6

This reference describes the released v0.6 workspace runner and Evidence 1.1. Start with the [quickstart](../portable-workspace-v0.6.md). The [v0.5 reference](configuration.md) describes the separate legacy runner and Evidence 1.0.

## Producer configuration

The tracked TOML contains exactly `[sentinel]` and `[producer]`. Unknown or missing fields are rejected.

| Field | Requirements |
| --- | --- |
| `sentinel.config_version` | String `"1"`. |
| `sentinel.route` | `"DIRECT_EOA_UUPS"`. |
| `producer.id` | Identifier containing letters, digits or underscores, starting with a letter or underscore. |
| `producer.contract` | Test contract name, same identifier format. |
| `producer.test` | Function name, same identifier format, starting with `test_`. Must select exactly one successful test. |
| `producer.source` | Workspace-relative `test/*.sol` path without `..`; producer must be owned by the consumer checkout. |
| `producer.fixture_id` | Nonempty string, at most 128 characters. |
| `producer.scenario_id` | `0x` plus 64 hex digits; must match the producer's exported `bytes32`. |

## CLI

| Runner option | Meaning |
| --- | --- |
| `--project` | Required Foundry workspace path. |
| `--tool-root` | Installed Git-pinned Sentinel path; defaults to `<project>/lib/protocol-sentinel`. |
| `--config` | Required workspace-relative producer TOML path. |
| `--solc` | Required path to the executable compiler matching the recorded build identity. |
| `--trusted-policy` | Optional absolute policy path outside the consumer repository. Omit for local verification. |

The completed-run verifier takes the same options plus required `--run-dir`, and requires `--trusted-policy`. It verifies trusted completed runs only; local runs without a gate are not accepted by this verifier. A `PASS` printed for producer execution or compiler replay is a technical-stage status, not an authority-policy decision; inspect `CLASSIFICATION`, `REPLAY`, and `CI DECISION` separately.

| Invocation | Exit | Meaning |
| --- | --- | --- |
| Runner without policy | `0` | Verification completed; decision is `NOT_EVALUATED`. Inspect classification. |
| Runner without policy | Nonzero | Setup or verification failed. |
| Runner with policy, or completed-run verifier | `0` / `2` / `3` | PASS / BLOCK or error / REVIEW. |

## Trusted policy

The policy is a TOML file selected by trusted CI outside the consumer checkout. The gate accepts exactly `[policy]` and one `[[required_scenario]]`:

| Field | Meaning |
| --- | --- |
| `policy.version` | `"2"`. |
| `policy.repository` | GitHub workflow repository, `owner/name`. |
| `policy.consumer_repository` | Consumer identity, `owner/name`; it can differ from the workflow repository. |
| `policy.consumer_commit` | Exact lowercase 40-character SHA matching the consumer checkout. |
| `policy.workspace` | Workspace path relative to the consumer Git root, or `.` at the root. |
| `policy.workflow` | Workflow path under `.github/workflows/` ending in `.yml` or `.yaml`. |
| `policy.tool_commit` | Exact lowercase 40-character SHA matching the installed Sentinel gitlink. |
| `required_scenario` | Exactly one entry with `id`, `scenario_id`, `route`, `source`, `contract`, `test`, `fixture_id`; values must match the producer and route. |

The gate also requires `GITHUB_REPOSITORY`, `GITHUB_SHA`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT` and `GITHUB_WORKFLOW_REF`. It checks the workflow repository and path against policy and records the CI context. The consumer commit is separately checked against `policy.consumer_commit`; `GITHUB_SHA` identifies the workflow context and need not equal the consumer commit.

The protected workflow must establish which consumer commit and producer are required. A candidate-controlled policy or environment is not a trust anchor. The [acceptance harness](../../scripts/check_capu_workspace.sh) constructs policy v2 for a pinned test fixture; its synthetic local context is not a production CI recipe. See [CI guide](../guides/ci.md).

## Completed artifacts

A successful run is published under `artifacts/sentinel/runs/completed/<run-id>/` in the workspace. A BLOCK or REVIEW can still publish a verified bundle; a setup or verification failure does not publish a completed bundle.

| Path | Contents |
| --- | --- |
| `raw-capture.json` | Solidity capture. |
| `forge-results.json` | Recorded producer result. |
| `build/build-provenance.json`, `build/build-info/` | v2 source and compiler provenance and build units. |
| `evidence.json` | Comparison Evidence 1.1. |
| `verification.json` | Replay, build and decision summary. |
| `ci-gate.json` | Policy decision and CI context; created only for a trusted run. |

The independent verifier requires exactly these six top-level entries including `ci-gate.json`, validates the bundle, and rejects unexpected or symlinked build artifacts. It replays compiler output and classification but does not re-execute the original Foundry producer.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `Dirty consumer checkout` or `Dirty submodule` | Commit the integration and initialize pinned submodules; inspect Git status at the repository and submodule roots. |
| `Missing Foundry workspace` | Pass the workspace directory containing `foundry.toml` as `--project`. |
| `Tool is not a registered Git submodule` / revision mismatch | Install Sentinel as a clean pinned submodule in the consumer's Git submodule chain; supply `--tool-root` if needed. |
| `Evidence output directory must be Git-ignored` | Ignore `artifacts/sentinel/runs/` relative to the workspace. |
| `Producer failed or ambiguous` | Check exact source, contract and test selection and the printed Forge diagnostics. |
| `Captured scenario ID differs from trusted producer` | Match the TOML scenario ID to the Solidity export. |
| Compiler identity or source-closure error | Supply the matching solc binary; check tracked source ownership, gitlinks, inherited configs and unsupported symlinks or outside-checkout paths. |
| Trusted policy / CI context mismatch | Check the protected policy fields, consumer and tool commits, workspace, and GitHub environment; a different run attempt changes the recorded gate. |

Failures after staging begins print the diagnostic staging path. See the [quickstart](../portable-workspace-v0.6.md) for producer setup.

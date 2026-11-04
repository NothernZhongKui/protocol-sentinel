# Portable Direct configuration and artifacts

Applies to the v0.5.1 portable runner and Evidence 1.0. Start with the [v0.5 quickstart](../portable-direct-v0.5.md). For the unreleased v0.6 workspace runner and Evidence 1.1, see the [workspace reference](workspace-v0.6.md).

## Producer configuration

The tracked TOML must contain exactly `[sentinel]` and `[producer]`, with the fields below. Unknown or missing fields are rejected.

| Field | Meaning and constraints |
| --- | --- |
| `sentinel.config_version` | String `"1"`. |
| `sentinel.route` | String `"DIRECT_EOA_UUPS"`. |
| `producer.id` | Identifier: letters, digits, underscore; starts with a letter or underscore. |
| `producer.contract` | Solidity test contract name; same identifier format. |
| `producer.test` | Test function name; same identifier format and starts with `test_`. Must select one passing test. |
| `producer.source` | Relative Solidity path under `test/`, without `..`. |
| `producer.fixture_id` | Nonempty fixture description, at most 128 characters. |
| `producer.scenario_id` | `0x` plus 64 hex digits; must equal the Solidity export's scenario ID. |

Example configuration: [quickstart](../portable-direct-v0.5.md#3-configure-and-commit).

## Runner options

| Option | Meaning |
| --- | --- |
| `--project` | Consumer project root; defaults to the current directory. |
| `--config` | Project-relative TOML path, default `sentinel.toml`. |
| `--trusted-policy` | Absolute policy path outside the consumer checkout, selected by trusted CI. Omit for local verification. |

The producer config, tracked project files and pinned submodules must be clean; the output path must be ignored. See [requirements](../portable-direct-v0.5.md#requirements).

| Mode | Exit | Meaning |
| --- | --- | --- |
| Local | `0` | Verification completed; no CI policy decision was made. Inspect the classification. |
| Trusted policy | `0` / `2` / `3` | `PASS` / `BLOCK` or error / `REVIEW`. |
| Local | nonzero | Setup or verification failed. |

## Completed output

A successful run is published under `artifacts/sentinel/runs/completed/<run-id>/`. Failed runs do not publish there; failures after staging begins print a diagnostic staging path.

| Path | Contents |
| --- | --- |
| `raw-capture.json` | Solidity producer capture. |
| `evidence.json` | Assembled comparison evidence. |
| `verification.json` | Replay and build verification summary. Its `ci_decision` is `NOT_EVALUATED`; inspect `ci-gate.json` for the trusted decision. |
| `forge-results.json` | Selected test's Forge execution record. |
| `build/` | Compiler build-info and provenance. |
| `ci-gate.json` | Trusted policy decision, only when a trusted policy was supplied. |

## Troubleshooting

| Message or symptom | Check |
| --- | --- |
| `Consumer checkout must be clean` | Commit intended changes; inspect `git status --short`, including submodules. |
| `Missing dependency`, `Dependency gitlink mismatch` or `Dirty dependency` | Initialize the three required submodules at the exact paths in the quickstart; check their gitlinks and working trees. |
| `Sentinel revision differs from consumer Git index` | Initialize the pinned Sentinel submodule and commit its gitlink. |
| `Evidence output directory must be Git-ignored` | Ignore `artifacts/sentinel/` in the consumer. |
| `Producer failed or ambiguous` | Match exactly one passing test using its source, contract and function name. |
| `Captured scenario differs from configuration` | Use the same bytes32 scenario ID in TOML and Solidity. |
| `Exact solc 0.8.24+commit.e11b9ed9 not found` | Install that compiler in a supported SVM location or on `PATH`. |

The producer also needs Foundry write permission for `artifacts/sentinel`; see the quickstart. The [CI guide](../guides/ci.md) covers trusted policy requirements.

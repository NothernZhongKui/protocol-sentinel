# Portable Foundry workspace — v0.6 (development)

Protocol Sentinel v0.6 validates a declared **Direct EOA → UUPS** authority scenario in an existing Foundry workspace. The v0.6 runner supports a nested workspace in a Git monorepo and exact pinned submodules. It is separate from the released [v0.5 portable runner](portable-direct-v0.5.md).

**Status:** v0.6 implementation in draft PR #41, not a released interface. The tested external acceptance fixture is [Capminal](../tests/external/capu/); the synthetic faulty V2 is a test-only regression, **not an upstream Capminal finding**.

## What the runner checks

```text
Pinned consumer checkout + installed Sentinel gitlink
    └─ Foundry workspace (possibly nested)
        └─ One declared Foundry producer test
            └─ Lossless raw Direct capture
                └─ Build-provenance v2 + Git-owned source closure
                    └─ Original Standard JSON, isolated solc replay
                        └─ Evidence 1.1 + independent Python replay
                            └─ Trusted PASS / BLOCK / REVIEW (when configured)
```

A successful producer test is **not** itself an authorization to merge. In particular, a reproduced `CHANGED_TO_VIOLATION` remains a `BLOCK`. Neither replay nor Git source checks authenticate EVM execution independently.

## Requirements

- Python 3.12, Foundry 1.8.7 (the tested CI toolchain), Git, and the exact `solc` binary used for the build. The Capminal pilot uses `0.8.26+commit.8a97fa7a`.
- A **clean Git checkout** and pinned, clean Sentinel Git submodule. All compiler source units must belong to that checkout or its pinned Git submodule chain; untracked source files, symlink aliases, external source paths and divergent Git blobs are rejected.
- A committed workspace `foundry.toml` and any applicable inherited configs; the runner records source unit Git ownership and effective compiler settings from fresh build-info. For fully Git-pinned dependencies, a `foundry.lock` is not required.
- A uniquely selected producer test inheriting `DirectComparisonCapture`. It records a baseline observation, an authorized change and the new observation. Keep verdict assertions in separate tests.
- A Git-ignored `artifacts/sentinel/runs` output tree. Foundry must allow the export cheatcode to write there; merge the following into the workspace's **existing** `[profile.default]` configuration (never duplicate a TOML table/key):

```toml
fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]
```

Use your existing, reviewed remappings. Do not replace your project configuration with the Capminal sample.

## Reproduce the tested Capminal acceptance

From a checked-out v0.6 PR branch with Python dependencies installed and an exact `solc 0.8.26` binary in an SVM location:

```bash
python3 -m pip install -r evidence/requirements-schema.txt -r evidence/requirements-abi.txt
bash scripts/check_capu_workspace.sh
```

The acceptance script clones the [original Capminal repository](https://github.com/Capminal/capminal-contracts) at pinned commit `40b713b58f39476bcc081d7987c34a46cc085dd9`, stages only the [four test fixtures](../tests/external/capu/), a pinned Sentinel submodule and the scoped Foundry write permission in a temporary checkout, and commits that test-only integration locally. It **never pushes** to Capminal. It runs the native Solidity oracle, safe and faulty Evidence publication, independent completed-run verification, mutation rejection, and a deliberately failed producer. The original Capminal contracts are unchanged.

Expected observations:

| Test | Replayed classification | Trusted CI |
| --- | --- | --- |
| Test-only safe upgrade | `STILL_SATISFIED` | `PASS` |
| Synthetic test-only faulty role migration | `CHANGED_TO_VIOLATION` | `BLOCK` |
| Failed producer after export | No completed Evidence | `BLOCK` |
| Tampered completed artifact | Independent verification rejects | `BLOCK` |

## Integrate another Git-pinned Foundry workspace

Install Sentinel as a Git submodule within the consumer's declared workspace, for example `projects/my-app/lib/protocol-sentinel`, pin its commit, commit the gitlink and producer/config files, and ensure the checkout is clean. A producer config selects one exact test:

```toml
[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "my_safe_upgrade"
contract = "MyAuthorityProducerTest"
test = "test_ProduceSafe"
source = "test/MyAuthorityProducer.t.sol"
fixture_id = "my-upgrade-v1"
scenario_id = "0x0000000000000000000000000000000000000000000000000000000000000001"
```

The scenario ID shown above is **only a placeholder**. Replace it with the exact `bytes32` emitted by the Solidity producer. The producer must return successfully even when its comparison verdict is unsafe, because the trusted policy gate makes the merge decision.

Invoke the pinned tool from the workspace root, supplying the exact solc binary:

```bash
python3 -B lib/protocol-sentinel/scripts/run_workspace_direct.py \
  --project "$PWD" \
  --config sentinel-safe.toml \
  --solc "/absolute/path/to/solc-0.8.26"
```

Without a trusted policy, it publishes verified local Evidence but prints `CI DECISION: NOT_EVALUATED`. It does **not** authorize merging.

In trusted CI, supply `--trusted-policy /absolute/path/to/protected-policy.toml` selected from an independently protected workflow/base revision. The policy v2 binds the workflow repository, consumer repository, consumer commit, Foundry workspace, installed tool commit, and one required scenario. It must not be loaded from untrusted candidate-branch changes. See [the tested acceptance harness](../scripts/check_capu_workspace.sh) for exact fields.

Exit codes in trusted mode: `0` = PASS; `2` = BLOCK or any verification failure; `3` = REVIEW. The completed run includes `raw-capture.json`, `forge-results.json`, `build/build-provenance.json`, the compiler build-info files, `evidence.json`, `verification.json` and `ci-gate.json`.

## Independently re-verify a completed run

With the same pinned checkout, tool and trusted policy, run:

```bash
python3 -B lib/protocol-sentinel/scripts/verify_workspace_run.py \
  --project "$PWD" \
  --run-dir "/absolute/path/to/artifacts/sentinel/runs/completed/<run-id>" \
  --config sentinel-safe.toml \
  --solc "/absolute/path/to/solc-0.8.26" \
  --trusted-policy "/absolute/path/to/protected-policy.toml"
```

The verifier reads the published artifacts again, validates source ownership and hashes, repeats the recorded compilation and classification, and recomputes the trusted policy decision. It outputs `PUBLISHED_EVIDENCE=INDEPENDENTLY_REVERIFIED` when successful.

**Boundary:** This establishes agreement between recorded observations, compiler inputs/outputs, Git ownership and policy decision within the trusted checkout. It does not independently attest the original EVM execution, all possible privileges, or contract safety. The current v0.6 scope is Direct EOA UUPS only; Timelock remains a separate Solidity route. For the legacy Treasury workflow and Evidence 1.0, keep using the [v0.5 quickstart](portable-direct-v0.5.md).

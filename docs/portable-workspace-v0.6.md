# Portable Foundry workspace — v0.6

For the current v1.0 developer path, start with [First verified result](v1-onboarding.md). This page documents the released v0.6 runner; the maintainer acceptance suite is at the end.

Use the workspace runner to compare a declared Direct EOA/UUPS upgrade attempt before and after an authorized implementation change. It runs your Foundry producer, captures Comparison Evidence 1.1, replays the classification in Python and reproduces the recorded compiler outputs.

**Release:** [v0.6.0](https://github.com/NothernZhongKui/protocol-sentinel/releases/tag/v0.6.0). Pin the release tag for reproducible integration. For the earlier Evidence 1.0 workflow, see the [v0.5 guide](portable-direct-v0.5.md).

## Integrate your project

### 1. Check prerequisites

- Git, Python 3.12 or newer, Foundry with the required build-info flags (CI uses 1.8.7), and an executable solc matching the recorded compiler identity.
- A clean Git checkout containing a tracked `foundry.toml` in the workspace and any inherited configs. The workspace may be the repository root or a nested directory.
- Compiler sources owned by the checkout or its clean, pinned Git submodule chain. Untracked, changed, outside-checkout or unsupported symlinked sources cannot pass source attestation. A `foundry.lock` is optional for Git-pinned dependencies.
- One tracked, uniquely selected Foundry producer test and a tracked TOML config.
- A Git-ignored workspace `artifacts/sentinel/runs/` directory and Foundry permission to write there.

For compiler replay, an explicit `--solc` path is required. If Foundry records only a short compiler identity, Sentinel has pinned commit mappings for `0.8.24` and `0.8.26`; other versions need a matching full build identity in build-info. These are checks of compiler version identity and normalized outputs, not independent authentication of the original EVM execution.

### 2. Install and configure

From your Foundry workspace, add Sentinel as a Git submodule and pin the published `v0.6.0` release:

```bash
git submodule add https://github.com/NothernZhongKui/protocol-sentinel.git lib/protocol-sentinel
git -C lib/protocol-sentinel checkout v0.6.0
```

**Dependency ownership:** the Direct UUPS helper imports `forge-std` but does not import OpenZeppelin. Use the compatible, **Git-pinned `forge-std` already owned by your consumer workspace**, and keep the OpenZeppelin sources your own contracts import. Do **not** recursively initialize Sentinel's nested maintainer/test OpenZeppelin copies just to use the Direct UUPS runner. If your consumer has no compatible pinned `forge-std`, install and pin it as a **consumer** submodule before running Forge. Preserve your project's remappings so they resolve to those intended copies; don't silently replace dependency revisions.

This scoped installation has been exercised against the pinned external [Capminal acceptance harness](../scripts/check_capu_workspace.sh): after skipping Sentinel-owned nested library initialization, the build-provenance v2 manifest still attests the physical compiler paths, Git owners, commits, blobs and byte hashes for consumer-owned OpenZeppelin and `forge-std`. The runner continues to reject untracked or mutable sources. This does not add npm/pnpm provenance or guarantee support for every Foundry remapping layout.

Add the following to the workspace's existing `[profile.default]` in `foundry.toml`. Merge it into an existing `fs_permissions` array if present; do not duplicate TOML keys.

```toml
fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]
```

Add `artifacts/sentinel/runs/` to an appropriate `.gitignore`, preserving existing patterns. Keep your project's remappings. Commit `.gitmodules`, the Sentinel gitlink, configuration, producer, any inherited configs and other intended changes. The checkout and submodules must be clean when the runner starts.

### 3. Write a producer

Inherit `DirectComparisonCapture`, set up your fixture and use one shared `UpgradeCheck` for both observations:

1. Observe the baseline with `_observeDirectStage(spec)`.
2. Perform the intended authorized implementation change in the fixture.
3. Observe the updated state using the same specification.
4. Call `_compareDirectUpgrade` and `_exportDirectComparison` with the same `bytes32` scenario ID.

| Implementation | Role |
| --- | --- |
| Baseline | Active before the authorized transition. |
| Updated | Installed by the authorized actor between observations. |
| Candidate | A separate, valid UUPS implementation the declared actor attempts to install in **both** isolated probes; do not confuse it with the updated implementation. |

The [Capminal producer](../tests/external/capu/CapuSentinelProducer.t.sol) is a complete example in its own fixture, not a drop-in test for a different project. Adapt its actors, proxy, expected revert, candidate and transition to your contracts. Its separate [oracle](../tests/external/capu/AuthorityRegressionOracle.t.sol) shows the underlying fixture and independent assertions.

The producer must complete and export one capture, including when it observes an unsafe verdict. Supply the exact expected authorization revert and keep the same actor, target, candidate and policy across both stages. Keep expected-verdict assertions in separate tests; the CI gate makes the policy decision. The runner rejects failed, skipped or ambiguous producer selection.

### 4. Configure and run

Create a tracked `sentinel.toml`, replacing every example value with your own. The scenario ID must exactly match the value passed to the Solidity comparison and export:

```toml
[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "my_upgrade"
contract = "MyAuthorityProducerTest"
test = "test_Produce"
source = "test/MyAuthorityProducer.t.sol"
fixture_id = "my-upgrade-v1"
scenario_id = "0x0000000000000000000000000000000000000000000000000000000000000001"
```

For example, if Solidity uses `keccak256("my-upgrade-v1")` as its scenario ID, `cast keccak "my-upgrade-v1"` prints the value to put in TOML. This ID is scenario identity, not a proof of execution.

After committing the integration, run from the workspace root:

```bash
python -m pip install -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt
python -B lib/protocol-sentinel/scripts/run_workspace_direct.py \
  --project "$PWD" \
  --config sentinel.toml \
  --solc "/absolute/path/to/solc"
```

Successful local output includes `CLASSIFICATION: …`, `REPLAY: MATCH`, `CI DECISION: NOT_EVALUATED` and a completed directory under `artifacts/sentinel/runs/completed/<run-id>/`.

Interpret these independently:

| Output | Meaning |
| --- | --- |
| `PASS \| Fresh producer and scenario` | The selected Foundry producer completed and exported its observation; **not** a security approval. |
| `PASS \| Isolated compiler replay` | Recorded compiler outputs were independently reproduced. |
| `CLASSIFICATION: STILL_SATISFIED` | The declared restriction held before and after the authorized upgrade. |
| `CLASSIFICATION: CHANGED_TO_VIOLATION` | The declared restriction held before the upgrade but failed afterward. |
| `REPLAY: MATCH` | Python independently reproduced the recorded classification, even if that classification is unsafe. |
| `CI DECISION: NOT_EVALUATED` | Local verification succeeded without a trusted merge policy; no merge decision was made. |

A trusted policy maps `STILL_SATISFIED` to `PASS` and `CHANGED_TO_VIOLATION` to `BLOCK`. A verified `BLOCK` can still publish Evidence. The local runner does not make that decision.

If Sentinel is installed at another Git-pinned path inside the checkout, invoke its script there and supply `--tool-root /absolute/path/to/protocol-sentinel`. See [configuration and troubleshooting](reference/workspace-v0.6.md).

## Trusted CI and completed-run verification

Pass `--trusted-policy /absolute/path/to/policy.toml` only from a protected CI workflow that selects and supplies the trusted policy and execution context. The policy binds the workflow repository, consumer repository and commit, workspace, tool commit and required scenario. The policy must live outside the consumer checkout. An absolute path alone is not proof that the policy is trusted. See [trusted CI](guides/ci.md) and the [policy reference](reference/workspace-v0.6.md#trusted-policy).

A trusted run returns `0` for PASS, `2` for BLOCK or error, and `3` for REVIEW. A correct replay of `CHANGED_TO_VIOLATION` is BLOCK.

A completed **trusted** run can be checked again using the same checkout, installed tool, producer config, compiler, policy and GitHub run context:

```bash
python -B lib/protocol-sentinel/scripts/verify_workspace_run.py \
  --project "$PWD" \
  --run-dir "/absolute/path/to/artifacts/sentinel/runs/completed/<run-id>" \
  --config sentinel.toml \
  --solc "/absolute/path/to/solc" \
  --trusted-policy "/absolute/path/to/policy.toml"
```

This verifier requires `ci-gate.json` and the same recorded CI context, including run ID and attempt; it cannot reverify a local `NOT_EVALUATED` run in this mode. It rereads artifacts, checks Git-attested provenance and the recorded Forge result, repeats compiler and classification replay, and recomputes the gate decision. A verified BLOCK still exits `2`; `PUBLISHED_EVIDENCE=INDEPENDENTLY_REVERIFIED` and `CI_DECISION=BLOCK` distinguish it from a rejection.

## Limits

The portable runner covers one declared Direct EOA → ERC-1967/UUPS `upgradeToAndCall(address,bytes)` probe with empty initialization calldata per invocation. It does not discover roles or arbitrary governance routes, validate storage layout, or establish contract security. A matching revert does not prove which authorization branch executed. Git/source and replay checks do not independently authenticate the original EVM execution. See the [threat model](threat-model.md).

## Maintainer acceptance (optional)

This is a maintainer regression suite, not a prerequisite for integrating your own project. The Capminal acceptance exercises a real, pinned external Foundry workspace with test-only safe and faulty implementations. The faulty migration is synthetic; it is not an upstream vulnerability.

From a checkout of the v0.6.0 release with the toolchain installed:

```bash
python3.12 -m venv "$HOME/protocol-sentinel-venv"
source "$HOME/protocol-sentinel-venv/bin/activate"
python -m pip install -r evidence/requirements-schema.txt -r evidence/requirements-abi.txt
bash scripts/check_capu_workspace.sh
```

Keep the virtual environment outside the consumer Git checkout, especially when the workspace is nested in a monorepo, so the runner's clean-worktree requirement is preserved.

This requires Git, Foundry 1.8.7, network access to clone the pinned Capminal repository and dependencies, and executable solc `0.8.26+commit.8a97fa7a` in one of the SVM locations checked by the script. The script makes a temporary local integration commit and deletes its temporary checkout on exit. It does not modify or push to the upstream repository.

| Case | Classification | Trusted decision |
| --- | --- | --- |
| Test-only safe upgrade | `STILL_SATISFIED` | `PASS` |
| Synthetic faulty migration | `CHANGED_TO_VIOLATION` | `BLOCK` |
| Failed producer or tampered artifact | Rejected | `BLOCK` |

The harness also exercises the Solidity oracle, completed-run verifier and mutation controls. A local invocation uses synthetic GitHub context for the test; it does not demonstrate a protected production workflow. The [producer](../tests/external/capu/CapuSentinelProducer.t.sol) and [configuration](../tests/external/capu/sentinel-safe.toml) are executable examples to adapt.

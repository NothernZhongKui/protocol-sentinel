# Portable Direct quickstart

Use Protocol Sentinel in a Foundry project to compare a declared upgrade-authority scenario before and after an authorized implementation change. The runner executes your test, captures observations, replays the classification in Python, and reproduces the recorded compiler outputs.

For a complete working project, see the [Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer), including its [producer test](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/main/test/TreasuryAuthority.t.sol).

## Try the pinned Treasury example

This example uses the consumer at commit `1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb`, which pins Sentinel commit `944ff25f356f2b5c537076c43d4ce8b0edb181b0` (the portable runner predates v0.5.1). The version pinned in your own project can be newer. Requirements below still apply, including Foundry, Python 3.12 and the exact solc.

```bash
git clone https://github.com/NothernZhongKui/protocol-sentinel-consumer.git
cd protocol-sentinel-consumer
git checkout 1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb
git submodule update --init --recursive
python3.12 -m venv ../sentinel-example-venv
source ../sentinel-example-venv/bin/activate
python -m pip install -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt
python -B lib/protocol-sentinel/scripts/run_portable_direct.py \
  --project "$PWD" --config sentinel-safe.toml
```

The safe fixture is expected to finish with output including:

```text
SCENARIO: treasury_safe
CLASSIFICATION: STILL_SATISFIED
REPLAY: MATCH
CI DECISION: NOT_EVALUATED
COMPLETED: .../artifacts/sentinel/runs/completed/<run-id>
```

The run ID and absolute path vary. Local verification makes no merge decision. Inspect `evidence.json` and `verification.json` in the completed directory. The [configuration reference](reference/configuration.md) explains the files and troubleshooting.

## Connect your own project

The steps below target Sentinel `v0.5.1`.

## Supported scenario

| Component | v0.5 portable runner |
| --- | --- |
| Actor | Declared direct EOA |
| Target | ERC-1967 implementation slot |
| Action | UUPS `upgradeToAndCall(address,bytes)` with empty initialization data |
| Inputs | Declared actor, target, candidate, expected revert and policy |
| Execution | One uniquely selected passing producer test per invocation |

You set up the fixture and perform the authorized transition. Sentinel does not discover actors or privileges. The [Timelock adapter](timelock-route-quickstart.md) is a separate API.

## Requirements

- Git and a Git-tracked Foundry project.
- Foundry with the required build-info and test flags; the Sentinel CI uses Foundry **1.8.7**.
- Python **3.12** and the pinned verifier dependencies.
- `solc 0.8.24+commit.e11b9ed9` available to the replay verifier.
- A clean consumer checkout, committed `foundry.toml`, `foundry.lock`, configuration, and a clean, pinned Sentinel Git submodule.

The current portable build-provenance format requires three
clean, pinned Git submodules at these exact project-relative paths:

- `lib/forge-std`
- `lib/openzeppelin-contracts`
- `lib/openzeppelin-contracts-upgradeable`

Projects using different dependency paths or package layouts are not
yet supported by this portable runner. These requirements are checked
before Forge execution and before creating a run directory. The
runner reports a setup failure instead of publishing completed Evidence.

Foundry may install the configured Solidity compiler on its first build. The portable runner therefore checks the exact compiler during independent replay, after Forge execution and before completed Evidence publication.

The verifier looks for solc in common Foundry/SVM locations or on `PATH`. A matching compiler on `PATH` can be checked with `solc --version`. See [compiler replay](build-reproducibility.md).

## 1. Install and configure

From the root of your existing Foundry project, add Sentinel as a submodule and pin a reviewed revision:

```bash
git submodule add https://github.com/NothernZhongKui/protocol-sentinel.git lib/protocol-sentinel
git -C lib/protocol-sentinel checkout v0.5.1
```

The portable runner was introduced in v0.5.0. Pin a reviewed release or commit when upgrading. Keep the submodule initialized when cloning the consumer:

```bash
git submodule update --init --recursive
```

Add the following entries to your existing `[profile.default]` in `foundry.toml`. Merge them into any existing `remappings` or `fs_permissions` arrays rather than defining either key twice:

```toml
[profile.default]
solc_version = "0.8.24"
fs_permissions = [{ access = "read-write", path = "./artifacts/sentinel" }]
remappings = [
  "forge-std/=lib/forge-std/src/",
  "protocol-sentinel/=lib/protocol-sentinel/src/",
]
```

Retain your project's other remappings and filesystem permissions. The write permission allows the producer to export its capture. Ensure `artifacts/sentinel/` is Git-ignored, for example by adding it to `.gitignore`:

```gitignore
artifacts/sentinel/
```

## 2. Write the producer test

The names below refer to different implementations:

| Name | Role |
| --- | --- |
| Baseline | Active before the authorized transition. |
| Updated | Installed by the authorized actor between observations. |
| Candidate | The implementation the actor under test attempts to install during each isolated probe. |


Inherit `DirectComparisonCapture` in a Foundry test. Set up your proxy and implementations, then:

1. Define an `UpgradeCheck` with the actor, target, candidate, expected revert and policy.
2. Capture the baseline with `_observeDirectStage(spec)`.
3. Perform the intended authorized implementation upgrade.
4. Capture the updated stage with the same specification.
5. Call `_compareDirectUpgrade` and `_exportDirectComparison` with the same `bytes32` scenario ID.

The producer must execute successfully, be uniquely selected, and export one Direct capture. For a CI producer, record the observed result without asserting it is safe: the trusted gate decides whether to pass, block or review. Put expected safe/unsafe verdict assertions in separate tests. A passing producer does not itself authorize a merge.

Adapt the [complete Treasury producer](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/test/TreasuryAuthority.t.sol) to your contracts and roles. The scenario ID in your configuration must match the value passed to both Solidity calls. The linked producer is a complete executable example; replace its fixture, actors, expected revert and authorized transition with your own.

## 3. Configure and commit

Create `sentinel-safe.toml`. This example names the Treasury consumer's test; replace the values with your own:

```toml
[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "treasury_safe"
contract = "TreasuryAuthorityTest"
test = "test_SafeUpgradePreservesRestriction"
source = "test/TreasuryAuthority.t.sol"
fixture_id = "external-treasury-v1-safe-v2"
scenario_id = "0x86917dbb645eece6a5a6f11fa636fdae5558fa7fd4ab12c07488142cbfbb39bf"
```

`source` is a project-relative Solidity file under `test/`; `contract` and `test` identify exactly one test, whose name starts with `test_`. `id` is the producer identifier, `fixture_id` describes the fixture, and `scenario_id` is the exact 32-byte ID exported by the producer.

Commit your test, configuration, `foundry.toml`, `foundry.lock`, `.gitmodules`, submodule gitlink, and any other project changes. The runner requires a clean working tree and verifies that the installed Sentinel revision matches the tracked gitlink.

## 4. Run

Create a Python 3.12 virtual environment outside the checkout so it does not make the working tree dirty:

```bash
python3.12 -m venv ~/venvs/protocol-sentinel
source ~/venvs/protocol-sentinel/bin/activate
python -m pip install \
  -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt
```

From the clean project root:

```bash
python -B lib/protocol-sentinel/scripts/run_portable_direct.py \
  --project "$PWD" \
  --config sentinel-safe.toml
```

A successful local run reports the scenario, classification, `REPLAY: MATCH`, `CI DECISION: NOT_EVALUATED`, and the completed directory under `artifacts/sentinel/runs/completed/<run-id>/`. The directory includes `evidence.json`, `verification.json`, build provenance and execution records.

`MATCH` confirms classification replay agrees with the recorded observations; inspect the classification itself. For example, `MATCH` with `CHANGED_TO_VIOLATION` describes a reproduced violation. Local mode does not apply a merge policy.

If a run fails, no completed evidence is published. The runner prints a diagnostic staging path. Common setup failures include a dirty checkout or submodule, missing Git-ignored output path, mismatched scenario ID, ambiguous test selection, missing filesystem permission, or an unavailable exact solc version.

## 5. Apply a trusted CI policy

For `PASS`, `BLOCK`, or `REVIEW`, trusted CI supplies `--trusted-policy` with an absolute path to a policy from the trusted base revision. The policy binds the required producer and expected repository and workflow. The [reference consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer) provides an integration to adapt, including workflow-integrity checks.

| Comparison | Decision |
| --- | --- |
| `STILL_SATISFIED` | `PASS` |
| `CHANGED_TO_VIOLATION`, `STILL_VIOLATED` | `BLOCK` |
| `CHANGED_TO_SATISFIED`, `INDETERMINATE`, `INCOMPARABLE` | `REVIEW` |

Missing, duplicated, or invalid required scenarios block. In trusted-policy mode, the runner exits with code `0` for PASS, `2` for BLOCK or an error, and `3` for REVIEW. Without a trusted policy, a successfully verified local run exits `0` regardless of its classification.

Protect the required workflow, policy, tool revision and branch rules against unreviewed changes. The runner alone cannot establish that trust boundary. See the [CI guide](guides/ci.md) and [configuration and troubleshooting reference](reference/configuration.md).

## What verification establishes

Python replay checks the classification against recorded observations. Compiler replay checks normalized compiler outputs against recorded build inputs. Neither independently authenticates EVM execution. The test author controls fixture setup, actor selection, expected revert and the transition; the result applies only to that declared scenario. See the [threat model](threat-model.md).

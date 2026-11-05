# Direct UUPS — first verified result (v1.0 development)

**Status:** source-tree onboarding guide for unreleased v1.0 work. The latest published release is [v0.6.0](releases/v0.6.0.md). This guide uses the reviewed development commit `82830f957f4340b0ac472d1a1f4518451da231ae`; do not assume that `v0.6.0` contains `sentinel doctor` or `sentinel init`.

This workflow is for a **pre-existing Foundry project** using a canonical ERC-1967/UUPS proxy and **one declared** authority regression scenario. Sentinel does not discover roles, choose a policy, or audit your whole protocol.

## 1. Pin the tool in your project

Requirements: Git, Python 3.12+, Foundry (CI uses 1.8.7), an executable `solc` matching your project/compiler build-info, and Git-pinned compatible Solidity dependencies.

At the Foundry workspace root:

```bash
git submodule add https://github.com/NothernZhongKui/protocol-sentinel.git lib/protocol-sentinel
git -C lib/protocol-sentinel checkout 82830f957f4340b0ac472d1a1f4518451da231ae
git submodule update --init -- lib/protocol-sentinel
```

If your project already has the submodule, inspect and update its approved gitlink rather than adding it again. Use **the consumer's** compatible Git-pinned `forge-std` and OpenZeppelin versions. Do not recursively initialize Sentinel's maintainer-only OpenZeppelin copies. Preserve the project's remappings; untracked `node_modules` compiler inputs are not Git-attested.

Ensure the existing `[profile.default]` includes write permission for Evidence (merge into existing `fs_permissions`, do not duplicate TOML keys):

```toml
fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]
```

Ignore `artifacts/sentinel/runs/` in the consumer's `.gitignore`.

## 2. Generate a deliberately incomplete producer

```bash
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py init \
  --route direct-uups --project . --dry-run
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py init \
  --route direct-uups --project .
```

This creates only `test/SentinelAuthorityProducer.t.sol` and `sentinel.toml`. It will **not** rewrite your Foundry config, ignore rules or CI. The generated Solidity test is supposed to **compile but fail** with `SentinelFixtureIncomplete()`. It cannot publish completed Evidence while unfilled.

Implement the two fixture hooks using your actual contracts: (1) deploy the V1 proxy, declare the **unauthorized actor** and a **separate valid UUPS probe candidate**, with the exact expected authorization revert; (2) perform the real *authorized* V1 → V2 upgrade. Observe the same actor/target/candidate before and after. Do **not** replace the intended restriction with an assertion that the upgrade must be safe in the producer itself—Sentinel must still record a faulty migration.

Set an explicit meaningful `fixture_id`, and change `scenario_id` in both Solidity and `sentinel.toml` to the same `bytes32`. The remaining config fields must identify the **one** producing test exactly. For a complete, independently exercised fixture, see the [external Treasury producer](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/146ec1461bf7774ab57b84a2d7f5bc06dfb70138/test/TreasuryAuthority.t.sol) and its [safe producer TOML](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/146ec1461bf7774ab57b84a2d7f5bc06dfb70138/sentinel-safe.toml). Adapt its identity, not its assumptions, to your project.

## 3. Commit, diagnose and run

Commit the intended consumer files and gitlinks first. `doctor` is **offline/read-only** and reports `PASS`, `FAIL`, `WARN`, `DEFERRED`. It cannot establish compiler source closure or merge approval.

```bash
git add .gitmodules .gitignore foundry.toml lib/protocol-sentinel \
  test/SentinelAuthorityProducer.t.sol sentinel.toml
git commit -m "test: declare Direct UUPS authority scenario"

# Replace this with an absolute path to the solc version actually used by Forge:
SOLC_PATH="/absolute/path/to/solc"

python3.12 -B lib/protocol-sentinel/scripts/sentinel.py doctor \
  --project . --config sentinel.toml --solc "$SOLC_PATH"

python3.12 -m pip install \
  -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt

python3.12 -B lib/protocol-sentinel/scripts/run_workspace_direct.py \
  --project "$PWD" --config sentinel.toml --solc "$SOLC_PATH"
```

Before running, ensure the checkout and Git submodules are clean; resolve any doctor FAIL. The runner will perform a **fresh producer execution**, attest compiler source ownership, independently replay compiler outputs and classification, then publish a completed Evidence 1.1 bundle on success.

Interpret separate fields, not a single green light:

| Output | What it means |
| --- | --- |
| `CLASSIFICATION: STILL_SATISFIED` | Declared restriction held in both observations |
| `CLASSIFICATION: CHANGED_TO_VIOLATION` | Restriction held before V2 and failed afterward |
| `REPLAY: MATCH` | Python reproduced the **recorded** comparison; it can accompany a violation |
| `CI DECISION: NOT_EVALUATED` | Local check had **no trusted policy**, so it did **not** approve a merge |
| `COMPLETED: …/completed/<run-id>` | The exact newly published Evidence bundle |

If the producer fails, fix the fixture: failed execution does not publish completed Evidence.

## 4. Add trusted CI only when needed

Start by getting one local verified result. To enforce a merge decision, adapt the [protected-base workflow example](../examples/trusted-ci/README.md) and the [trusted CI guide](guides/ci.md). In CI, the protected policy and reviewed tool SHA must be independent of the candidate checkout; approved per-run policy v2 binds the actual tested commit. `PASS`, `BLOCK` and `REVIEW` are policy decisions, not synonyms for `MATCH`.

**Do not rely on a required job name alone.** A [synthetic pilot PR](https://github.com/NothernZhongKui/protocol-sentinel-consumer/pull/14) replaced a candidate workflow with `exit 0` and produced a false-green check. Protect workflow integrity through independently enforced repository rules, then confirm a candidate cannot merge by spoofing the check.

## Onboarding feedback

If you tried this without maintainer help, please open a GitHub issue describing the first blocker, your existing Foundry/solc versions, root vs nested workspace, whether you reached a completed local run, and approximate **hands-on** time excluding toolchain installation. Never include signing keys, private RPC credentials or sensitive project data.

The [v1.0 milestone](roadmap-v1.0.md) still requires independent onboarding evidence before release; these instructions are not themselves proof of an unassisted integration.

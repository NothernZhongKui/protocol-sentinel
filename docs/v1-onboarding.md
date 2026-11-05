# Direct UUPS — first verified result

**Version:** Protocol Sentinel v1.0.0. Use the exact published `v1.0.0` commit after release; this release PR leaves the tag uncreated until merge. The `v0.6.0` tag does not contain `sentinel doctor` or `sentinel init`.

This workflow is for a **pre-existing Foundry project** using a canonical ERC-1967/UUPS proxy and **one declared** authority regression scenario. Sentinel does not discover roles, choose a policy, or audit your whole protocol.

## 1. Pin the tool in your project

Requirements: Git, Python 3.12+, Foundry (CI uses 1.8.7), an executable `solc` matching your project/compiler build-info, and Git-pinned compatible Solidity dependencies.

The commands below use `python3.12`; if your Python 3.12+ executable has a different name, substitute it consistently. The scaffold writes to `test/`; ensure your Foundry configuration discovers tests there.

At the Foundry workspace root:

```bash
git submodule add https://github.com/NothernZhongKui/protocol-sentinel.git lib/protocol-sentinel
git -C lib/protocol-sentinel fetch --tags origin
git -C lib/protocol-sentinel checkout --detach v1.0.0
# init checks the installed revision against the consumer's Git index.
git add -- ':(top).gitmodules' lib/protocol-sentinel
```

Stage the selected gitlink **before** running `init`: `git submodule add` records the initially checked-out revision, which may differ from `v1.0.0`. Do not run `git submodule update` before staging or committing the chosen pin, as it can restore the indexed revision. If the submodule already exists, inspect and update its approved gitlink rather than adding it again. Use **the consumer's** compatible Git-pinned `forge-std` and OpenZeppelin versions. Do not recursively initialize Sentinel's maintainer-only OpenZeppelin copies. Preserve the project's remappings; untracked `node_modules` compiler inputs are not Git-attested.

Ensure the existing `[profile.default]` includes write permission for Evidence (merge into existing `fs_permissions`, do not duplicate TOML keys):

```toml
fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]
```

Ignore `artifacts/sentinel/runs/` in the consumer's `.gitignore`.

## 2. Generate a deliberately incomplete producer

```bash
mkdir -p test
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py init \
  --route direct-uups --project . --dry-run
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py init \
  --route direct-uups --project .
```

This creates only `test/SentinelAuthorityProducer.t.sol` and `sentinel.toml`. It will **not** rewrite your Foundry config, ignore rules or CI. The generated Solidity test is supposed to **compile but fail** with `SentinelFixtureIncomplete()`. It cannot publish completed Evidence while unfilled.

Before implementing the hooks, distinguish the three implementations involved:

| Implementation | Role |
| --- | --- |
| Baseline | Active in the proxy before the authorized transition. |
| Updated | Installed by the authorized actor between the two observations. |
| Probe candidate | A separate valid UUPS implementation that the declared actor attempts to install in **both** isolated probes. |

The probe restores its state after each attempt; the authorized transition between probes is performed by your fixture.

Implement the two fixture hooks using your actual contracts: (1) deploy the V1 proxy, declare the **unauthorized actor** and a **separate valid UUPS probe candidate**, with the exact expected authorization revert; (2) perform the real *authorized* V1 → V2 upgrade. Observe the same actor/target/candidate before and after. Do **not** replace the intended restriction with an assertion that the upgrade must be safe in the producer itself—Sentinel must still record a faulty migration.

Set an explicit meaningful `fixture_id`, and change `scenario_id` in both Solidity and `sentinel.toml` to the same `bytes32`. The remaining config fields must identify the **one** producing test exactly. For a complete executable example, see the [Treasury walkthrough](examples/treasury.md), including both Solidity files and matching TOML from the pinned external consumer. It shows an authorized transition and a separate probe candidate; adapt the fixture and identities to your own contracts.

## 3. Commit, diagnose and run

Commit the intended consumer files and gitlinks first. `doctor` is **offline/read-only** and reports `PASS`, `FAIL`, `WARN`, `DEFERRED`. It cannot establish compiler source closure or merge approval.

```bash
# .gitmodules lives at the repository root, even for a nested Foundry workspace.
git add -- ':(top).gitmodules'
git add -- foundry.toml lib/protocol-sentinel \
  test/SentinelAuthorityProducer.t.sol sentinel.toml

# Stage the actual ignore-rule file (workspace and/or repository root).
if [ -f .gitignore ]; then git add -- .gitignore; fi
GIT_ROOT="$(git rev-parse --show-toplevel)"
if [ "$GIT_ROOT" != "$PWD" ] && [ -f "$GIT_ROOT/.gitignore" ]; then
  git add -- ':(top).gitignore'
fi

git commit -m "test: declare Direct UUPS authority scenario"

# Use the absolute executable matching the solc version used by Forge.
# On macOS, Foundry-managed binaries can be under:
# "$HOME/Library/Application Support/svm/<version>/solc-<version>"
# On Linux, check "$HOME/.svm/<version>/solc-<version>".
SOLC_PATH="/absolute/path/to/solc"

python3.12 -B lib/protocol-sentinel/scripts/sentinel.py doctor \
  --project . --config sentinel.toml --solc "$SOLC_PATH"

python3.12 -m venv "$HOME/protocol-sentinel-venv"
source "$HOME/protocol-sentinel-venv/bin/activate"
python -m pip install \
  -r lib/protocol-sentinel/evidence/requirements-schema.txt \
  -r lib/protocol-sentinel/evidence/requirements-abi.txt

python3.12 -B lib/protocol-sentinel/scripts/run_workspace_direct.py \
  --project "$PWD" --config sentinel.toml --solc "$SOLC_PATH"
```

Keep the Python environment outside the consumer checkout so it does not dirty the Git working tree. Before running, ensure the checkout and Git submodules are clean; resolve any doctor FAIL. The runner will perform a **fresh producer execution**, attest compiler source ownership, independently replay compiler outputs and classification, then publish a completed Evidence 1.1 bundle on success.

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

The [milestone record](roadmap-v1.0.md) documents completed acceptance and the follow-on community onboarding work. Do not present an assisted integration as an unaided developer result.

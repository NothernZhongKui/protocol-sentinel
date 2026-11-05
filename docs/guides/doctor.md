# Direct UUPS integration preflight (development branch)

**Scope:** proposed v1.0 usability CLI. It is not present in published v0.6.0. The existing workspace runner and trusted policy gate remain authoritative.

In an existing Git-pinned Foundry workspace with Sentinel installed under lib/protocol-sentinel, run:

~~~bash
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py doctor \
  --project . \
  --config sentinel.toml \
  --solc "/absolute/path/to/solc"
~~~

Doctor is **read-only and offline**. It does not run Forge, initialize submodules, install dependencies, modify the Git index or create Evidence. It checks the exact pinned Sentinel gitlink, producer configuration and tracked sources, required Foundry filesystem permissions, ignored Evidence output, Forge and an explicit solc executable/version. The TOML parser is shared with the v0.6 workspace runner.

| Status | Meaning |
| --- | --- |
| PASS | One specific local precondition is verified; not a security or merge approval. |
| FAIL | A local blocker with file/setting remediation. |
| WARN | Attention needed, for example uncommitted files or missing optional --solc. |
| DEFERRED | A fresh compiler build or protected CI is necessary. No source-closure or approval claim. |

Doctor can diagnose a dirty checkout, but the actual workspace runner still requires pinned, clean Git sources. The **real compiler build** establishes selected physical import paths, Git owners/revisions and source closure; a green Foundry build by itself is insufficient.

For a simple workspace, its default Foundry profile needs permission for the Evidence directory:

~~~toml
fs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]
~~~

Merge with existing permissions, preserve remappings, and ensure the Git ignore rules include artifacts/sentinel/runs/.

After preflight, follow the [v0.6 workspace quickstart](../portable-workspace-v0.6.md). A local REPLAY: MATCH can accompany CHANGED_TO_VIOLATION. Only a protected CI workflow with a trusted policy can make the gate decision.

**OpenZeppelin:** DirectComparisonCapture does not directly import OpenZeppelin, but the separate Timelock helper and demonstration fixtures do. Selective nested-submodule initialization has not yet been accepted in a clean external build, so this CLI does not change install instructions or relax Git attestation.

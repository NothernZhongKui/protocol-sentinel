# Direct UUPS scaffold (development branch)

This command is part of the proposed v1.0 adoption work. It is **not in the released v0.6.0 tag**.

From a Foundry workspace that already contains a pinned Sentinel git submodule at lib/protocol-sentinel:

~~~bash
python3.12 -B lib/protocol-sentinel/scripts/sentinel.py init \
  --route direct-uups --project . --dry-run
~~~

Remove --dry-run to create two files (only if they do not already exist):

- test/SentinelAuthorityProducer.t.sol
- sentinel.toml

**No configuration is silently rewritten.** Keep your existing Foundry remappings, add the Evidence write permission and ignore rule as documented in the [workspace quickstart](../portable-workspace-v0.6.md). Commit the intended integration files before running the trusted workspace runner.

The Solidity file is an intentionally incomplete producer: its fixture and authorized-transition hooks both revert with the custom error **SentinelFixtureIncomplete()**. A developer must implement the real actor, proxy, separately valid UUPS probe candidate, exact authorization revert and V1 → V2 upgrade, as well as replacing the example fixture and scenario identities consistently.

The generated test is expected to **compile but fail** until those hooks are implemented. A failing producer cannot publish completed Evidence, even if it compiles. Do not remove the revert without supplying the actual security scenario.

The init command does not discover roles or infer safety requirements. It does not install OpenZeppelin, modify foundry.toml, .gitignore or CI policies, or enable merge enforcement.

**Acceptance note:** the first dedicated GitHub Foundry smoke job compiled and exercised the incomplete template in a Git-pinned consumer while initializing only forge-std. That test deliberately produced the incomplete-fixture revert and no completed Evidence. It does **not** yet establish full compiler source-closure provenance for a completed safe/faulty scenario; that remains a separate external acceptance requirement.

# Build Reproducibility — Protocol Sentinel v0.4.1

This page describes the legacy Direct and Timelock runners and Evidence 1.0. For the unreleased v0.6 workspace runner, Git-attested source closure and Evidence 1.1, see the [workspace guide](portable-workspace-v0.6.md) and [architecture](architecture.md).

Status: IMPLEMENTED
Scope: Direct and Timelock Comparison Evidence 1.0

## Pipeline

1. Forge executes the required producer tests.
2. Each producer uses fresh, isolated build output and cache.
3. Forge emits real compiler build-info.
4. The runner captures build-info in the run-local bundle.
5. Build provenance records compiler inputs and SHA-256 hashes.
6. Sources are checked against the local Git checkout.
7. Dependency revisions are checked against pinned gitlinks.
8. Evidence references the build manifest SHA-256.
9. The recorded compiler inputs are independently recompiled.
10. Only verified runs can be atomically published.

The publication gates are implemented in:

- `scripts/run_direct_comparison.py`
- `scripts/run_timelock_comparison.py`
- `scripts/build_provenance.py`
- `scripts/replay_build_compilation.py`

## Independent compiler replay

The verifier uses Solidity compiler version
`0.8.24+commit.e11b9ed9`.

The saved Foundry build-info includes some non-standard
compiler invocation fields, such as `allowPaths`.
The replay supplies the embedded `language`, `sources`
and `settings` to `solc --standard-json`.

The verifier compares the recorded and independently
compiled `contracts` and `sources` sections.

Explicit, limited normalization handles differences
observed between Foundry's serialized compiler output
and the direct solc response:

- ABI entries may appear in a different order; complete
  entries are sorted without discarding arguments or duplicates.
- Empty AST `nodes` arrays on typed nodes are treated
  equivalently to omitted empty `nodes`.
- Empty `devdoc`, `userdoc`, `methodIdentifiers` and
  `immutableReferences` fields are omitted.

Other compiler output values must still match.
The normalization does not discard nonempty ABI,
bytecode, metadata, or AST information.

Compiler diagnostics are not part of the equality check.

## Negative controls

The tests cover changes to:

- ABI
- AST
- Creation bytecode
- Metadata
- Compiler optimizer settings
- Published compiler build-info hash
- Source contents and dependency revisions

The producer pipeline also includes an injected build
mutation that must prevent completed publication.

## Reproduce

Requirements:

- Foundry 1.8.7
- Python 3.12 with the repository's pinned dependencies
- Solidity compiler 0.8.24+commit.e11b9ed9
- Initialized pinned Git submodules

Run the complete acceptance suite:

    bash scripts/run_comparison_c4.sh

Then run compiler replay mutation checks against
completed Direct and Timelock runs:

    python3 scripts/test_build_compilation.py artifacts/demo/comparison-runs/completed
    python3 scripts/test_build_compilation.py artifacts/demo/comparison-runs/c3/completed

Both producing pipelines independently check build
reproducibility before publishing completed evidence.

## Guarantee and limits

A successful build replay demonstrates that the
recorded compiler inputs produce matching normalized
compiler contracts and sources under the verified
compiler version.

The Evidence-to-manifest SHA-256 binding detects
changes relative to the published manifest and Evidence.
It is not, by itself, a trusted external signature.

The local checks depend on the inspected checkout,
installed compiler and trusted execution environment.

These checks do not independently authenticate:

- That the original EVM execution actually occurred.
- Control of the declared actor or its private key.
- Mainnet transaction inclusion.
- The provenance of a fully fabricated but internally
  consistent evidence bundle.
- Security beyond the declared policy and route.

The recorded execution provenance remains
`UNAUTHENTICATED`.

The independent external *classification* consumer
is a separate verification layer. It can replay
Evidence without recompiling Solidity or requiring
Foundry, Git or RPC.

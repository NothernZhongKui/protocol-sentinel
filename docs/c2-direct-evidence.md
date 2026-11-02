# C2 — Direct Comparison Evidence

Status: IMPLEMENTED FOR REVIEW

Route: DIRECT_EOA_UUPS
Schema: protocol-sentinel-comparison 1.0
Semantics: direct-eoa-v1

## Purpose

Produce real Foundry observations for a UUPS authority
regression and independently replay their classification.

The fixture compares:

- Before: operator denied by RoleVaultV1.
- After: operator can upgrade via RoleVaultV2Risky.

Expected fixture classification:

    PASS -> FAIL
    CHANGED_TO_VIOLATION

## Requirements

- Foundry 1.8.7
- Python 3.12
- Python dependencies from evidence/requirements-schema.txt
  and evidence/requirements-abi.txt

The Solidity helper library itself does not require Python.

## Reproduce

Install Python dependencies:

    python -m pip install \
      -r evidence/requirements-schema.txt \
      -r evidence/requirements-abi.txt

Run the complete producer and verification pipeline:

    python scripts/run_direct_comparison.py

Run the post-write failure negative control:

    python scripts/run_direct_comparison.py \
      --inject-postwrite-failure

The second command must not publish completed evidence.

## Artifacts

Successful runs are published to:

    artifacts/demo/comparison-runs/completed/<run-id>/

Each completed run contains:

- raw-capture.json
- evidence.json
- forge-results.json
- verification.json

A fresh staging directory is used for every invocation.

A producing test that fails, is absent or is skipped
cannot produce a completed publication.

## Replay

An existing evidence document can be classified without
Foundry or RPC:

    python scripts/replay_direct_comparison.py evidence.json

Replay independently checks:

- JSON Schema 1.0
- Canonical calldata
- ABI/Keccak scenario key
- Both policy evaluations and diagnostic reasons
- Comparison verdict and reason

Raw observations are not repaired to match declarations.

## Trust limits

Classification MATCH means Python reproduced the
recorded Solidity classification.

It does not mean the underlying policy passed.

Source-context verification compares hashes against
the runner's local checkout. It is not independent
authentication of execution provenance.

Execution provenance remains UNAUTHENTICATED.

Local development may use a dirty working tree;
the source-input hashes preserve the checked context.

The CI job executes the pipeline on a fresh Linux checkout.

Legacy evidence schemas 0.2–0.4 remain unchanged.
No production Solidity API is modified.

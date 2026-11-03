# C3 — Timelock Comparison Evidence

Status: IMPLEMENTED FOR REVIEW

Route: OZ_TIMELOCK_SINGLE
Schema: protocol-sentinel-comparison 1.0
Semantics: oz-timelock-single-v1

## Scope

Independent comparison replay for the OpenZeppelin
TimelockController -> ProxyAdmin -> TransparentUpgradeableProxy
execution route.

The pipeline preserves actual Solidity observations and
independently reconstructs:

- Canonical ProxyAdmin upgrade calldata.
- Canonical Timelock execute calldata.
- Timelock operation ID.
- Domain-separated comparison scenario key.
- Before and after policy evaluations.
- Diagnostic reason precedence.
- Comparison verdict and reason.

No production Solidity API changes.

## Real EVM fixtures

### Ready

A shared Timelock operation is Ready in both stages.

A separate authorized governance operation changes the
active implementation from V1 to V2.

The shared operation remains unconsumed.

Expected result:

    Before: PASS
    After: PASS
    Comparison: STILL_SATISFIED

### Waiting

An upgrade installation is prepared and made Ready before
the shared comparison operation is scheduled.

The installation changes V1 to V2 without advancing
the EVM clock after the shared operation is scheduled.

The shared operation remains Waiting in both stages.

Both attempted executions produce the pinned
TimelockUnexpectedOperationState revert.

Expected result:

    Before: PASS
    After: PASS
    Comparison: STILL_SATISFIED

In Waiting, PASS means the Timelock correctly rejects
execution before the delay expires.

It does not mean the upgrade succeeded.

## Run

Requirements:

- Foundry 1.8.7
- Python 3.12
- evidence/requirements-schema.txt
- evidence/requirements-abi.txt

Install dependencies:

    python -m pip install \
      -r evidence/requirements-schema.txt \
      -r evidence/requirements-abi.txt

Produce and verify both scenarios:

    python scripts/run_timelock_comparison.py

Verify the post-write failure boundary:

    python scripts/run_timelock_comparison.py \
      --inject-postwrite-failure

## Completed artifacts

Successful runs appear under:

    artifacts/demo/comparison-runs/c3/completed/<run-id>/

Each contains exactly:

- ready-raw.json
- waiting-raw.json
- ready-evidence.json
- waiting-evidence.json
- forge-results.json
- verification.json
- build/ (compiler build-info and provenance)

Both producing tests must succeed before publication.

The runner performs schema validation, independent replay,
lossless raw-observation checks, local source-context
verification and adversarial mutation tests.

A failed producing test cannot publish a completed run.

## Independent replay

Either evidence file can be independently replayed
without Foundry or RPC:

    RUN_DIR="$(ls -td artifacts/demo/comparison-runs/c3/completed/*/ | head -n 1)"
    python scripts/replay_timelock_comparison.py "$RUN_DIR/ready-evidence.json"
    python scripts/replay_timelock_comparison.py "$RUN_DIR/waiting-evidence.json"

An InvalidTimelockPreparation exception aborts
replay of a completed comparison.

Invalid governance preparation must never be silently
converted into a policy FAIL.

UNKNOWN, INDETERMINATE and INCOMPARABLE retain their
distinct frozen semantics.

## Trust boundary

classification_replay = MATCH means Python reproduced
the recorded Solidity classification.

It is not proof of an authentic Ethereum execution.

Local source hashes are verified against the runner's
checkout, not against an external trusted authority.

execution_provenance remains UNAUTHENTICATED.

Legacy Evidence 0.2–0.4 and direct Comparison C2
remain independent and unchanged.

## References

- RFC-004C
- ADR-004C
- evidence/semantics/registry.json
- evidence/schema/comparison-1.0.schema.json

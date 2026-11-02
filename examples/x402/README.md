# External integration: Fortytwo x402Escrow

## Source

External repository: https://github.com/Fortytwo-Network/fortytwo-x402Escrow

Pinned commit: 2ee48d0af7dfdc6f0daa0a3017b70edf137033ec

The original Fortytwo implementation is not modified.

## One-command reproduction

From the Protocol Sentinel repository root, with Git submodules initialized:

    bash scripts/reproduce_x402.sh

The script verifies dependencies, fetches the pinned external
source, generates a test-only risky V2, and executes five tests
in a temporary directory.

## Scenarios

1. Admin cannot upgrade V1.
2. Facilitator cannot upgrade V1.
3. Owner can perform an authorized upgrade.
4. Normal V2 preserves authorization restrictions.
5. Authority regression: PASS -> FAIL -> PASS.

## Regression demonstration

- PASS: facilitator cannot upgrade original V1.
- FAIL: intentionally risky V2 grants facilitator upgrade authority.
- PASS: corrected V2 restores the restriction.

Sentinel's FAIL is expected. The Foundry test itself must pass.

## Limitations

The regression is deliberately introduced by Sentinel developers.
It is not a claim of a vulnerability in Fortytwo's original contract.

The original external source is preserved.

The experiment tests upgrade authorization, not payment settlement
or the complete security of the external project.

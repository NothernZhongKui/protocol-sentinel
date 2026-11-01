# External Integration: Fortytwo x402Escrow

## Source

Repository:
https://github.com/Fortytwo-Network/fortytwo-x402Escrow

External source commit: `2ee48d0af7dfdc6f0daa0a3017b70edf137033ec`

Protocol Sentinel commit: `7e8e303e667ddaaa25305ddae11e1e0c8361bd4a`

## Scope

This experiment tests the existing X402Escrow authorization
model using the unchanged Protocol Sentinel public core.

The external Solidity implementation is not modified.

## Scenarios

1. DEFAULT_ADMIN_ROLE cannot upgrade implementation.
2. FACILITATOR_ROLE cannot upgrade implementation.
3. Owner can perform an authorized UUPS upgrade.
4. Following an authorized V1-to-V2 upgrade, admin and
   facilitator remain unable to upgrade implementation.

## Reproduction

Use a checkout of the external repository at the recorded
source commit, with its declared Foundry dependencies.

Make Protocol Sentinel available as a local dependency.

Add this Foundry remapping:

    protocol-sentinel/=lib/protocol-sentinel/src/

Copy ExternalSentinelIntegration.t.sol into the external
repository's test directory.

Then execute:

    forge test --offline --match-path test/ExternalSentinelIntegration.t.sol -vv

## Limitations

The V2 contract is defined inside the integration test.

This verifies declared permissions in a local synthetic
upgrade workflow, not an actual production upgrade.

The integration was written by the Sentinel developers,
not by the external project's maintainers.

The local dependency was connected using a filesystem
symlink, not a published versioned package.

The test does not claim to discover a vulnerability.

# Standalone Foundry Consumer

This example demonstrates importing Protocol Sentinel v0.1.0
into an independent Foundry project.

## Verified behavior

- Baseline authorization: PASS
- Intentionally expanded upgrade authority: FAIL
- Snapshot restores the original implementation slot

## Import

Install Protocol Sentinel v0.1.0 as a Foundry dependency.

Configure the remapping:

    protocol-sentinel/=lib/protocol-sentinel/src/

Copy SentinelConsumer.t.sol into the consumer project's
test directory.

Run:

    forge test --match-path test/SentinelConsumer.t.sol -vv

## Scope

This is an API integration smoke test using a mock contract
with an ERC-1967 implementation slot.

It is not a full UUPS proxy integration or a security audit.

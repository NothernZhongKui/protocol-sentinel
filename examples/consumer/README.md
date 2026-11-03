# Standalone Foundry consumer examples

These examples exercise Solidity helper APIs in a separate Foundry project. Python is not required for these library-only examples. The repository CI checks their supported imports and scenarios.

| Example | Purpose |
| --- | --- |
| `SentinelConsumer.t.sol` | Basic authority helper; also exercised against v0.1.0 for compatibility. |
| `SentinelDetailedConsumer.t.sol` | Detailed observation and diagnostic result. |
| `SentinelComparativeConsumer.t.sol` | Compare a declared Direct scenario between implementations. |
| `SentinelTimelockConsumer.t.sol` | Separate OpenZeppelin Timelock route. |

See the [library guide](../../docs/library-quickstart.md), [comparison guide](../../docs/comparative-authority-quickstart.md), and [Timelock guide](../../docs/timelock-route-quickstart.md). To run the independent Timelock consumer from the Sentinel repository root:

```bash
bash scripts/check_timelock_consumer.sh
```

For portable evidence and trusted CI rather than library-only tests, see the [portable quickstart](../../docs/portable-direct-v0.5.md) and [Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer).

The basic example uses a mock with an ERC-1967 implementation slot; it is not a full UUPS proxy integration or a security audit.

# Treasury Direct UUPS example

This complete synthetic example compares the same unauthorized upgrade attempt before and after an authorized upgrade. It is copied from the pinned [Treasury consumer](https://github.com/NothernZhongKui/protocol-sentinel-consumer/tree/146ec1461bf7774ab57b84a2d7f5bc06dfb70138), which is exercised by the project's external integration checks. It illustrates the API; replace the fixture, roles, expected revert and transition with your project's actual contracts before relying on a result.

| Role | In this example |
| --- | --- |
| Baseline implementation | `ConsumerTreasuryV1`, active before the authorized upgrade. |
| Updated implementation | `ConsumerTreasuryV2Safe` or the deliberately unsafe `ConsumerTreasuryV2Unsafe`, installed by the administrator. |
| Probe candidate | `ConsumerTreasuryCandidate`, a separate valid UUPS implementation that the settlement operator attempts to install during each isolated observation. |

The complete example uses Solidity 0.8.24, a Git-pinned compatible `forge-std`, OpenZeppelin Contracts and OpenZeppelin Contracts Upgradeable with the remappings in the [consumer's foundry.toml](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/146ec1461bf7774ab57b84a2d7f5bc06dfb70138/foundry.toml). Its [pinned dependency revisions](https://github.com/NothernZhongKui/protocol-sentinel-consumer/tree/146ec1461bf7774ab57b84a2d7f5bc06dfb70138/lib) are part of the reference fixture. The Direct helper itself does not require OpenZeppelin; these example contracts do.

## Fixture contracts

`src/ConsumerTreasury.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract ConsumerTreasuryV1 is UUPSUpgradeable {
    error NotTreasuryAdmin(address caller);

    address public treasuryAdmin;
    address public settlementOperator;
    uint256 public dailySettlementLimit;

    constructor() {
        _disableInitializers();
    }

    function initialize(address admin, address operator, uint256 limit) external initializer {
        require(admin != address(0), "Invalid admin");
        require(operator != address(0), "Invalid operator");
        require(admin != operator, "Roles must differ");

        __UUPSUpgradeable_init();

        treasuryAdmin = admin;
        settlementOperator = operator;
        dailySettlementLimit = limit;
    }

    function version() external pure virtual returns (uint256) {
        return 1;
    }

    function _authorizeUpgrade(address) internal view virtual override {
        if (msg.sender != treasuryAdmin) {
            revert NotTreasuryAdmin(msg.sender);
        }
    }
}

contract ConsumerTreasuryV2Safe is ConsumerTreasuryV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }
}

contract ConsumerTreasuryV2Unsafe is ConsumerTreasuryV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }

    // Deliberate regression: settlement operators
    // can now authorize implementation upgrades.
    function _authorizeUpgrade(address) internal view override {
        if (msg.sender != treasuryAdmin && msg.sender != settlementOperator) {
            revert NotTreasuryAdmin(msg.sender);
        }
    }
}

contract ConsumerTreasuryCandidate is ConsumerTreasuryV1 {
    function version() external pure override returns (uint256) {
        return 3;
    }
}
```

## Producer and assertions

`test/TreasuryAuthority.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {DirectComparisonCapture} from "protocol-sentinel/DirectComparisonCapture.sol";

import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {
    ConsumerTreasuryV1,
    ConsumerTreasuryV2Safe,
    ConsumerTreasuryV2Unsafe,
    ConsumerTreasuryCandidate
} from "../src/ConsumerTreasury.sol";

contract TreasuryAuthorityTest is DirectComparisonCapture {
    address internal administrator;
    address internal settlementOperator;

    ERC1967Proxy internal treasuryProxy;

    function setUp() public {
        administrator = makeAddr("treasury-administrator");
        settlementOperator = makeAddr("settlement-operator");

        ConsumerTreasuryV1 initial = new ConsumerTreasuryV1();

        bytes memory initialization =
            abi.encodeCall(ConsumerTreasuryV1.initialize, (administrator, settlementOperator, 100 ether));

        treasuryProxy = new ERC1967Proxy(address(initial), initialization);
    }

    function _compareAgainst(address nextImplementation) internal returns (DirectComparisonResult memory result) {
        ConsumerTreasuryCandidate candidate = new ConsumerTreasuryCandidate();

        UpgradeCheck memory spec = UpgradeCheck({
            actor: settlementOperator,
            target: address(treasuryProxy),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSelector(ConsumerTreasuryV1.NotTreasuryAdmin.selector, settlementOperator),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        DirectStage memory beforeStage = _observeDirectStage(spec);

        vm.prank(administrator, administrator);

        ConsumerTreasuryV1(address(treasuryProxy)).upgradeToAndCall(nextImplementation, bytes(""));

        DirectStage memory afterStage = _observeDirectStage(spec);

        bytes32 scenarioId = keccak256("external-treasury-upgrade-authority");

        result = _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        _exportDirectComparison(scenarioId, spec, beforeStage, afterStage, result);
    }

    /// @dev CI producer: capture observations without asserting a verdict.
    /// The trusted Sentinel gate decides PASS, BLOCK or REVIEW.
    function test_SafeUpgradePreservesRestriction() public {
        ConsumerTreasuryV2Safe next = new ConsumerTreasuryV2Safe();

        _compareAgainst(address(next));
    }

    /// @dev Example assertions are independent of the CI producer.
    function test_ExpectSafeUpgradeRestriction() public {
        ConsumerTreasuryV2Safe next = new ConsumerTreasuryV2Safe();

        DirectComparisonResult memory result = _compareAgainst(address(next));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));
    }

    function test_UnsafeUpgradeIntroducesViolation() public {
        ConsumerTreasuryV2Unsafe next = new ConsumerTreasuryV2Unsafe();

        DirectComparisonResult memory result = _compareAgainst(address(next));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));
    }
}
```

`test_SafeUpgradePreservesRestriction` is the producing test: it exports the observed comparison without asserting that the result is safe. The two separate assertion tests check the example's expected safe and deliberately unsafe classifications. Foundry can pass a test that correctly observes a violation; the CI policy decides whether to block.

## Producer configuration

`sentinel-safe.toml`:

```toml
[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "treasury_safe"
contract = "TreasuryAuthorityTest"
test = "test_SafeUpgradePreservesRestriction"
source = "test/TreasuryAuthority.t.sol"
fixture_id = "external-treasury-v1-safe-v2"
scenario_id = "0x86917dbb645eece6a5a6f11fa636fdae5558fa7fd4ab12c07488142cbfbb39bf"
```

The `scenario_id` is the bytes32 value of `keccak256("external-treasury-upgrade-authority")`, used by both comparison and export. Use your own scenario and fixture identifiers in your project.

With the listed dependencies and remappings installed, the fixture tests can be run with:

```bash
forge test --match-path test/TreasuryAuthority.t.sol -vv
```

That command runs Foundry tests; it does not by itself create a verified Sentinel evidence bundle. To execute this producer through the v1 workspace runner, follow [First verified result](../v1-onboarding.md#3-commit-diagnose-and-run), selecting `sentinel-safe.toml` instead of `sentinel.toml`. The consumer configuration, producer, sources and dependency gitlinks must be committed and the checkout clean. Configure the Evidence write permission and ignore rule described in the quickstart.

This fixture only tests the declared actor and action. A successful replay does not authenticate the original EVM execution or establish overall contract security.

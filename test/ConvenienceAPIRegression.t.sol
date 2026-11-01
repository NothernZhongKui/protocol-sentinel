// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV2Risky, UpgradeProbe} from "./fixtures/VaultVersions.sol";

contract ConvenienceAPIRegressionTest is AuthorityRegressionTest {
    function _runCheck(address candidate)
        internal
        returns (UpgradeCheckResult memory)
    {
        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(proxy),
            candidate: candidate,
            expectedRevert: abi.encodeWithSignature(
                "OwnableUnauthorizedAccount(address)",
                operator
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        return _checkIsolatedUpgrade(spec);
    }

    function test_ConvenienceAPI_BaselinePass() public {
        UpgradeProbe candidate = new UpgradeProbe();

        UpgradeCheckResult memory result = _runCheck(address(candidate));

        assertEq(
            uint256(result.status),
            uint256(PolicyStatus.PASS)
        );
        assertFalse(result.observation.success);
    }

    function test_ConvenienceAPI_RiskyFail() public {
        VaultV2Risky risky = new VaultV2Risky();

        _upgradeViaTimelock(
            address(risky),
            keccak256("convenience-api-regression")
        );

        UpgradeProbe candidate = new UpgradeProbe();

        bytes32 beforeSlot = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        UpgradeCheckResult memory result = _runCheck(address(candidate));

        assertEq(
            uint256(result.status),
            uint256(PolicyStatus.FAIL)
        );
        assertTrue(result.observation.success);

        // The public API must preserve the original EVM state.
        assertEq(
            vm.load(address(proxy), ERC1967_IMPL_SLOT),
            beforeSlot
        );
    }
}

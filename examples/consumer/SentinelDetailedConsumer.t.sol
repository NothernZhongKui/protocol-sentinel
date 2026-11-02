// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "protocol-sentinel/AuthorityProbe.sol";
import {MockTarget, MockCandidate} from "./SentinelConsumer.t.sol";

contract SentinelDetailedConsumerTest is AuthorityProbe {
    function test_ExternalDetailedApiPassFail() public {
        address operator = address(0xBEEF);

        MockCandidate initial = new MockCandidate();
        MockCandidate candidate = new MockCandidate();

        MockTarget target = new MockTarget(address(initial), address(this));

        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(target),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSelector(MockTarget.NotGovernor.selector, operator),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        bytes32 beforeSlot = vm.load(address(target), ERC1967_IMPL_SLOT);

        DetailedUpgradeCheckResult memory baseline = _checkIsolatedUpgradeDetailed(spec);

        assertEq(uint256(baseline.status), uint256(PolicyStatus.PASS));
        assertEq(uint256(baseline.reason), uint256(PolicyReason.NONE));
        assertFalse(baseline.observation.success);

        target.enableRiskyUpgrade();

        DetailedUpgradeCheckResult memory regression = _checkIsolatedUpgradeDetailed(spec);

        assertEq(uint256(regression.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(regression.reason), uint256(PolicyReason.NONE));
        assertTrue(regression.observation.success);

        assertEq(address(uint160(uint256(regression.observation.implementationAfter))), address(candidate));

        // The isolated probe must restore the implementation.
        assertEq(vm.load(address(target), ERC1967_IMPL_SLOT), beforeSlot);
    }
}

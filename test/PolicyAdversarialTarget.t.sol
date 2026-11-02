// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";
import {RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

// Not a proxy. It simply returns the expected error.
contract FakeUpgradeRejector {
    error NotAuthorized(address caller);

    fallback() external payable {
        revert NotAuthorized(msg.sender);
    }
}

contract PolicyAdversarialTargetTest is AuthorityProbe {
    address internal constant ACTOR = address(0xA11CE);

    function _check(address target, UpgradePolicy policy, bytes memory expectedRevert)
        internal
        returns (DetailedUpgradeCheckResult memory)
    {
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        return _checkIsolatedUpgradeDetailed(
            UpgradeCheck({
                actor: ACTOR,
                target: target,
                candidate: address(candidate),
                expectedRevert: expectedRevert,
                policy: policy
            })
        );
    }

    function test_FakeProxyMustNotPass() public {
        FakeUpgradeRejector fake = new FakeUpgradeRejector();

        DetailedUpgradeCheckResult memory result = _check(
            address(fake),
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            abi.encodeWithSelector(FakeUpgradeRejector.NotAuthorized.selector, ACTOR)
        );

        assertEq(uint256(result.status), uint256(PolicyStatus.UNKNOWN), "Non-proxy incorrectly classified as PASS");
    }

    function test_EmptyAddressMustNotFailAsUpgrade() public {
        address emptyTarget = address(0xBEEF);

        assertEq(emptyTarget.code.length, 0);

        DetailedUpgradeCheckResult memory result =
            _check(emptyTarget, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, hex"deadbeef");

        assertEq(uint256(result.status), uint256(PolicyStatus.UNKNOWN), "No-code target incorrectly classified as FAIL");
    }
}

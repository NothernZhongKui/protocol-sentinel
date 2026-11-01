// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV2Risky, UpgradeProbe} from "./fixtures/VaultVersions.sol";

contract ReviewOriginBindingTest is AuthorityRegressionTest {
    function _check(Observation memory obs, address candidate) internal view returns (PolicyStatus) {
        return _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            bytes32(uint256(uint160(candidate))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );
    }

    function test_OriginBinding_PassRequiresMatchingOrigin() public {
        UpgradeProbe candidate = new UpgradeProbe();

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        assertEq(obs.txOrigin, operator);
        assertEq(uint256(_check(obs, address(candidate))), uint256(PolicyStatus.PASS));

        // Simulate an inconsistent saved Observation.
        obs.txOrigin = makeAddr("different-origin");

        assertEq(
            uint256(_check(obs, address(candidate))),
            uint256(PolicyStatus.UNKNOWN),
            "Origin mismatch must not produce PASS"
        );
    }

    function test_OriginBinding_FailRequiresMatchingOrigin() public {
        VaultV2Risky risky = new VaultV2Risky();
        UpgradeProbe candidate = new UpgradeProbe();

        _upgradeViaTimelock(address(risky), keccak256("review-origin-binding"));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        assertEq(uint256(_check(obs, address(candidate))), uint256(PolicyStatus.FAIL));

        obs.txOrigin = makeAddr("different-origin");

        assertEq(
            uint256(_check(obs, address(candidate))),
            uint256(PolicyStatus.UNKNOWN),
            "Origin mismatch must not produce FAIL"
        );
    }
}

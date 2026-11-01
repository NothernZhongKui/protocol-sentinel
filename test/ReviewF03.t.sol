// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV2Risky} from "./fixtures/VaultVersions.sol";

contract MutableCandidateF03 {
    bool public valid = true;

    function invalidate() external {
        valid = false;
    }

    function proxiableUUID() external view returns (bytes32) {
        if (!valid) return bytes32(0);

        return 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    }
}

contract ReviewF03Test is AuthorityRegressionTest {
    function test_F03_SameObservationMustKeepVerdict() public {
        VaultV2Risky risky = new VaultV2Risky();
        MutableCandidateF03 candidate = new MutableCandidateF03();

        _upgradeViaTimelock(address(risky), keccak256("review-F03"));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        assertTrue(obs.success);
        assertNotEq(obs.implementationBefore, obs.implementationAfter);

        bytes32 expectedImplementation = bytes32(uint256(uint160(address(candidate))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus first = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        assertEq(uint256(first), uint256(PolicyStatus.FAIL));

        // Change candidate state AFTER the observation.
        candidate.invalidate();

        PolicyStatus second = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        // Same evidence must always produce the same verdict.
        assertEq(uint256(second), uint256(first), "F03: verdict changed after candidate mutation");
    }
}

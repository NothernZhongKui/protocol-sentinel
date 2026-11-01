// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV2Risky} from "./fixtures/VaultVersions.sol";

// Candidate behaves differently depending on the caller.
contract ProxyContextCandidate {
    address immutable expectedProxy;

    bytes32 constant IMPLEMENTATION_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    constructor(address proxy_) {
        expectedProxy = proxy_;
    }

    function proxiableUUID() external view returns (bytes32) {
        if (msg.sender == expectedProxy) {
            return IMPLEMENTATION_SLOT;
        }

        return bytes32(0);
    }
}

contract ReviewCandidatePrecedenceTest is AuthorityRegressionTest {
    function test_P1_ConfirmedUpgradeMustNotBeUnknown() public {
        VaultV2Risky risky = new VaultV2Risky();

        ProxyContextCandidate candidate = new ProxyContextCandidate(address(proxy));

        _upgradeViaTimelock(address(risky), keccak256("review-candidate-precedence"));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        // Observer's precondition check is negative.
        assertFalse(obs.candidateValidAtObservation);

        // But the actual upgrade succeeded.
        assertTrue(obs.success);

        assertNotEq(obs.implementationBefore, obs.implementationAfter);

        assertEq(obs.implementationAfter, bytes32(uint256(uint160(address(candidate)))));

        bytes32 expectedImplementation = bytes32(uint256(uint160(address(candidate))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus replacement = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        PolicyStatus successfulCall = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        // Confirmed violations must not become UNKNOWN.
        assertEq(uint256(replacement), uint256(PolicyStatus.FAIL), "P1: confirmed replacement classified incorrectly");

        assertEq(
            uint256(successfulCall), uint256(PolicyStatus.FAIL), "P1: successful upgrade call classified incorrectly"
        );
    }
}

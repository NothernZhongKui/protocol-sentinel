// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {UpgradeProbe} from "./fixtures/VaultVersions.sol";

// Adversarial fixture from Astra's independent review.
contract RedirectingVaultF01 is VaultV1 {
    address immutable destination;

    constructor(address destination_) {
        destination = destination_;
    }

    function upgradeToAndCall(address, bytes memory) public payable override {
        bytes32 slot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

        address next = destination;

        assembly {
            sstore(slot, next)
        }
    }
}

contract ReviewF01Test is AuthorityRegressionTest {
    function test_F01_RedirectedUpgradeMustFail() public {
        UpgradeProbe requested = new UpgradeProbe();
        UpgradeProbe actual = new UpgradeProbe();

        RedirectingVaultF01 redirect = new RedirectingVaultF01(address(actual));

        _upgradeViaTimelock(address(redirect), keccak256("review-F01"));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(requested), bytes(""));

        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        // The EVM really replaced the implementation.
        assertTrue(obs.success);
        assertNotEq(obs.implementationBefore, obs.implementationAfter);

        assertEq(obs.implementationAfter, bytes32(uint256(uint160(address(actual)))));

        bytes32 expectedImplementation = bytes32(uint256(uint160(address(requested))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus replacementPolicy = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        PolicyStatus successfulCallPolicy = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        // Both policies must detect this violation.
        assertEq(uint256(replacementPolicy), uint256(PolicyStatus.FAIL), "F01: replacement policy missed violation");

        assertEq(
            uint256(successfulCallPolicy), uint256(PolicyStatus.FAIL), "F01: successful-call policy missed violation"
        );
    }
}

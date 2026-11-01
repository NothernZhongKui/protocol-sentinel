// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {UpgradeProbe} from "./fixtures/VaultVersions.sol";

// Synthetic fixture: modifies only a high bit of the ERC-1967 word.
contract HighBitsOnlyVaultP2 is VaultV1 {
    function upgradeToAndCall(address, bytes memory) public payable override {
        bytes32 slot =
            0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

        assembly {
            sstore(slot, xor(sload(slot), shl(200, 1)))
        }
    }
}

contract ReviewImplementationAddressTest is AuthorityRegressionTest {
    function test_P2_HighBitsAreNotImplementationReplacement() public {
        HighBitsOnlyVaultP2 scenario = new HighBitsOnlyVaultP2();
        UpgradeProbe candidate = new UpgradeProbe();

        _upgradeViaTimelock(
            address(scenario),
            keccak256("review-P2-high-bits")
        );

        assertEq(vault.version(), 1);

        bytes memory payload = abi.encodeWithSignature(
            "upgradeToAndCall(address,bytes)",
            address(candidate),
            bytes("")
        );

        // Observe the actual execution and resulting proxy behavior.
        Observation memory obs = _observeCall(
            operator,
            address(proxy),
            payload,
            IMPLEMENTATION_SLOT
        );

        assertTrue(obs.success);
        assertTrue(obs.candidateValidAtObservation);

        // Full storage words differ.
        assertNotEq(
            obs.implementationBefore,
            obs.implementationAfter
        );

        // Effective implementation addresses do not.
        address beforeAddress =
            address(uint160(uint256(obs.implementationBefore)));

        address afterAddress =
            address(uint160(uint256(obs.implementationAfter)));

        assertEq(beforeAddress, afterAddress);
        assertEq(afterAddress, address(scenario));

        // The proxy still executes the original implementation.
        assertEq(vault.version(), 1);

        bytes32 expectedImplementation =
            bytes32(uint256(uint160(address(candidate))));

        bytes memory expectedRevert = abi.encodeWithSignature(
            "OwnableUnauthorizedAccount(address)",
            operator
        );

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

        assertEq(
            uint256(replacement),
            uint256(PolicyStatus.UNKNOWN),
            "P2: storage word change is not implementation replacement"
        );

        assertEq(
            uint256(successfulCall),
            uint256(PolicyStatus.FAIL),
            "P2: successful upgrade call must remain FAIL"
        );
    }
}

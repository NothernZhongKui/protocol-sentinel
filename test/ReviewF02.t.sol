// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityRegressionTest} from "./AuthorityRegression.t.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {UpgradeProbe} from "./fixtures/VaultVersions.sol";

contract OriginSensitiveVaultF02 is VaultV1 {
    function _authorizeUpgrade(address) internal view override {
        if (msg.sender != tx.origin) {
            revert OwnableUnauthorizedAccount(msg.sender);
        }
    }
}

contract ReviewF02Test is AuthorityRegressionTest {
    function test_F02_DirectEOAProbeMustMatchRealEOA() public {
        OriginSensitiveVaultF02 originVault = new OriginSensitiveVaultF02();

        UpgradeProbe candidate = new UpgradeProbe();

        _upgradeViaTimelock(address(originVault), keccak256("review-F02"));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        bytes32 baseline = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        // Sentinel's current execution observer.
        Observation memory obs = _observeIsolatedCall(operator, address(proxy), payload, IMPLEMENTATION_SLOT);

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), baseline);

        // Control: direct EOA transaction with sender == origin.
        uint256 snapshotId = vm.snapshotState();

        vm.prank(operator, operator);
        (bool controlSuccess,) = address(proxy).call(payload);

        assertTrue(controlSuccess, "EOA control failed");

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), bytes32(uint256(uint160(address(candidate)))));

        assertTrue(vm.revertToStateAndDelete(snapshotId), "Control snapshot restore failed");

        assertEq(obs.actor, operator);
        assertEq(obs.txOrigin, operator);

        // Sentinel must reproduce the direct EOA behavior.
        assertTrue(obs.success, "F02: EOA probe incorrectly rejected call");

        assertEq(obs.implementationAfter, bytes32(uint256(uint160(address(candidate)))));
    }
}

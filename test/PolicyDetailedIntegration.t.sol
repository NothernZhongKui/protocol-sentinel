// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {RoleVaultV1, RoleVaultV2Risky, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract PolicyDetailedIntegrationTest is AuthorityProbe {
    address internal governor;
    address internal operator;

    ERC1967Proxy internal proxy;
    RoleVaultV1 internal vault;
    RoleVaultCandidate internal candidate;

    function setUp() public {
        governor = makeAddr("diagnostic-governor");
        operator = makeAddr("diagnostic-operator");

        RoleVaultV1 implementation = new RoleVaultV1();

        proxy = new ERC1967Proxy(address(implementation), abi.encodeCall(RoleVaultV1.initialize, (governor, operator)));

        vault = RoleVaultV1(address(proxy));
        candidate = new RoleVaultCandidate();
    }

    function _spec() internal view returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: operator,
            target: address(proxy),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function test_DetailedBaselinePass() public {
        bytes32 beforeSlot = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(_spec());

        assertEq(uint256(result.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.reason), uint256(PolicyReason.NONE));

        assertFalse(result.observation.success);
        assertEq(result.observation.implementationBefore, beforeSlot);
        assertEq(result.observation.implementationAfter, beforeSlot);

        // The probe must not change the real fixture state.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), beforeSlot);
    }

    function test_DetailedRiskyV2Fail() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();

        // Legitimate governor installs the unsafe version.
        vm.prank(governor, governor);
        vault.upgradeToAndCall(address(risky), bytes(""));

        assertTrue(vault.hasRole(vault.OPERATOR_ROLE(), operator));

        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));

        bytes32 beforeSlot = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(_spec());

        assertEq(uint256(result.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.reason), uint256(PolicyReason.NONE));

        assertTrue(result.observation.success);

        assertEq(result.observation.implementationBefore, beforeSlot);

        assertEq(address(uint160(uint256(result.observation.implementationAfter))), address(candidate));

        // Sentinel restored the risky V2 after observing the breach.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), beforeSlot);

        assertEq(vault.version(), 2);
    }
}

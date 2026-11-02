// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "protocol-sentinel/AuthorityProbe.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {X402Escrow} from "../src/X402Escrow.sol";
import {LocalX402EscrowRisky} from "./fixtures/SentinelRiskyEscrow.sol";

// Local initialization stub; no payment operations are tested.
contract LocalTokenStub {}

// Test-only V2; original Fortytwo source is unchanged.
contract LocalX402EscrowV2 is X402Escrow {
    function version() external pure returns (uint256) {
        return 2;
    }
}

contract ExternalSentinelIntegrationTest is AuthorityProbe {
    X402Escrow escrow;
    X402Escrow candidate;

    address owner;
    address admin;
    address facilitator;

    function setUp() public {
        owner = makeAddr("owner");
        admin = makeAddr("admin");
        facilitator = makeAddr("facilitator");

        LocalTokenStub token = new LocalTokenStub();

        X402Escrow implementation = new X402Escrow();
        candidate = new X402Escrow();

        ERC1967Proxy proxy = new ERC1967Proxy(
            address(implementation), abi.encodeCall(X402Escrow.initialize, (address(token), facilitator, admin, owner))
        );

        escrow = X402Escrow(address(proxy));
    }

    function _check(address actor) internal returns (UpgradeCheckResult memory) {
        UpgradeCheck memory spec = UpgradeCheck({
            actor: actor,
            target: address(escrow),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", actor),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        return _checkIsolatedUpgrade(spec);
    }

    function test_AdminCannotUpgrade() public {
        assertTrue(escrow.hasRole(escrow.DEFAULT_ADMIN_ROLE(), admin));

        UpgradeCheckResult memory result = _check(admin);

        assertEq(uint256(result.status), uint256(PolicyStatus.PASS));
        assertFalse(result.observation.success);
        assertEq(result.observation.implementationBefore, result.observation.implementationAfter);
    }

    function test_FacilitatorCannotUpgrade() public {
        assertTrue(escrow.hasRole(escrow.FACILITATOR_ROLE(), facilitator));

        UpgradeCheckResult memory result = _check(facilitator);

        assertEq(uint256(result.status), uint256(PolicyStatus.PASS));
        assertFalse(result.observation.success);
        assertEq(result.observation.implementationBefore, result.observation.implementationAfter);
    }

    function test_OwnerCanUpgrade() public {
        bytes32 beforeSlot = vm.load(address(escrow), ERC1967_IMPL_SLOT);

        vm.prank(owner, owner);

        escrow.upgradeToAndCall(address(candidate), bytes(""));

        bytes32 afterSlot = vm.load(address(escrow), ERC1967_IMPL_SLOT);

        assertNotEq(beforeSlot, afterSlot);

        assertEq(address(uint160(uint256(afterSlot))), address(candidate));

        assertEq(escrow.owner(), owner);

        assertTrue(escrow.hasRole(escrow.DEFAULT_ADMIN_ROLE(), admin));

        assertTrue(escrow.hasRole(escrow.FACILITATOR_ROLE(), facilitator));
    }

    function test_AuthorityPreservedAfterUpgrade() public {
        // Baseline: both restricted actors are rejected.
        assertEq(uint256(_check(admin).status), uint256(PolicyStatus.PASS));
        assertEq(uint256(_check(facilitator).status), uint256(PolicyStatus.PASS));

        // Authorized owner installs a test-only V2.
        LocalX402EscrowV2 v2 = new LocalX402EscrowV2();

        vm.prank(owner, owner);
        escrow.upgradeToAndCall(address(v2), bytes(""));

        assertEq(LocalX402EscrowV2(address(escrow)).version(), 2);
        assertEq(escrow.owner(), owner);

        // Roles survive the upgrade.
        assertTrue(escrow.hasRole(escrow.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(escrow.hasRole(escrow.FACILITATOR_ROLE(), facilitator));

        // The same authorization restrictions must survive.
        assertEq(uint256(_check(admin).status), uint256(PolicyStatus.PASS));
        assertEq(uint256(_check(facilitator).status), uint256(PolicyStatus.PASS));
    }

    function test_AuthorityRegression_PassFailPass() public {
        // V1: facilitator has no upgrade authority.
        assertTrue(escrow.hasRole(escrow.FACILITATOR_ROLE(), facilitator));

        UpgradeCheckResult memory baseline = _check(facilitator);

        assertEq(uint256(baseline.status), uint256(PolicyStatus.PASS));
        assertFalse(baseline.observation.success);

        // Owner installs an intentionally unsafe test-only V2.
        LocalX402EscrowRisky riskyV2 = new LocalX402EscrowRisky();

        vm.prank(owner, owner);
        escrow.upgradeToAndCall(address(riskyV2), bytes(""));

        assertEq(address(uint160(uint256(vm.load(address(escrow), ERC1967_IMPL_SLOT)))), address(riskyV2));

        assertEq(escrow.owner(), owner);
        assertTrue(escrow.hasRole(escrow.FACILITATOR_ROLE(), facilitator));

        // V2 risky: same facilitator can now replace implementation.
        UpgradeCheckResult memory regression = _check(facilitator);

        assertEq(uint256(regression.status), uint256(PolicyStatus.FAIL));

        assertTrue(regression.observation.success);

        assertNotEq(regression.observation.implementationBefore, regression.observation.implementationAfter);

        assertEq(address(uint160(uint256(regression.observation.implementationAfter))), address(candidate));

        // Probe was isolated: risky implementation remains installed.
        assertEq(address(uint160(uint256(vm.load(address(escrow), ERC1967_IMPL_SLOT)))), address(riskyV2));

        // Admin was not accidentally granted upgrade authority.
        assertEq(uint256(_check(admin).status), uint256(PolicyStatus.PASS));

        // Owner installs a fixed test-only V2.
        LocalX402EscrowV2 fixedV2 = new LocalX402EscrowV2();

        vm.prank(owner, owner);
        escrow.upgradeToAndCall(address(fixedV2), bytes(""));

        assertEq(LocalX402EscrowV2(address(escrow)).version(), 2);

        // V2 fixed: facilitator loses unauthorized upgrade authority.
        UpgradeCheckResult memory repaired = _check(facilitator);

        assertEq(uint256(repaired.status), uint256(PolicyStatus.PASS));
        assertFalse(repaired.observation.success);

        // Positive control: owner can still upgrade.
        vm.prank(owner, owner);
        escrow.upgradeToAndCall(address(candidate), bytes(""));

        assertEq(escrow.owner(), owner);

        assertEq(address(uint160(uint256(vm.load(address(escrow), ERC1967_IMPL_SLOT)))), address(candidate));
    }
}

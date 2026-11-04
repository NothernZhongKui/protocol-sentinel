// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {IAccessControl} from
    "@openzeppelin/contracts/access/IAccessControl.sol";

import {Capu} from "@capu/Capu.sol";
import {Fixture} from "./helpers/Fixture.sol";

// Safe updated implementation.
// The original upgrade authorization is inherited unchanged.
contract CapuSafePilotV2 is Capu {
    function pilotVersion() external pure returns (uint256) {
        return 2;
    }
}

// Intentionally faulty TEST-ONLY implementation.
//
// The authorized migration grants upgrade authority
// to an actor who did not possess it in the baseline.
//
// This is NOT a vulnerability in upstream Capminal.
contract CapuFaultyPilotV2 is Capu {
    function migratePilotRole(address actor)
        external
        reinitializer(2)
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        _grantRole(DEFAULT_ADMIN_ROLE, actor);
    }
}

// One fixed, valid probe candidate.
// Never used as the authorized updated V2.
contract CapuProbeCandidate is Capu {
    function probeVersion() external pure returns (uint256) {
        return 999;
    }
}

contract AuthorityRegressionOracleTest is Fixture {
    bytes32 internal constant IMPLEMENTATION_SLOT =
        0x360894A13BA1A3210667C828492DB98DCA3E2076CC3735A920A3CA505D382BBC;

    address internal actor;
    CapuProbeCandidate internal probe;

    function setUp() public {
        // Use the existing consumer-owned fixture.
        _deployStack();

        actor = makeAddr("sentinel-outsider");
        probe = new CapuProbeCandidate();

        assertTrue(capu.hasRole(bytes32(0), admin));
        assertFalse(capu.hasRole(bytes32(0), actor));

        assertTrue(_implementation() != address(probe));
    }

    function _implementation()
        internal
        view
        returns (address)
    {
        return address(
            uint160(
                uint256(
                    vm.load(
                        address(capu),
                        IMPLEMENTATION_SLOT
                    )
                )
            )
        );
    }

    function _assertActorRejected() internal {
        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControl
                    .AccessControlUnauthorizedAccount
                    .selector,
                actor,
                bytes32(0)
            )
        );

        vm.prank(actor);
        capu.upgradeToAndCall(address(probe), "");
    }

    function testSafeUpgradePreservesAuthority() public {
        address baseline = _implementation();

        // Before: actor cannot upgrade.
        _assertActorRejected();
        assertEq(_implementation(), baseline);

        CapuSafePilotV2 updated = new CapuSafePilotV2();

        assertTrue(address(updated) != baseline);
        assertTrue(address(updated) != address(probe));

        // Authorized transition.
        vm.prank(admin);
        capu.upgradeToAndCall(address(updated), "");

        assertEq(_implementation(), address(updated));

        // After: actor still cannot upgrade.
        _assertActorRejected();

        assertEq(_implementation(), address(updated));
        assertFalse(capu.hasRole(bytes32(0), actor));
    }

    function testFaultyMigrationGrantsUpgradeAuthority()
        public
    {
        address baseline = _implementation();

        // Before: actor cannot upgrade.
        _assertActorRejected();
        assertEq(_implementation(), baseline);

        CapuFaultyPilotV2 updated =
            new CapuFaultyPilotV2();

        assertTrue(address(updated) != baseline);
        assertTrue(address(updated) != address(probe));

        // Authorized transition with deliberately
        // faulty TEST-ONLY migration.
        vm.prank(admin);
        capu.upgradeToAndCall(
            address(updated),
            abi.encodeCall(
                CapuFaultyPilotV2.migratePilotRole,
                (actor)
            )
        );

        assertEq(_implementation(), address(updated));

        // The actor gained authority during migration.
        assertTrue(capu.hasRole(bytes32(0), actor));

        // After: same actor can now install
        // the same fixed probe candidate.
        vm.prank(actor);
        capu.upgradeToAndCall(address(probe), "");

        assertEq(_implementation(), address(probe));
    }
}

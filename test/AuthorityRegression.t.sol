// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {ITransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {VaultV2Risky, VaultV2Fixed, UpgradeProbe} from "./fixtures/VaultVersions.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract AuthorityRegressionTest is Test {
    uint256 constant DELAY = 48 hours;

    bytes32 constant IMPLEMENTATION_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    bytes32 constant ADMIN_SLOT = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    address operator;
    address proposer;
    address executor;

    TimelockController timelock;
    TransparentUpgradeableProxy proxy;
    VaultV1 vault;
    VaultV1 implementation;

    function setUp() public {
        operator = makeAddr("operator");
        proposer = makeAddr("proposer");
        executor = makeAddr("executor");

        address[] memory proposers = new address[](1);
        proposers[0] = proposer;

        address[] memory executors = new address[](1);
        executors[0] = executor;

        timelock = new TimelockController(DELAY, proposers, executors, address(0));

        implementation = new VaultV1();

        bytes memory initData = abi.encodeCall(VaultV1.initialize, (address(timelock), operator));

        proxy = new TransparentUpgradeableProxy(address(implementation), address(timelock), initData);

        vault = VaultV1(address(proxy));
    }

    function test_BaselineConfiguration() public view {
        assertEq(vault.owner(), address(timelock));
        assertEq(vault.operator(), operator);
        assertEq(vault.version(), 1);
        assertEq(timelock.getMinDelay(), DELAY);

        address admin = address(uint160(uint256(vm.load(address(proxy), ADMIN_SLOT))));

        assertEq(ProxyAdmin(admin).owner(), address(timelock));

        address activeImplementation = address(uint160(uint256(vm.load(address(proxy), IMPLEMENTATION_SLOT))));

        assertEq(activeImplementation, address(implementation));
    }

    function test_OperatorCannotUpgradeDirectly() public {
        VaultV1 candidate = new VaultV1();

        // Verify the upgrade target is UUPS-compatible.
        assertEq(candidate.proxiableUUID(), IMPLEMENTATION_SLOT);

        bytes32 beforeUpgrade = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        vm.expectRevert(abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator));

        vm.prank(operator);
        vault.upgradeToAndCall(address(candidate), "");

        bytes32 afterUpgrade = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        assertEq(afterUpgrade, beforeUpgrade);
    }

    function test_TimelockRequiresFullDelay() public {
        VaultV1 candidate = new VaultV1();
        assertEq(candidate.proxiableUUID(), IMPLEMENTATION_SLOT);

        address adminAddress = address(uint160(uint256(vm.load(address(proxy), ADMIN_SLOT))));

        bytes memory data = abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(address(proxy)), address(candidate), bytes(""))
        );

        bytes32 predecessor = bytes32(0);
        bytes32 salt = keccak256("authorized-upgrade");

        vm.prank(proposer);
        timelock.schedule(adminAddress, 0, data, predecessor, salt, DELAY);

        bytes32 operationId = timelock.hashOperation(adminAddress, 0, data, predecessor, salt);

        uint256 readyAt = timelock.getTimestamp(operationId);
        assertEq(readyAt, block.timestamp + DELAY);

        // One second before the deadline: execution must fail.
        vm.warp(readyAt - 1);

        vm.expectRevert(
            abi.encodeWithSelector(
                TimelockController.TimelockUnexpectedOperationState.selector, operationId, bytes32(uint256(4))
            )
        );

        vm.prank(executor);
        timelock.execute(adminAddress, 0, data, predecessor, salt);

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), bytes32(uint256(uint160(address(implementation)))));

        assertFalse(timelock.isOperationDone(operationId));

        // Exactly at the deadline: execution must succeed.
        vm.warp(readyAt);
        assertTrue(timelock.isOperationReady(operationId));

        vm.prank(executor);
        timelock.execute(adminAddress, 0, data, predecessor, salt);

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), bytes32(uint256(uint160(address(candidate)))));

        assertTrue(timelock.isOperationDone(operationId));
        assertEq(vault.owner(), address(timelock));
        assertEq(vault.version(), 1);
    }

    function test_RiskyUpgradeIntroducesOperatorBypass() public {
        VaultV2Risky risky = new VaultV2Risky();
        UpgradeProbe probe = new UpgradeProbe();

        assertEq(probe.proxiableUUID(), IMPLEMENTATION_SLOT);

        bytes32 adminBefore = vm.load(address(proxy), ADMIN_SLOT);

        address adminAddress = address(uint160(uint256(adminBefore)));

        bytes memory data = abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(address(proxy)), address(risky), bytes(""))
        );

        bytes32 predecessor = bytes32(0);
        bytes32 salt = keccak256("install-risky-v2");

        // Authorized installation of V2 via Timelock.
        vm.prank(proposer);
        timelock.schedule(adminAddress, 0, data, predecessor, salt, DELAY);

        bytes32 operationId = timelock.hashOperation(adminAddress, 0, data, predecessor, salt);

        vm.warp(timelock.getTimestamp(operationId));

        vm.prank(executor);
        timelock.execute(adminAddress, 0, data, predecessor, salt);

        assertTrue(timelock.isOperationDone(operationId));
        assertEq(vault.version(), 2);
        assertEq(vault.owner(), address(timelock));
        assertEq(vault.operator(), operator);
        assertEq(timelock.getMinDelay(), DELAY);

        // Operator performs a second upgrade directly.
        // No new schedule, execute, or time advancement.
        uint256 timeBefore = block.timestamp;

        vm.prank(operator);
        vault.upgradeToAndCall(address(probe), "");

        // Verify actual implementation change.
        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), bytes32(uint256(uint160(address(probe)))));

        assertEq(vault.version(), 3);
        assertEq(block.timestamp, timeBefore);

        // Administrative configuration remains unchanged.
        assertEq(vault.owner(), address(timelock));
        assertEq(vault.operator(), operator);
        assertEq(timelock.getMinDelay(), DELAY);
        assertEq(vm.load(address(proxy), ADMIN_SLOT), adminBefore);
        assertEq(ProxyAdmin(adminAddress).owner(), address(timelock));
    }

    function _upgradeViaTimelock(address nextImplementation, bytes32 salt) internal {
        address admin = address(uint160(uint256(vm.load(address(proxy), ADMIN_SLOT))));

        bytes memory data = abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(address(proxy)), nextImplementation, bytes(""))
        );

        bytes32 predecessor = bytes32(0);

        vm.prank(proposer);
        timelock.schedule(admin, 0, data, predecessor, salt, DELAY);

        bytes32 operationId = timelock.hashOperation(admin, 0, data, predecessor, salt);

        vm.warp(timelock.getTimestamp(operationId));

        vm.prank(executor);
        timelock.execute(admin, 0, data, predecessor, salt);

        assertTrue(timelock.isOperationDone(operationId));
    }

    function test_RiskyUpgradeRejectsOutsider() public {
        VaultV2Risky risky = new VaultV2Risky();
        UpgradeProbe probe = new UpgradeProbe();
        address outsider = makeAddr("outsider");

        _upgradeViaTimelock(address(risky), keccak256("risky-outsider"));

        assertEq(vault.version(), 2);

        bytes32 beforeUpgrade = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        vm.expectRevert(abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", outsider));

        vm.prank(outsider);
        vault.upgradeToAndCall(address(probe), "");

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), beforeUpgrade);
    }

    function test_FixedUpgradeRejectsOperator() public {
        VaultV2Fixed fixedVault = new VaultV2Fixed();
        UpgradeProbe probe = new UpgradeProbe();

        _upgradeViaTimelock(address(fixedVault), keccak256("install-fixed"));

        assertEq(vault.version(), 2);

        bytes32 beforeUpgrade = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        vm.expectRevert(abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator));

        vm.prank(operator);
        vault.upgradeToAndCall(address(probe), "");

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), beforeUpgrade);

        assertEq(vault.owner(), address(timelock));
        assertEq(timelock.getMinDelay(), DELAY);
    }

    function test_FixedKeepsAuthorizedUpgrade() public {
        VaultV2Fixed fixedVault = new VaultV2Fixed();
        UpgradeProbe probe = new UpgradeProbe();

        _upgradeViaTimelock(address(fixedVault), keccak256("install-fixed"));

        _upgradeViaTimelock(address(probe), keccak256("fixed-to-probe"));

        assertEq(vault.version(), 3);

        assertEq(vm.load(address(proxy), IMPLEMENTATION_SLOT), bytes32(uint256(uint160(address(probe)))));

        assertEq(vault.owner(), address(timelock));
    }
}

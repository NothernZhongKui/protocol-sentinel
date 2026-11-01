// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AuthorityProbe} from "./helpers/AuthorityProbe.sol";
import {ITransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {VaultV2Risky, VaultV2Fixed, UpgradeProbe} from "./fixtures/VaultVersions.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

import {NonUUPSImplementation} from "./fixtures/NonUUPSImplementation.sol";

contract AuthorityRegressionTest is AuthorityProbe {
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

    struct TimelockEvidence {
        bytes32 operationId;
        uint256 scheduledAt;
        uint256 readyAt;
        uint256 executedAt;
    }

    function _upgradeViaTimelock(address nextImplementation, bytes32 salt)
        internal
        returns (TimelockEvidence memory history)
    {
        address admin = address(uint160(uint256(vm.load(address(proxy), ADMIN_SLOT))));

        bytes memory data = abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(address(proxy)), nextImplementation, bytes(""))
        );

        bytes32 predecessor = bytes32(0);

        history.scheduledAt = block.timestamp;

        vm.prank(proposer);
        timelock.schedule(admin, 0, data, predecessor, salt, DELAY);

        history.operationId = timelock.hashOperation(admin, 0, data, predecessor, salt);

        history.readyAt = timelock.getTimestamp(history.operationId);

        assertEq(history.readyAt, history.scheduledAt + DELAY);

        vm.warp(history.readyAt);

        vm.prank(executor);
        timelock.execute(admin, 0, data, predecessor, salt);

        history.executedAt = block.timestamp;

        assertTrue(timelock.isOperationDone(history.operationId));

        assertGe(history.executedAt, history.readyAt);
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

    function _checkOperatorPolicy(PolicyStatus expected) internal {
        UpgradeProbe candidate = new UpgradeProbe();

        // Confirm that the upgrade target is valid.
        assertEq(candidate.proxiableUUID(), IMPLEMENTATION_SLOT);

        bytes memory callData =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        // Execute the same probe against the current proxy state.
        Observation memory observation = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        bytes32 expectedImplementation = bytes32(uint256(uint160(address(candidate))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus actual =
            _classifyUpgrade(observation, expectedImplementation, expectedRevert, operator, address(proxy));

        assertEq(uint256(actual), uint256(expected));

        if (actual == PolicyStatus.FAIL) {
            assertTrue(observation.success);
            assertEq(vault.version(), 3);
        } else if (actual == PolicyStatus.PASS) {
            assertFalse(observation.success);
        }
    }

    function test_ProbeClassifiesBaseline() public {
        _checkOperatorPolicy(PolicyStatus.PASS);
    }

    function test_ProbeClassifiesRisky() public {
        VaultV2Risky risky = new VaultV2Risky();

        _upgradeViaTimelock(address(risky), keccak256("probe-risky"));

        _checkOperatorPolicy(PolicyStatus.FAIL);
    }

    function test_ProbeClassifiesFixed() public {
        VaultV2Fixed fixedVault = new VaultV2Fixed();

        _upgradeViaTimelock(address(fixedVault), keccak256("probe-fixed"));

        _checkOperatorPolicy(PolicyStatus.PASS);
    }

    function test_ProbeReturnsUnknownForNonUpgradeCall() public {
        UpgradeProbe candidate = new UpgradeProbe();

        Observation memory observation = _observeCall(
            operator, address(proxy), abi.encodeWithSelector(VaultV1.version.selector), IMPLEMENTATION_SLOT
        );

        PolicyStatus actual = _classifyUpgrade(
            observation,
            bytes32(uint256(uint160(address(candidate)))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );

        assertEq(uint256(actual), uint256(PolicyStatus.UNKNOWN));
    }

    function test_ExportRiskyWitness() public {
        VaultV2Risky risky = new VaultV2Risky();
        UpgradeProbe candidate = new UpgradeProbe();

        assertEq(candidate.proxiableUUID(), IMPLEMENTATION_SLOT);

        // First upgrade: authorized via Timelock.
        TimelockEvidence memory history = _upgradeViaTimelock(address(risky), keccak256("export-risky"));

        assertEq(vault.version(), 2);

        address ownerBefore = vault.owner();
        bytes32 adminBefore = vm.load(address(proxy), ADMIN_SLOT);
        uint256 delayBefore = timelock.getMinDelay();
        uint256 timestampBefore = block.timestamp;

        bytes memory callData =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        // Second upgrade: operator attempts direct execution.
        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        PolicyStatus status = _classifyUpgrade(
            obs,
            bytes32(uint256(uint160(address(candidate)))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );

        // Confirm the regression and unchanged admin settings.
        assertEq(uint256(status), uint256(PolicyStatus.FAIL));
        assertTrue(obs.success);
        assertEq(vault.version(), 3);
        assertEq(vault.owner(), ownerBefore);
        assertEq(vm.load(address(proxy), ADMIN_SLOT), adminBefore);
        assertEq(timelock.getMinDelay(), delayBefore);
        assertEq(block.timestamp, timestampBefore);

        // Build evidence from actual execution observations.
        string memory key = "sentinel_witness";

        vm.serializeString(key, "schema_version", "0.1");
        vm.serializeString(key, "run_kind", "local_fixture");
        vm.serializeString(key, "policy_id", "AR-001");
        vm.serializeString(key, "result", "FAIL");

        vm.serializeAddress(key, "actor", operator);
        vm.serializeAddress(key, "target", address(proxy));
        vm.serializeAddress(key, "owner", ownerBefore);

        vm.serializeBytes(key, "calldata", callData);
        vm.serializeBool(key, "call_success", obs.success);
        vm.serializeBytes(key, "return_data", obs.returnData);

        vm.serializeBytes32(key, "implementation_before", obs.implementationBefore);

        vm.serializeBytes32(key, "implementation_after", obs.implementationAfter);

        vm.serializeBytes32(key, "proxy_admin_slot", adminBefore);
        vm.serializeUint(key, "minimum_delay", delayBefore);
        vm.serializeUint(key, "timestamp_before", timestampBefore);
        vm.serializeUint(key, "timestamp_after", block.timestamp);

        vm.serializeString(key, "coverage", "operator; proxy.upgradeToAndCall; synthetic fixture");

        vm.serializeBytes32(key, "timelock_operation_id", history.operationId);
        vm.serializeUint(key, "timelock_scheduled_at", history.scheduledAt);
        vm.serializeUint(key, "timelock_ready_at", history.readyAt);
        vm.serializeUint(key, "timelock_executed_at", history.executedAt);

        string memory json =
            vm.serializeString(key, "reproduce", "forge test --match-test test_ExportRiskyWitness -vvvv");

        if (vm.envOr("EXPORT_WITNESS", false)) {
            vm.writeJson(json, "./artifacts/demo/authority-regression.json");
        }
    }

    function test_InvalidUpgradeCandidateMustBeUnknown() public {
        address invalidCandidate = makeAddr("invalid-candidate");

        // The candidate has no deployed code.
        assertEq(invalidCandidate.code.length, 0);

        bytes memory callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", invalidCandidate, bytes(""));

        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus actual = _classifyUpgrade(
            obs, bytes32(uint256(uint160(invalidCandidate))), expectedRevert, operator, address(proxy)
        );

        // Invalid test input must not establish security.
        assertEq(uint256(actual), uint256(PolicyStatus.UNKNOWN), "Invalid candidate must produce UNKNOWN");
    }

    function test_DeployedNonUUPSCandidateMustBeUnknown() public {
        NonUUPSImplementation candidate = new NonUUPSImplementation();

        // Code exists, but UUPS is not supported.
        assertGt(address(candidate).code.length, 0);

        bytes32 implementationBefore = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        bytes memory callData =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        PolicyStatus result = _classifyUpgrade(
            obs,
            bytes32(uint256(uint160(address(candidate)))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );

        assertEq(uint256(result), uint256(PolicyStatus.UNKNOWN));

        assertFalse(obs.success);
        assertEq(obs.implementationAfter, implementationBefore);
    }

    function test_SelfUpgradeReturnsUnknown() public {
        VaultV2Risky risky = new VaultV2Risky();

        _upgradeViaTimelock(address(risky), keccak256("self-upgrade"));

        bytes memory callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(risky), bytes(""));

        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        // The call succeeds, but implementation stays the same.
        assertTrue(obs.success);
        assertEq(obs.implementationBefore, obs.implementationAfter);

        PolicyStatus status = _classifyUpgrade(
            obs,
            bytes32(uint256(uint160(address(risky)))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );

        assertEq(uint256(status), uint256(PolicyStatus.UNKNOWN));

        assertEq(vault.version(), 2);
    }

    function test_SelfUpgradeViolatesCallPolicy() public {
        VaultV2Risky risky = new VaultV2Risky();

        _upgradeViaTimelock(address(risky), keccak256("policy-self-upgrade"));

        bytes memory callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(risky), bytes(""));

        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        assertTrue(obs.success);
        assertEq(obs.implementationBefore, obs.implementationAfter);

        bytes32 candidate = bytes32(uint256(uint160(address(risky))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        PolicyStatus replacementPolicy = _evaluateUpgradePolicy(
            obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, candidate, expectedRevert, operator, address(proxy)
        );

        PolicyStatus callPolicy = _evaluateUpgradePolicy(
            obs, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, candidate, expectedRevert, operator, address(proxy)
        );

        assertEq(uint256(replacementPolicy), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(callPolicy), uint256(PolicyStatus.FAIL));
    }

    function test_RegularCallDoesNotViolateUpgradePolicy() public {
        UpgradeProbe candidate = new UpgradeProbe();

        bytes32 beforeCall = vm.load(address(proxy), IMPLEMENTATION_SLOT);

        Observation memory obs =
            _observeCall(operator, address(proxy), abi.encodeWithSignature("version()"), IMPLEMENTATION_SLOT);

        assertTrue(obs.success);
        assertEq(obs.implementationBefore, beforeCall);
        assertEq(obs.implementationAfter, beforeCall);

        PolicyStatus status = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL,
            bytes32(uint256(uint160(address(candidate)))),
            abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator),
            operator,
            address(proxy)
        );

        assertEq(uint256(status), uint256(PolicyStatus.UNKNOWN));
    }

    function test_OutsiderObservationCannotProveOperatorPolicy() public {
        UpgradeProbe candidate = new UpgradeProbe();
        address outsider = makeAddr("outsider");

        bytes memory callData =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        // Observe outsider, not the intended operator.
        Observation memory obs = _observeCall(outsider, address(proxy), callData, IMPLEMENTATION_SLOT);

        assertEq(obs.actor, outsider);
        assertEq(obs.target, address(proxy));
        assertTrue(obs.actor != operator);

        bytes memory outsiderRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", outsider);

        PolicyStatus actual = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            bytes32(uint256(uint160(address(candidate)))),
            outsiderRevert,
            operator,
            address(proxy)
        );

        // An outsider's result cannot certify operator policy.
        assertEq(uint256(actual), uint256(PolicyStatus.UNKNOWN), "Actor mismatch must produce UNKNOWN");
    }

    function test_TargetMismatchCannotCertifyPolicy() public {
        UpgradeProbe candidate = new UpgradeProbe();

        bytes memory callData =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", address(candidate), bytes(""));

        Observation memory obs = _observeCall(operator, address(proxy), callData, IMPLEMENTATION_SLOT);

        bytes32 expectedImplementation = bytes32(uint256(uint160(address(candidate))));

        bytes memory expectedRevert = abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", operator);

        // Correctly bound observation establishes PASS.
        PolicyStatus correct = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            address(proxy)
        );

        assertEq(uint256(correct), uint256(PolicyStatus.PASS));

        // Same observation cannot certify another target.
        address otherTarget = makeAddr("other-target");

        PolicyStatus mismatch = _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            operator,
            otherTarget
        );

        assertEq(uint256(mismatch), uint256(PolicyStatus.UNKNOWN));
    }
}

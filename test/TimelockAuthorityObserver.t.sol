// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

// Deliberately NOT UUPS implementations.
contract PlainImplementationV1 {
    function version() external pure returns (uint256) {
        return 1;
    }
}

contract PlainImplementationV2 {
    function version() external pure returns (uint256) {
        return 2;
    }
}

contract TimelockAuthorityObserverTest is TimelockAuthorityProbe {
    uint256 internal constant DELAY = 48 hours;

    address internal proposer;
    address internal executor;

    TimelockController internal controller;
    TransparentUpgradeableProxy internal proxy;
    ProxyAdmin internal admin;

    PlainImplementationV1 internal initial;
    PlainImplementationV2 internal candidate;

    function setUp() public {
        proposer = makeAddr("route-proposer");
        executor = makeAddr("route-executor");

        initial = new PlainImplementationV1();
        candidate = new PlainImplementationV2();

        _deploy(false);
    }

    function _deploy(bool openExecution) internal {
        address[] memory proposers = new address[](1);
        proposers[0] = proposer;

        address[] memory executors = new address[](1);
        executors[0] = openExecution ? address(0) : executor;

        controller = new TimelockController(DELAY, proposers, executors, address(0));

        // OZ 5.x creates its own ProxyAdmin.
        // The second constructor argument is initialOwner.
        proxy = new TransparentUpgradeableProxy(address(initial), address(controller), bytes(""));

        address adminAddress = address(uint160(uint256(vm.load(address(proxy), ERC1967_ADMIN_SLOT))));

        admin = ProxyAdmin(adminAddress);

        assertTrue(address(admin).code.length > 0);
        assertEq(admin.owner(), address(controller));
    }

    function _spec(TimelockProperty property) internal view returns (TimelockScenario memory) {
        return TimelockScenario({
            timelock: address(controller),
            proposer: proposer,
            executor: executor,
            proxyAdmin: address(admin),
            proxy: address(proxy),
            candidate: address(candidate),
            predecessor: bytes32(0),
            salt: keccak256("real-routed-operation"),
            property: property
        });
    }

    function _schedule(TimelockScenario memory spec) internal {
        vm.prank(proposer, proposer);

        controller.schedule(spec.proxyAdmin, 0, _timelockUpgradePayload(spec), spec.predecessor, spec.salt, DELAY);

        assertTrue(controller.isOperationPending(_timelockOperationId(spec)));
    }

    function _advanceToReady(TimelockScenario memory spec) internal {
        uint256 readyAt = controller.getTimestamp(_timelockOperationId(spec));

        vm.warp(readyAt);

        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));
    }

    function evaluateExternal(TimelockScenario memory spec, RoutedObservation memory obs)
        external
        pure
        returns (RoutedEvaluation memory)
    {
        return _evaluateTimelockRoute(spec, obs);
    }

    function _assertEvaluation(
        TimelockScenario memory spec,
        RoutedObservation memory obs,
        PolicyStatus status,
        RoutedReason reason
    ) internal pure {
        RoutedEvaluation memory result = _evaluateTimelockRoute(spec, obs);

        assertEq(uint256(result.status), uint256(status));
        assertEq(uint256(result.reason), uint256(reason));
    }

    function test_ReadyRealExecutionAndSnapshotRestoration() public {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _schedule(spec);
        _advanceToReady(spec);

        bytes32 originalImplementation = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertEq(obs.executor, executor);
        assertEq(obs.txOrigin, executor);
        assertEq(obs.outerTarget, address(controller));

        assertTrue(obs.outerSuccess);
        assertFalse(obs.operationDoneBefore);
        assertTrue(obs.operationDoneAfter);

        assertEq(obs.implementationBefore, originalImplementation);

        assertEq(address(uint160(uint256(obs.implementationAfter))), address(candidate));

        _assertEvaluation(spec, obs, PolicyStatus.PASS, RoutedReason.NONE);

        // These checks describe the state AFTER probe restoration.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), originalImplementation);

        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));

        assertFalse(controller.isOperationDone(_timelockOperationId(spec)));

        assertEq(admin.owner(), address(controller));
    }

    function test_WaitingExactRevertAndTwoIsolatedProbes() public {
        TimelockScenario memory spec = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        _schedule(spec);

        bytes32 operationId = _timelockOperationId(spec);
        uint256 timestampBefore = vm.getBlockTimestamp();

        RoutedObservation memory first = _observeIsolatedTimelockRoute(spec);

        RoutedObservation memory second = _observeIsolatedTimelockRoute(spec);

        assertFalse(first.outerSuccess);
        assertFalse(second.outerSuccess);

        assertEq(first.operationId, second.operationId);
        assertEq(first.returnData, second.returnData);

        bytes memory expected = abi.encodeWithSelector(
            TimelockController.TimelockUnexpectedOperationState.selector, operationId, bytes32(uint256(4))
        );

        assertEq(first.returnData, expected);

        _assertEvaluation(spec, first, PolicyStatus.PASS, RoutedReason.NONE);

        _assertEvaluation(spec, second, PolicyStatus.PASS, RoutedReason.NONE);

        assertEq(vm.getBlockTimestamp(), timestampBefore);

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), first.implementationBefore);

        assertEq(uint256(controller.getOperationState(operationId)), uint256(TimelockController.OperationState.Waiting));
    }

    function test_ExactReadinessBoundary() public {
        TimelockScenario memory spec = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        _schedule(spec);

        uint256 readyAt = controller.getTimestamp(_timelockOperationId(spec));

        vm.warp(readyAt - 1);

        RoutedObservation memory waiting = _observeIsolatedTimelockRoute(spec);

        _assertEvaluation(spec, waiting, PolicyStatus.PASS, RoutedReason.NONE);

        // Advancing time is explicit test preparation.
        vm.warp(readyAt);

        spec.property = TimelockProperty.READY_UPGRADE_SUCCEEDS;

        RoutedObservation memory ready = _observeIsolatedTimelockRoute(spec);

        assertEq(ready.observedTimestamp, ready.readyAt);
        assertTrue(ready.outerSuccess);

        _assertEvaluation(spec, ready, PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_OpenExecutorRoleRealExecution() public {
        _deploy(true);

        TimelockScenario memory spec = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        _schedule(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertFalse(obs.executorHasRole);
        assertTrue(obs.openExecutorRole);

        _assertEvaluation(spec, obs, PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_UnauthorizedExecutorIsPreparationError() public {
        TimelockScenario memory spec = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        spec.executor = makeAddr("unauthorized-executor");

        _schedule(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertFalse(obs.outerSuccess);
        assertFalse(obs.executorHasRole);
        assertFalse(obs.openExecutorRole);

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.INELIGIBLE_EXECUTOR)
        );

        this.evaluateExternal(spec, obs);
    }

    function test_ReadyUnfinishedPredecessorDoesNotFailPolicy() public {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        spec.predecessor = keccak256("unfinished-dependency");

        _schedule(spec);
        _advanceToReady(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertEq(uint256(obs.operationStateBefore), uint256(TimelockController.OperationState.Ready));

        assertFalse(obs.outerSuccess);
        assertTrue(obs.predecessorStateObserved);
        assertFalse(obs.predecessorDoneBefore);

        assertEq(
            obs.returnData,
            abi.encodeWithSelector(TimelockController.TimelockUnexecutedPredecessor.selector, spec.predecessor)
        );

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.UNFINISHED_PREDECESSOR)
        );

        this.evaluateExternal(spec, obs);

        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));
    }

    function test_WrongProxyAdminOwnerIsPreparationError() public {
        address outsider = makeAddr("other-admin-owner");

        TransparentUpgradeableProxy wrongProxy = new TransparentUpgradeableProxy(address(initial), outsider, bytes(""));

        address wrongAdminAddress = address(uint160(uint256(vm.load(address(wrongProxy), ERC1967_ADMIN_SLOT))));

        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        spec.proxy = address(wrongProxy);
        spec.proxyAdmin = wrongAdminAddress;

        _schedule(spec);
        _advanceToReady(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertFalse(obs.proxyAdminOwnedByTimelock);
        assertFalse(obs.outerSuccess);

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.INVALID_PROXY_ADMIN)
        );

        this.evaluateExternal(spec, obs);
    }

    function test_TransparentCandidateNeedsNoUUPSInterface() public {
        // PlainImplementationV2 intentionally has no proxiableUUID().
        (bool supportsUUPS,) = address(candidate).staticcall(abi.encodeWithSignature("proxiableUUID()"));

        assertFalse(supportsUUPS);

        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _schedule(spec);
        _advanceToReady(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        _assertEvaluation(spec, obs, PolicyStatus.PASS, RoutedReason.NONE);
    }
}

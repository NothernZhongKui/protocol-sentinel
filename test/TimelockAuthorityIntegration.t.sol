// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

// Clean, non-UUPS implementation contracts.
contract RouteImplementationV1 {
    function version() external pure returns (uint256) {
        return 1;
    }
}

contract RouteImplementationV2 {
    function version() external pure returns (uint256) {
        return 2;
    }
}

contract RouteImplementationV3 {
    function version() external pure returns (uint256) {
        return 3;
    }
}

contract TimelockAuthorityIntegrationTest is TimelockAuthorityProbe {
    uint256 internal constant DELAY = 48 hours;

    address internal proposer;
    address internal executor;

    TimelockController internal controller;
    TransparentUpgradeableProxy internal proxy;
    ProxyAdmin internal admin;

    RouteImplementationV1 internal first;
    RouteImplementationV2 internal second;
    RouteImplementationV3 internal candidate;

    function setUp() public {
        proposer = makeAddr("comparison-proposer");
        executor = makeAddr("comparison-executor");

        first = new RouteImplementationV1();
        second = new RouteImplementationV2();
        candidate = new RouteImplementationV3();

        address[] memory proposers = new address[](1);
        proposers[0] = proposer;

        address[] memory executors = new address[](1);
        executors[0] = executor;

        controller = new TimelockController(DELAY, proposers, executors, address(0));

        // OZ 5.x creates ProxyAdmin internally.
        proxy = new TransparentUpgradeableProxy(address(first), address(controller), bytes(""));

        address adminAddress = address(uint160(uint256(vm.load(address(proxy), ERC1967_ADMIN_SLOT))));

        admin = ProxyAdmin(adminAddress);

        assertTrue(address(admin).code.length > 0);
        assertEq(admin.owner(), address(controller));

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(first)));
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _spec(address implementation, bytes32 salt) internal view returns (TimelockScenario memory) {
        return TimelockScenario({
            timelock: address(controller),
            proposer: proposer,
            executor: executor,
            proxyAdmin: address(admin),
            proxy: address(proxy),
            candidate: implementation,
            predecessor: bytes32(0),
            salt: salt,
            property: TimelockProperty.READY_UPGRADE_SUCCEEDS
        });
    }

    function _schedule(TimelockScenario memory spec) internal {
        vm.prank(proposer, proposer);

        controller.schedule(spec.proxyAdmin, 0, _timelockUpgradePayload(spec), spec.predecessor, spec.salt, DELAY);

        assertTrue(controller.isOperationPending(_timelockOperationId(spec)));
    }

    function _warpToReady(TimelockScenario memory spec) internal {
        uint256 readyAt = controller.getTimestamp(_timelockOperationId(spec));

        vm.warp(readyAt);

        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));
    }

    function _installVersion(address implementation) internal {
        // A separate authorized operation changes the real version.
        TimelockScenario memory installation = _spec(implementation, keccak256("install-v2-operation"));

        _schedule(installation);
        _warpToReady(installation);

        vm.prank(executor, executor);

        controller.execute(
            installation.proxyAdmin,
            0,
            _timelockUpgradePayload(installation),
            installation.predecessor,
            installation.salt
        );

        assertTrue(controller.isOperationDone(_timelockOperationId(installation)));

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(implementation));

        assertEq(admin.owner(), address(controller));
    }

    function _capture(TimelockScenario memory spec, address expectedImplementation)
        internal
        returns (RoutedStage memory)
    {
        bytes32 active = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        assertEq(active, _word(expectedImplementation));

        bytes32 operationId = _timelockOperationId(spec);

        assertTrue(controller.isOperationReady(operationId));
        assertFalse(controller.isOperationDone(operationId));

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertTrue(obs.outerSuccess);
        assertTrue(obs.operationDoneAfter);

        assertEq(obs.implementationBefore, active);

        assertEq(obs.implementationAfter, _word(spec.candidate));

        RoutedEvaluation memory evaluation = _evaluateTimelockRoute(spec, obs);

        assertEq(uint256(evaluation.status), uint256(PolicyStatus.PASS));

        // The isolated probe must restore the active version.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), active);

        assertTrue(controller.isOperationReady(operationId));
        assertFalse(controller.isOperationDone(operationId));

        return RoutedStage({expectedActiveImplementation: expectedImplementation, observation: obs});
    }

    function test_RealRouteStillSatisfiedAcrossVersions() public {
        TimelockScenario memory spec = _spec(address(candidate), keccak256("shared-comparison-operation"));

        // Prepare exactly one common operation for both stages.
        _schedule(spec);
        _warpToReady(spec);

        RoutedStage memory beforeStage = _capture(spec, address(first));

        // Upgrade via a different legitimate Timelock operation.
        _installVersion(address(second));

        assertEq(RouteImplementationV2(address(proxy)).version(), 2);

        // The shared probe operation remains ready and unused.
        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));

        RoutedStage memory afterStage = _capture(spec, address(second));

        // Time advanced during installation, but governance
        // permissions and operation identity remained unchanged.
        assertGt(afterStage.observation.observedTimestamp, beforeStage.observation.observedTimestamp);

        assertEq(beforeStage.observation.operationId, afterStage.observation.operationId);

        assertEq(beforeStage.observation.readyAt, afterStage.observation.readyAt);

        assertEq(beforeStage.observation.executorHasRole, afterStage.observation.executorHasRole);

        assertEq(beforeStage.observation.openExecutorRole, afterStage.observation.openExecutorRole);

        bytes32 scenarioId = keccak256("real-route-comparison");

        RoutedComparisonResult memory result = _compareTimelockRoute(scenarioId, spec, beforeStage, afterStage);

        assertEq(result.scenarioKey, _routedScenarioKey(scenarioId, spec));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.NONE));

        // Neither observation consumed the shared operation.
        assertTrue(controller.isOperationReady(_timelockOperationId(spec)));

        assertFalse(controller.isOperationDone(_timelockOperationId(spec)));

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(second)));
    }

    function test_RealRouteSameImplementationIncomparable() public {
        TimelockScenario memory spec = _spec(address(candidate), keccak256("same-stage-operation"));

        _schedule(spec);
        _warpToReady(spec);

        RoutedStage memory firstCapture = _capture(spec, address(first));

        RoutedStage memory secondCapture = _capture(spec, address(first));

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("same-stage-test"), spec, firstCapture, secondCapture);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.SAME_IMPLEMENTATION_STAGE));
    }
}

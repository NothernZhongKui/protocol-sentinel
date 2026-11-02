// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "protocol-sentinel/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract ConsumerVersionOne {
    function version() external pure returns (uint256) {
        return 1;
    }
}

contract ConsumerVersionTwo {
    function version() external pure returns (uint256) {
        return 2;
    }
}

contract ConsumerVersionThree {
    function version() external pure returns (uint256) {
        return 3;
    }
}

/// @notice External integration of the v0.4-B Timelock adapter.
/// @dev Imports the library as an independent Foundry dependency.
contract SentinelTimelockConsumerTest is TimelockAuthorityProbe {
    uint256 internal constant DELAY = 48 hours;

    address internal proposer;
    address internal executor;

    TimelockController internal timelock;
    TransparentUpgradeableProxy internal proxy;
    ProxyAdmin internal admin;

    ConsumerVersionOne internal v1;
    ConsumerVersionTwo internal v2;
    ConsumerVersionThree internal v3;

    function setUp() public {
        proposer = makeAddr("consumer-proposer");
        executor = makeAddr("consumer-executor");

        v1 = new ConsumerVersionOne();
        v2 = new ConsumerVersionTwo();
        v3 = new ConsumerVersionThree();

        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);

        proposers[0] = proposer;
        executors[0] = executor;

        timelock = new TimelockController(DELAY, proposers, executors, address(0));

        // OZ 5.x deploys an internal ProxyAdmin.
        // The second argument is its initial owner.
        proxy = new TransparentUpgradeableProxy(address(v1), address(timelock), bytes(""));

        address adminAddress = address(uint160(uint256(vm.load(address(proxy), ERC1967_ADMIN_SLOT))));

        admin = ProxyAdmin(adminAddress);

        assertEq(admin.owner(), address(timelock));
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _scenario(address implementation, bytes32 salt, TimelockProperty property)
        internal
        view
        returns (TimelockScenario memory)
    {
        return TimelockScenario({
            timelock: address(timelock),
            proposer: proposer,
            executor: executor,
            proxyAdmin: address(admin),
            proxy: address(proxy),
            candidate: implementation,
            predecessor: bytes32(0),
            salt: salt,
            property: property
        });
    }

    function _schedule(TimelockScenario memory spec) internal {
        vm.prank(proposer, proposer);

        timelock.schedule(spec.proxyAdmin, 0, _timelockUpgradePayload(spec), spec.predecessor, spec.salt, DELAY);

        assertTrue(timelock.isOperationPending(_timelockOperationId(spec)));
    }

    function _makeReady(TimelockScenario memory spec) internal {
        vm.warp(timelock.getTimestamp(_timelockOperationId(spec)));
    }

    function _assertPass(TimelockScenario memory spec, RoutedObservation memory obs) internal pure {
        RoutedEvaluation memory result = _evaluateTimelockRoute(spec, obs);

        assertEq(uint256(result.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.reason), uint256(RoutedReason.NONE));
    }

    function test_ConsumerWaitingRejectsEarlyExecution() public {
        TimelockScenario memory spec =
            _scenario(address(v3), keccak256("consumer-waiting"), TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        _schedule(spec);

        bytes32 beforeImplementation = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertFalse(obs.outerSuccess);
        assertFalse(obs.operationDoneAfter);

        _assertPass(spec, obs);

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), beforeImplementation);

        assertTrue(timelock.isOperationPending(_timelockOperationId(spec)));
    }

    function test_ConsumerReadyUpgradeAndRestoration() public {
        TimelockScenario memory spec =
            _scenario(address(v3), keccak256("consumer-ready"), TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _schedule(spec);
        _makeReady(spec);

        RoutedObservation memory obs = _observeIsolatedTimelockRoute(spec);

        assertTrue(obs.outerSuccess);
        assertTrue(obs.operationDoneAfter);

        assertEq(obs.implementationAfter, _word(address(v3)));

        _assertPass(spec, obs);

        // The observer restored the state of the test fixture.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(v1)));

        assertTrue(timelock.isOperationReady(_timelockOperationId(spec)));

        assertFalse(timelock.isOperationDone(_timelockOperationId(spec)));
    }

    function test_ConsumerComparativeUpgradeRoute() public {
        TimelockScenario memory shared =
            _scenario(address(v3), keccak256("consumer-shared-operation"), TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _schedule(shared);
        _makeReady(shared);

        RoutedObservation memory beforeObs = _observeIsolatedTimelockRoute(shared);

        _assertPass(shared, beforeObs);

        // An independent scheduled upgrade installs V2.
        TimelockScenario memory installation =
            _scenario(address(v2), keccak256("consumer-install-v2"), TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _schedule(installation);
        _makeReady(installation);

        vm.prank(executor, executor);

        timelock.execute(
            installation.proxyAdmin,
            0,
            _timelockUpgradePayload(installation),
            installation.predecessor,
            installation.salt
        );

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(v2)));

        assertTrue(timelock.isOperationDone(_timelockOperationId(installation)));

        // Shared operation was never consumed.
        assertTrue(timelock.isOperationReady(_timelockOperationId(shared)));

        RoutedObservation memory afterObs = _observeIsolatedTimelockRoute(shared);

        _assertPass(shared, afterObs);

        RoutedStage memory beforeStage =
            RoutedStage({expectedActiveImplementation: address(v1), observation: beforeObs});

        RoutedStage memory afterStage = RoutedStage({expectedActiveImplementation: address(v2), observation: afterObs});

        RoutedComparisonResult memory comparison =
            _compareTimelockRoute(keccak256("external-consumer-comparison"), shared, beforeStage, afterStage);

        assertEq(uint256(comparison.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(comparison.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(comparison.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));

        assertEq(uint256(comparison.reason), uint256(RoutedComparisonReason.NONE));

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(v2)));

        assertFalse(timelock.isOperationDone(_timelockOperationId(shared)));
    }
}

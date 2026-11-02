// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

contract TimelockAuthorityComparisonTest is TimelockAuthorityProbe {
    address internal constant OLD_IMPL = address(0x3001);
    address internal constant NEW_IMPL = address(0x3002);
    address internal constant CANDIDATE = address(0x3003);

    function _spec(TimelockProperty property) internal pure returns (TimelockScenario memory) {
        return TimelockScenario({
            timelock: address(0x1001),
            proposer: address(0x1002),
            executor: address(0x1003),
            proxyAdmin: address(0x2001),
            proxy: address(0x2002),
            candidate: CANDIDATE,
            predecessor: bytes32(0),
            salt: keccak256("comparative-timelock"),
            property: property
        });
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _stage(TimelockScenario memory spec, address active, bool succeeds)
        internal
        pure
        returns (RoutedStage memory stage)
    {
        bool ready = spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS;

        RoutedObservation memory obs;

        obs.executor = spec.executor;
        obs.txOrigin = spec.executor;
        obs.executorEOAObserved = true;
        obs.executorEOAValid = true;
        obs.outerTarget = spec.timelock;
        obs.outerCallData = _timelockExecutePayload(spec);

        obs.timelock = spec.timelock;
        obs.proxyAdmin = spec.proxyAdmin;
        obs.operationId = _timelockOperationId(spec);

        obs.operationStateBeforeObserved = true;
        obs.operationStateBefore =
            ready ? TimelockController.OperationState.Ready : TimelockController.OperationState.Waiting;

        obs.operationDoneBefore = false;
        obs.operationDoneAfter = succeeds;

        obs.predecessor = spec.predecessor;
        obs.predecessorStateObserved = true;
        obs.predecessorDoneBefore = true;

        obs.observedTimestamp = 1000;
        obs.readyAt = ready ? 1000 : 1100;

        obs.outerSuccess = succeeds;

        obs.observedSlot = ERC1967_IMPL_SLOT;
        obs.implementationBefore = _word(active);
        obs.implementationAfter = succeeds ? _word(CANDIDATE) : _word(active);

        obs.proxyCodeObserved = true;
        obs.proxyHasCode = true;
        obs.candidateCodeObserved = true;
        obs.candidateHasCode = true;
        obs.proxyAdminOwnershipObserved = true;
        obs.proxyAdminOwnedByTimelock = true;

        obs.executorRolesObserved = true;
        obs.executorHasRole = true;
        obs.openExecutorRole = false;

        if (!succeeds) {
            if (ready) {
                obs.returnData = hex"deadbeef";
            } else {
                obs.returnData = abi.encodeWithSelector(
                    TimelockController.TimelockUnexpectedOperationState.selector, obs.operationId, bytes32(uint256(4))
                );
            }
        }

        stage = RoutedStage({expectedActiveImplementation: active, observation: obs});
    }

    function _assertVerdict(
        RoutedComparisonResult memory result,
        PolicyStatus beforeStatus,
        PolicyStatus afterStatus,
        ComparisonVerdict verdict
    ) internal pure {
        assertEq(uint256(result.beforeEvaluation.status), uint256(beforeStatus));
        assertEq(uint256(result.afterEvaluation.status), uint256(afterStatus));
        assertEq(uint256(result.verdict), uint256(verdict));
        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.NONE));
    }

    function test_ReadyStillSatisfied() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("ready-positive"), spec, _stage(spec, OLD_IMPL, true), _stage(spec, NEW_IMPL, true)
        );

        _assertVerdict(result, PolicyStatus.PASS, PolicyStatus.PASS, ComparisonVerdict.STILL_SATISFIED);
    }

    function test_WaitingStillSatisfied() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("waiting-negative"), spec, _stage(spec, OLD_IMPL, false), _stage(spec, NEW_IMPL, false)
        );

        _assertVerdict(result, PolicyStatus.PASS, PolicyStatus.PASS, ComparisonVerdict.STILL_SATISFIED);
    }

    // Deliberately synthetic outcome transition.
    // This tests classification, not a proven OZ vulnerability.
    function test_ReadyChangedToViolation() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("synthetic-violation"), spec, _stage(spec, OLD_IMPL, true), _stage(spec, NEW_IMPL, false)
        );

        _assertVerdict(result, PolicyStatus.PASS, PolicyStatus.FAIL, ComparisonVerdict.CHANGED_TO_VIOLATION);
    }

    function test_ReadyChangedToSatisfied() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("synthetic-restoration"), spec, _stage(spec, OLD_IMPL, false), _stage(spec, NEW_IMPL, true)
        );

        _assertVerdict(result, PolicyStatus.FAIL, PolicyStatus.PASS, ComparisonVerdict.CHANGED_TO_SATISFIED);
    }

    function test_ReadyStillViolated() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("synthetic-both-fail"), spec, _stage(spec, OLD_IMPL, false), _stage(spec, NEW_IMPL, false)
        );

        _assertVerdict(result, PolicyStatus.FAIL, PolicyStatus.FAIL, ComparisonVerdict.STILL_VIOLATED);
    }

    function test_ScenarioMismatchIsIncomparable() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        afterStage.observation.outerCallData = hex"deadbeef";

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("wrong-calldata"), spec, beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.SCENARIO_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));
    }

    function test_StageMismatchPreservesEvaluations() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, false);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        beforeStage.expectedActiveImplementation = CANDIDATE;

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("wrong-stage-binding"), spec, beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.STAGE_BINDING_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function test_SameImplementationIsIncomparable() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedComparisonResult memory result = _compareTimelockRoute(
            keccak256("same-implementation"), spec, _stage(spec, OLD_IMPL, true), _stage(spec, OLD_IMPL, true)
        );

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.SAME_IMPLEMENTATION_STAGE));
    }

    function test_GovernanceRoleDriftIsIncomparable() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        // Both remain eligible, but the configuration differs.
        afterStage.observation.openExecutorRole = true;

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("governance-drift"), spec, beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.PREPARATION_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function test_UnknownEvidenceIsIndeterminate() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        afterStage.observation.executorRolesObserved = false;

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("missing-role-evidence"), spec, beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.INDETERMINATE_POLICY));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));
    }

    function test_UpperStorageBitsDoNotChangeIdentity() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        beforeStage.observation.implementationBefore |= bytes32(uint256(1) << 200);

        afterStage.observation.implementationBefore |= bytes32(uint256(1) << 201);

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("upper-bits"), spec, beforeStage, afterStage);

        _assertVerdict(result, PolicyStatus.PASS, PolicyStatus.PASS, ComparisonVerdict.STILL_SATISFIED);
    }

    function test_ScenarioKeyBindsRouteIdentity() public pure {
        TimelockScenario memory original = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        bytes32 scenarioId = keccak256("identity");
        bytes32 originalKey = _routedScenarioKey(scenarioId, original);

        TimelockScenario memory changed = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        changed.proposer = address(0x9999);

        assertTrue(_routedScenarioKey(scenarioId, changed) != originalKey);

        changed = _spec(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        assertTrue(_routedScenarioKey(scenarioId, changed) != originalKey);

        changed = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        changed.predecessor = keccak256("other-dependency");

        assertTrue(_routedScenarioKey(scenarioId, changed) != originalKey);

        changed = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        changed.timelock = address(0x9998);

        assertTrue(_routedScenarioKey(scenarioId, changed) != originalKey);

        assertEq(originalKey, _routedScenarioKey(scenarioId, original));
    }

    function test_RescheduledOperationIsIncomparable() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        // Same operation ID, but different scheduling evidence.
        afterStage.observation.readyAt += 100;
        afterStage.observation.observedTimestamp = afterStage.observation.readyAt;

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("rescheduled-operation"), spec, beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.PREPARATION_MISMATCH));
    }

    function test_LaterTimestampSameScheduleIsComparable() public pure {
        TimelockScenario memory spec = _spec(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedStage memory beforeStage = _stage(spec, OLD_IMPL, true);

        RoutedStage memory afterStage = _stage(spec, NEW_IMPL, true);

        // Later execution time is acceptable:
        // the original operation readiness is unchanged.
        afterStage.observation.observedTimestamp += 1 days;

        RoutedComparisonResult memory result =
            _compareTimelockRoute(keccak256("later-observation"), spec, beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));
    }
}

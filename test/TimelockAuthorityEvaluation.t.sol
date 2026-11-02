// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

contract TimelockAuthorityEvaluationTest is TimelockAuthorityProbe {
    address internal constant EXECUTOR = address(0x1003);
    address internal constant TIMELOCK = address(0x1001);
    address internal constant ADMIN = address(0x2001);
    address internal constant PROXY = address(0x2002);
    address internal constant CANDIDATE = address(0x2003);
    address internal constant CURRENT = address(0x3001);

    function _scenario(TimelockProperty property) internal pure returns (TimelockScenario memory) {
        return TimelockScenario({
            timelock: TIMELOCK,
            proposer: address(0x1002),
            executor: EXECUTOR,
            proxyAdmin: ADMIN,
            proxy: PROXY,
            candidate: CANDIDATE,
            predecessor: bytes32(0),
            salt: keccak256("evaluation-scenario"),
            property: property
        });
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _observation(TimelockScenario memory spec) internal pure returns (RoutedObservation memory obs) {
        bool ready = spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS;

        obs.executor = EXECUTOR;
        obs.txOrigin = EXECUTOR;
        obs.executorEOAObserved = true;
        obs.executorEOAValid = true;
        obs.outerTarget = TIMELOCK;
        obs.outerCallData = _timelockExecutePayload(spec);

        obs.outerSuccess = ready;

        obs.timelock = TIMELOCK;
        obs.proxyAdmin = ADMIN;
        obs.operationId = _timelockOperationId(spec);

        obs.operationStateBeforeObserved = true;
        obs.operationStateBefore =
            ready ? TimelockController.OperationState.Ready : TimelockController.OperationState.Waiting;

        obs.operationDoneBefore = false;
        obs.operationDoneAfter = ready;

        obs.predecessor = spec.predecessor;
        obs.predecessorStateObserved = true;
        obs.predecessorDoneBefore = true;

        obs.observedTimestamp = 1000;
        obs.readyAt = ready ? 1000 : 1100;

        obs.observedSlot = ERC1967_IMPL_SLOT;
        obs.implementationBefore = _word(CURRENT);
        obs.implementationAfter = ready ? _word(CANDIDATE) : _word(CURRENT);

        obs.proxyCodeObserved = true;
        obs.proxyHasCode = true;
        obs.candidateCodeObserved = true;
        obs.candidateHasCode = true;
        obs.proxyAdminOwnershipObserved = true;
        obs.proxyAdminOwnedByTimelock = true;

        obs.executorRolesObserved = true;
        obs.executorHasRole = true;
        obs.openExecutorRole = false;

        if (!ready) {
            obs.returnData = abi.encodeWithSelector(
                TimelockController.TimelockUnexpectedOperationState.selector, obs.operationId, bytes32(uint256(4))
            );
        }
    }

    function evaluateExternal(TimelockScenario memory spec, RoutedObservation memory obs)
        external
        pure
        returns (RoutedEvaluation memory)
    {
        return _evaluateTimelockRoute(spec, obs);
    }

    function _assertStatus(RoutedEvaluation memory result, PolicyStatus expectedStatus, RoutedReason expectedReason)
        internal
        pure
    {
        assertEq(uint256(result.status), uint256(expectedStatus));

        assertEq(uint256(result.reason), uint256(expectedReason));
    }

    function test_ReadySuccessPass() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        _assertStatus(_evaluateTimelockRoute(spec, _observation(spec)), PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_ReadyRevertedExecutionFails() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.outerSuccess = false;
        obs.operationDoneAfter = false;
        obs.implementationAfter = obs.implementationBefore;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.FAIL, RoutedReason.EXECUTION_REJECTED);
    }

    function test_ReadyOuterSuccessWithoutEffectFails() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.implementationAfter = obs.implementationBefore;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.FAIL, RoutedReason.MISSING_UPGRADE_EFFECT);
    }

    function test_ReadyUnfinishedPredecessorIsPreparationError() public {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        spec.predecessor = keccak256("unfinished");

        RoutedObservation memory obs = _observation(spec);
        obs.predecessorDoneBefore = false;

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.UNFINISHED_PREDECESSOR)
        );

        this.evaluateExternal(spec, obs);
    }

    function test_UnknownPredecessorEvidenceIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        spec.predecessor = keccak256("unknown");

        RoutedObservation memory obs = _observation(spec);
        obs.predecessorStateObserved = false;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCOMPLETE_EVIDENCE);
    }

    function test_WaitingExactRevertPass() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        _assertStatus(_evaluateTimelockRoute(spec, _observation(spec)), PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_WaitingIneligibleExecutorCannotPass() public {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);
        obs.executorHasRole = false;
        obs.openExecutorRole = false;

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.INELIGIBLE_EXECUTOR)
        );

        this.evaluateExternal(spec, obs);
    }

    function test_WaitingRoleRevertDoesNotProveDelay() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);
        obs.returnData = abi.encodeWithSignature(
            "AccessControlUnauthorizedAccount(address,bytes32)", EXECUTOR, keccak256("EXECUTOR_ROLE")
        );

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.UNEXPECTED_REVERT);
    }

    function test_WaitingWrongReadyBitmapIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);

        obs.returnData = abi.encodeWithSelector(
            TimelockController.TimelockUnexpectedOperationState.selector, obs.operationId, bytes32(uint256(2))
        );

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.UNEXPECTED_REVERT);
    }

    function test_WaitingWrongOperationIdInRevertIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);

        obs.returnData = abi.encodeWithSelector(
            TimelockController.TimelockUnexpectedOperationState.selector,
            keccak256("wrong-operation"),
            bytes32(uint256(4))
        );

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.UNEXPECTED_REVERT);
    }

    function test_OpenExecutorRoleAccepted() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);
        obs.executorHasRole = false;
        obs.openExecutorRole = true;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_ExactReadinessTimestampIsReady() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);

        assertEq(obs.observedTimestamp, obs.readyAt);

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.PASS, RoutedReason.NONE);
    }

    function test_WaitingAtReadinessTimestampIsInconsistent() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);
        obs.readyAt = obs.observedTimestamp;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_TIMING);
    }

    function test_RevertedCallWithChangedImplementationIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.NOT_READY_EXECUTION_REJECTED);

        RoutedObservation memory obs = _observation(spec);
        obs.implementationAfter = _word(CANDIDATE);

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
    }

    function test_MissingOwnershipEvidenceIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.proxyAdminOwnershipObserved = false;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCOMPLETE_EVIDENCE);
    }

    function test_OperationIdMismatchIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.operationId = keccak256("other-operation");

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.CONTEXT_MISMATCH);
    }

    function test_SuccessWithoutOperationDoneIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.operationDoneAfter = false;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
    }

    function test_ReadyNonemptyOuterReturnDataIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);

        // Pinned TimelockController.execute() returns no value.
        obs.returnData = hex"deadbeef";

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
    }

    function test_MissingEOAEvidenceIsUnknown() public pure {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.executorEOAObserved = false;

        _assertStatus(_evaluateTimelockRoute(spec, obs), PolicyStatus.UNKNOWN, RoutedReason.INCOMPLETE_EVIDENCE);
    }

    function test_InvalidEOAEvidenceIsPreparationError() public {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        RoutedObservation memory obs = _observation(spec);
        obs.executorEOAValid = false;

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.INVALID_EOA_EXECUTOR)
        );

        this.evaluateExternal(spec, obs);
    }

    function test_ZeroExecutorCannotUseForgedEOAEvidence() public {
        TimelockScenario memory spec = _scenario(TimelockProperty.READY_UPGRADE_SUCCEEDS);

        spec.executor = address(0);

        RoutedObservation memory obs = _observation(spec);

        obs.executor = address(0);
        obs.txOrigin = address(0);

        // Even a claimed valid EOA cannot justify address(0).
        obs.executorEOAObserved = true;
        obs.executorEOAValid = true;

        vm.expectRevert(
            abi.encodeWithSelector(InvalidTimelockPreparation.selector, PreparationFailure.INVALID_EOA_EXECUTOR)
        );

        this.evaluateExternal(spec, obs);
    }
}

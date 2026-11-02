// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityIntegrationTest} from "./TimelockAuthorityIntegration.t.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

contract TimelockComparisonEvidenceCaptureTest is TimelockAuthorityIntegrationTest {
    function _captureStatusName(PolicyStatus value) internal pure returns (string memory) {
        if (value == PolicyStatus.PASS) return "PASS";
        if (value == PolicyStatus.FAIL) return "FAIL";
        if (value == PolicyStatus.UNKNOWN) return "UNKNOWN";
        if (value == PolicyStatus.ERROR) return "ERROR";
        revert("Unknown policy status");
    }

    function _captureRoutedReasonName(RoutedReason value) internal pure returns (string memory) {
        if (value == RoutedReason.NONE) return "NONE";
        if (value == RoutedReason.CONTEXT_MISMATCH) return "CONTEXT_MISMATCH";
        if (value == RoutedReason.INCOMPLETE_EVIDENCE) return "INCOMPLETE_EVIDENCE";
        if (value == RoutedReason.INCONSISTENT_TIMING) return "INCONSISTENT_TIMING";
        if (value == RoutedReason.INCONSISTENT_EXECUTION) return "INCONSISTENT_EXECUTION";
        if (value == RoutedReason.UNEXPECTED_REVERT) return "UNEXPECTED_REVERT";
        if (value == RoutedReason.EXECUTION_REJECTED) return "EXECUTION_REJECTED";
        if (value == RoutedReason.MISSING_UPGRADE_EFFECT) return "MISSING_UPGRADE_EFFECT";
        revert("Unknown routed reason");
    }

    function _captureVerdictName(ComparisonVerdict value) internal pure returns (string memory) {
        if (value == ComparisonVerdict.STILL_SATISFIED) return "STILL_SATISFIED";
        if (value == ComparisonVerdict.CHANGED_TO_VIOLATION) return "CHANGED_TO_VIOLATION";
        if (value == ComparisonVerdict.CHANGED_TO_SATISFIED) return "CHANGED_TO_SATISFIED";
        if (value == ComparisonVerdict.STILL_VIOLATED) return "STILL_VIOLATED";
        if (value == ComparisonVerdict.INDETERMINATE) return "INDETERMINATE";
        if (value == ComparisonVerdict.INCOMPARABLE) return "INCOMPARABLE";
        revert("Unknown comparison verdict");
    }

    function _captureComparisonReasonName(RoutedComparisonReason value) internal pure returns (string memory) {
        if (value == RoutedComparisonReason.NONE) return "NONE";
        if (value == RoutedComparisonReason.SCENARIO_MISMATCH) return "SCENARIO_MISMATCH";
        if (value == RoutedComparisonReason.STAGE_BINDING_MISMATCH) return "STAGE_BINDING_MISMATCH";
        if (value == RoutedComparisonReason.SAME_IMPLEMENTATION_STAGE) return "SAME_IMPLEMENTATION_STAGE";
        if (value == RoutedComparisonReason.PREPARATION_MISMATCH) return "PREPARATION_MISMATCH";
        if (value == RoutedComparisonReason.INDETERMINATE_POLICY) return "INDETERMINATE_POLICY";
        revert("Unknown comparison reason");
    }

    function _capturePropertyName(TimelockProperty value) internal pure returns (string memory) {
        if (value == TimelockProperty.READY_UPGRADE_SUCCEEDS) return "READY_UPGRADE_SUCCEEDS";
        if (value == TimelockProperty.NOT_READY_EXECUTION_REJECTED) return "NOT_READY_EXECUTION_REJECTED";
        revert("Unknown Timelock property");
    }

    function _captureOperationStateName(TimelockController.OperationState value) internal pure returns (string memory) {
        if (value == TimelockController.OperationState.Unset) return "Unset";
        if (value == TimelockController.OperationState.Waiting) return "Waiting";
        if (value == TimelockController.OperationState.Ready) return "Ready";
        if (value == TimelockController.OperationState.Done) return "Done";
        revert("Unknown operation state");
    }

    function _serializeCaptureStage(
        string memory key,
        string memory prefix,
        RoutedStage memory stage,
        RoutedEvaluation memory evaluation
    ) internal {
        RoutedObservation memory obs = stage.observation;

        vm.serializeAddress(
            key, string.concat(prefix, "_expectedActiveImplementation"), stage.expectedActiveImplementation
        );
        vm.serializeAddress(key, string.concat(prefix, "_executor"), obs.executor);
        vm.serializeAddress(key, string.concat(prefix, "_txOrigin"), obs.txOrigin);
        vm.serializeBool(key, string.concat(prefix, "_executorEOAObserved"), obs.executorEOAObserved);
        vm.serializeBool(key, string.concat(prefix, "_executorEOAValid"), obs.executorEOAValid);
        vm.serializeAddress(key, string.concat(prefix, "_outerTarget"), obs.outerTarget);
        vm.serializeBytes(key, string.concat(prefix, "_outerCallData"), obs.outerCallData);
        vm.serializeBool(key, string.concat(prefix, "_outerSuccess"), obs.outerSuccess);
        vm.serializeBytes(key, string.concat(prefix, "_returnData"), obs.returnData);
        vm.serializeAddress(key, string.concat(prefix, "_timelock"), obs.timelock);
        vm.serializeAddress(key, string.concat(prefix, "_proxyAdmin"), obs.proxyAdmin);
        vm.serializeBytes32(key, string.concat(prefix, "_operationId"), obs.operationId);
        vm.serializeString(
            key, string.concat(prefix, "_operationStateBefore"), _captureOperationStateName(obs.operationStateBefore)
        );
        vm.serializeBool(key, string.concat(prefix, "_operationStateBeforeObserved"), obs.operationStateBeforeObserved);
        vm.serializeBool(key, string.concat(prefix, "_operationDoneBefore"), obs.operationDoneBefore);
        vm.serializeBool(key, string.concat(prefix, "_operationDoneAfter"), obs.operationDoneAfter);
        vm.serializeBytes32(key, string.concat(prefix, "_predecessor"), obs.predecessor);
        vm.serializeBool(key, string.concat(prefix, "_predecessorStateObserved"), obs.predecessorStateObserved);
        vm.serializeBool(key, string.concat(prefix, "_predecessorDoneBefore"), obs.predecessorDoneBefore);
        vm.serializeString(key, string.concat(prefix, "_observedTimestamp"), vm.toString(obs.observedTimestamp));
        vm.serializeString(key, string.concat(prefix, "_readyAt"), vm.toString(obs.readyAt));
        vm.serializeBytes32(key, string.concat(prefix, "_observedSlot"), obs.observedSlot);
        vm.serializeBytes32(key, string.concat(prefix, "_implementationBefore"), obs.implementationBefore);
        vm.serializeBytes32(key, string.concat(prefix, "_implementationAfter"), obs.implementationAfter);
        vm.serializeBool(key, string.concat(prefix, "_proxyCodeObserved"), obs.proxyCodeObserved);
        vm.serializeBool(key, string.concat(prefix, "_proxyHasCode"), obs.proxyHasCode);
        vm.serializeBool(key, string.concat(prefix, "_candidateCodeObserved"), obs.candidateCodeObserved);
        vm.serializeBool(key, string.concat(prefix, "_candidateHasCode"), obs.candidateHasCode);
        vm.serializeBool(key, string.concat(prefix, "_proxyAdminOwnershipObserved"), obs.proxyAdminOwnershipObserved);
        vm.serializeBool(key, string.concat(prefix, "_proxyAdminOwnedByTimelock"), obs.proxyAdminOwnedByTimelock);
        vm.serializeBool(key, string.concat(prefix, "_executorRolesObserved"), obs.executorRolesObserved);
        vm.serializeBool(key, string.concat(prefix, "_executorHasRole"), obs.executorHasRole);
        vm.serializeBool(key, string.concat(prefix, "_openExecutorRole"), obs.openExecutorRole);

        vm.serializeString(key, string.concat(prefix, "_status"), _captureStatusName(evaluation.status));

        vm.serializeString(key, string.concat(prefix, "_reason"), _captureRoutedReasonName(evaluation.reason));
    }

    function test_CaptureRealTimelockComparison() public {
        TimelockScenario memory spec = _spec(address(candidate), keccak256("c3-shared-operation"));

        // Schedule one real OZ operation shared by both stages.
        _schedule(spec);
        _warpToReady(spec);

        RoutedStage memory beforeStage = _capture(spec, address(first));

        // A separate legitimate Timelock operation installs V2.
        _installVersion(address(second));

        RoutedStage memory afterStage = _capture(spec, address(second));

        bytes32 scenarioId = keccak256("sentinel-c3-real-timelock-comparison");

        RoutedComparisonResult memory result = _compareTimelockRoute(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.NONE));

        assertEq(beforeStage.observation.operationId, afterStage.observation.operationId);

        assertEq(beforeStage.observation.readyAt, afterStage.observation.readyAt);

        assertTrue(afterStage.observation.observedTimestamp >= beforeStage.observation.observedTimestamp);

        // Normal forge test runs never write evidence.
        if (!vm.envOr("EXPORT_ROUTED_CAPTURE", false)) return;

        string memory key = "sentinel_c3_routed_raw";

        vm.serializeString(key, "format", "protocol-sentinel-routed-capture-v1");

        vm.serializeString(key, "chain_id", vm.toString(block.chainid));

        vm.serializeBytes32(key, "scenario_id", scenarioId);

        vm.serializeAddress(key, "timelock", spec.timelock);
        vm.serializeAddress(key, "proposer", spec.proposer);
        vm.serializeAddress(key, "executor", spec.executor);
        vm.serializeAddress(key, "proxy_admin", spec.proxyAdmin);
        vm.serializeAddress(key, "proxy", spec.proxy);
        vm.serializeAddress(key, "candidate", spec.candidate);

        vm.serializeBytes32(key, "predecessor", spec.predecessor);
        vm.serializeBytes32(key, "salt", spec.salt);

        vm.serializeString(key, "property", _capturePropertyName(spec.property));

        vm.serializeBytes(key, "inner_calldata", _timelockUpgradePayload(spec));

        vm.serializeBytes(key, "outer_calldata", _timelockExecutePayload(spec));

        vm.serializeBytes32(key, "operation_id", _timelockOperationId(spec));

        _serializeCaptureStage(key, "before", beforeStage, result.beforeEvaluation);

        _serializeCaptureStage(key, "after", afterStage, result.afterEvaluation);

        vm.serializeBytes32(key, "comparison_scenario_key", result.scenarioKey);

        vm.serializeString(key, "comparison_verdict", _captureVerdictName(result.verdict));

        string memory raw = vm.serializeString(key, "comparison_reason", _captureComparisonReasonName(result.reason));

        vm.writeJson(
            raw, vm.envOr("ROUTED_COMPARISON_CAPTURE_PATH", string("./artifacts/demo/timelock-comparison-capture.json"))
        );
    }

    function test_CaptureRealTimelockWaitingComparison() public {
        // Prepare a legitimate V2 installation first.
        TimelockScenario memory installation = _spec(address(second), keccak256("c3-waiting-install-v2"));

        _schedule(installation);
        _warpToReady(installation);

        assertTrue(controller.isOperationReady(_timelockOperationId(installation)));

        // Schedule the shared comparison operation only AFTER
        // the installation is already ready.
        TimelockScenario memory spec = _spec(address(candidate), keccak256("c3-shared-waiting"));

        spec.property = TimelockProperty.NOT_READY_EXECUTION_REJECTED;

        _schedule(spec);

        bytes32 operationId = _timelockOperationId(spec);
        uint256 capturedTimestamp = vm.getBlockTimestamp();
        uint256 readyAt = controller.getTimestamp(operationId);

        assertGt(readyAt, capturedTimestamp);
        assertFalse(controller.isOperationReady(operationId));

        // Before: V1, shared Timelock operation is Waiting.
        RoutedObservation memory beforeObs = _observeIsolatedTimelockRoute(spec);

        RoutedStage memory beforeStage =
            RoutedStage({expectedActiveImplementation: address(first), observation: beforeObs});

        // Execute the PREPARED V2 installation without vm.warp().
        bytes memory installationPayload = _timelockUpgradePayload(installation);

        vm.prank(executor, executor);

        controller.execute(installation.proxyAdmin, 0, installationPayload, installation.predecessor, installation.salt);

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(address(second)));

        assertEq(vm.getBlockTimestamp(), capturedTimestamp);
        assertEq(controller.getTimestamp(operationId), readyAt);

        // After: V2, same shared operation is STILL Waiting.
        RoutedObservation memory afterObs = _observeIsolatedTimelockRoute(spec);

        RoutedStage memory afterStage =
            RoutedStage({expectedActiveImplementation: address(second), observation: afterObs});

        bytes32 scenarioId = keccak256("sentinel-c3-real-waiting-comparison");

        RoutedComparisonResult memory result = _compareTimelockRoute(scenarioId, spec, beforeStage, afterStage);

        bytes memory expectedRevert = abi.encodeWithSelector(
            TimelockController.TimelockUnexpectedOperationState.selector, operationId, bytes32(uint256(4))
        );

        assertFalse(beforeObs.outerSuccess);
        assertFalse(afterObs.outerSuccess);

        assertEq(beforeObs.returnData, expectedRevert);
        assertEq(afterObs.returnData, expectedRevert);

        assertEq(uint256(beforeObs.operationStateBefore), uint256(TimelockController.OperationState.Waiting));

        assertEq(uint256(afterObs.operationStateBefore), uint256(TimelockController.OperationState.Waiting));

        assertFalse(beforeObs.operationDoneAfter);
        assertFalse(afterObs.operationDoneAfter);

        assertEq(beforeObs.readyAt, afterObs.readyAt);
        assertEq(beforeObs.observedTimestamp, afterObs.observedTimestamp);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));

        assertEq(uint256(result.reason), uint256(RoutedComparisonReason.NONE));

        // The shared operation remains unexecuted.
        assertFalse(controller.isOperationDone(operationId));
        assertFalse(controller.isOperationReady(operationId));

        if (vm.envOr("EXPORT_ROUTED_WAITING_CAPTURE", false)) {
            _writeWaitingCapture(spec, scenarioId, beforeStage, afterStage, result);
        }
    }

    function _writeWaitingCapture(
        TimelockScenario memory spec,
        bytes32 scenarioId,
        RoutedStage memory beforeStage,
        RoutedStage memory afterStage,
        RoutedComparisonResult memory result
    ) internal {
        string memory key = "sentinel_c3_waiting_raw";

        vm.serializeString(key, "format", "protocol-sentinel-routed-capture-v1");

        vm.serializeString(key, "chain_id", vm.toString(block.chainid));
        vm.serializeBytes32(key, "scenario_id", scenarioId);

        vm.serializeAddress(key, "timelock", spec.timelock);
        vm.serializeAddress(key, "proposer", spec.proposer);
        vm.serializeAddress(key, "executor", spec.executor);
        vm.serializeAddress(key, "proxy_admin", spec.proxyAdmin);
        vm.serializeAddress(key, "proxy", spec.proxy);
        vm.serializeAddress(key, "candidate", spec.candidate);

        vm.serializeBytes32(key, "predecessor", spec.predecessor);
        vm.serializeBytes32(key, "salt", spec.salt);

        vm.serializeString(key, "property", _capturePropertyName(spec.property));

        vm.serializeBytes(key, "inner_calldata", _timelockUpgradePayload(spec));

        vm.serializeBytes(key, "outer_calldata", _timelockExecutePayload(spec));

        vm.serializeBytes32(key, "operation_id", _timelockOperationId(spec));

        _serializeCaptureStage(key, "before", beforeStage, result.beforeEvaluation);

        _serializeCaptureStage(key, "after", afterStage, result.afterEvaluation);

        vm.serializeBytes32(key, "comparison_scenario_key", result.scenarioKey);

        vm.serializeString(key, "comparison_verdict", _captureVerdictName(result.verdict));

        string memory raw = vm.serializeString(key, "comparison_reason", _captureComparisonReasonName(result.reason));

        vm.writeJson(
            raw, vm.envOr("ROUTED_WAITING_CAPTURE_PATH", string("./artifacts/demo/timelock-waiting-capture.json"))
        );

        // Publication must reject evidence if its producer
        // fails after successfully writing the raw JSON.
        if (vm.envOr("ROUTED_WAITING_FAIL_AFTER_WRITE", false)) {
            revert("Sentinel: deliberate C3 post-write failure");
        }
    }
}

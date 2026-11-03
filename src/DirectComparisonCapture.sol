// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "./ComparativeAuthorityProbe.sol";

/// @notice Direct EOA observation and lossless raw capture.
/// @dev Foundry-only. This does not authenticate EVM execution.
abstract contract DirectComparisonCapture is ComparativeAuthorityProbe {
    error UnsupportedDirectActor(address actor);

    /// @notice Observe one declared stage with EOA admission.
    function _observeDirectStage(UpgradeCheck memory spec) internal returns (DirectStage memory stage) {
        if (spec.actor == address(0) || spec.actor.code.length != 0) {
            revert UnsupportedDirectActor(spec.actor);
        }

        address active = address(uint160(uint256(vm.load(spec.target, ERC1967_IMPL_SLOT))));

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", spec.candidate, bytes(""));

        Observation memory obs = _observeIsolatedCall(spec.actor, spec.target, payload, ERC1967_IMPL_SLOT);

        require(
            address(uint160(uint256(vm.load(spec.target, ERC1967_IMPL_SLOT)))) == active,
            "Sentinel: stage restoration mismatch"
        );

        stage = DirectStage({expectedActiveImplementation: active, observation: obs});
    }

    function _statusName(PolicyStatus value) internal pure returns (string memory) {
        if (value == PolicyStatus.PASS) return "PASS";
        if (value == PolicyStatus.FAIL) return "FAIL";
        if (value == PolicyStatus.UNKNOWN) return "UNKNOWN";
        if (value == PolicyStatus.ERROR) return "ERROR";
        revert("Unknown PolicyStatus");
    }

    function _reasonName(PolicyReason value) internal pure returns (string memory) {
        if (value == PolicyReason.NONE) return "NONE";
        if (value == PolicyReason.INVALID_SLOT) return "INVALID_SLOT";
        if (value == PolicyReason.CONTEXT_MISMATCH) return "CONTEXT_MISMATCH";
        if (value == PolicyReason.NON_CANONICAL_CALLDATA) return "NON_CANONICAL_CALLDATA";
        if (value == PolicyReason.INVALID_CANDIDATE) return "INVALID_CANDIDATE";
        if (value == PolicyReason.UNEXPECTED_REVERT) return "UNEXPECTED_REVERT";
        if (value == PolicyReason.SUCCESS_WITHOUT_REPLACEMENT) return "SUCCESS_WITHOUT_REPLACEMENT";
        if (value == PolicyReason.INVALID_TARGET) return "INVALID_TARGET";
        revert("Unknown PolicyReason");
    }

    function _verdictName(ComparisonVerdict value) internal pure returns (string memory) {
        if (value == ComparisonVerdict.STILL_SATISFIED) return "STILL_SATISFIED";
        if (value == ComparisonVerdict.CHANGED_TO_VIOLATION) return "CHANGED_TO_VIOLATION";
        if (value == ComparisonVerdict.CHANGED_TO_SATISFIED) return "CHANGED_TO_SATISFIED";
        if (value == ComparisonVerdict.STILL_VIOLATED) return "STILL_VIOLATED";
        if (value == ComparisonVerdict.INDETERMINATE) return "INDETERMINATE";
        if (value == ComparisonVerdict.INCOMPARABLE) return "INCOMPARABLE";
        revert("Unknown ComparisonVerdict");
    }

    function _comparisonReasonName(ComparisonReason value) internal pure returns (string memory) {
        if (value == ComparisonReason.NONE) return "NONE";
        if (value == ComparisonReason.SCENARIO_MISMATCH) return "SCENARIO_MISMATCH";
        if (value == ComparisonReason.STAGE_BINDING_MISMATCH) return "STAGE_BINDING_MISMATCH";
        if (value == ComparisonReason.SAME_IMPLEMENTATION_STAGE) return "SAME_IMPLEMENTATION_STAGE";
        if (value == ComparisonReason.INDETERMINATE_POLICY) return "INDETERMINATE_POLICY";
        revert("Unknown ComparisonReason");
    }

    function _serializeStage(
        string memory key,
        string memory prefix,
        DirectStage memory stage,
        PolicyEvaluation memory evaluation
    ) internal {
        Observation memory obs = stage.observation;

        vm.serializeAddress(
            key, string.concat(prefix, "_expectedActiveImplementation"), stage.expectedActiveImplementation
        );

        vm.serializeAddress(key, string.concat(prefix, "_actor"), obs.actor);
        vm.serializeAddress(key, string.concat(prefix, "_txOrigin"), obs.txOrigin);
        vm.serializeAddress(key, string.concat(prefix, "_target"), obs.target);

        vm.serializeBool(key, string.concat(prefix, "_success"), obs.success);
        vm.serializeBytes(key, string.concat(prefix, "_returnData"), obs.returnData);

        vm.serializeBytes32(key, string.concat(prefix, "_observedSlot"), obs.observedSlot);
        vm.serializeBytes32(key, string.concat(prefix, "_implementationBefore"), obs.implementationBefore);
        vm.serializeBytes32(key, string.concat(prefix, "_implementationAfter"), obs.implementationAfter);

        vm.serializeBytes(key, string.concat(prefix, "_callData"), obs.callData);

        vm.serializeBool(key, string.concat(prefix, "_candidateValidAtObservation"), obs.candidateValidAtObservation);

        vm.serializeBool(key, string.concat(prefix, "_targetValidAtObservation"), obs.targetValidAtObservation);

        vm.serializeString(key, string.concat(prefix, "_status"), _statusName(evaluation.status));
        vm.serializeString(key, string.concat(prefix, "_reason"), _reasonName(evaluation.reason));
    }

    function _policyName(UpgradePolicy value) internal pure returns (string memory) {
        if (value == UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT) {
            return "NO_IMPLEMENTATION_REPLACEMENT";
        }

        if (value == UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL) {
            return "NO_SUCCESSFUL_UPGRADE_CALL";
        }

        revert("Unknown UpgradePolicy");
    }

    /// @notice Export exact Solidity observations on runner request.
    /// @dev Never writes during ordinary forge test.
    function _exportDirectComparison(
        bytes32 scenarioId,
        UpgradeCheck memory spec,
        DirectStage memory beforeStage,
        DirectStage memory afterStage,
        DirectComparisonResult memory result
    ) internal {
        if (!vm.envOr("SENTINEL_EXPORT_DIRECT", false)) {
            return;
        }

        if (spec.actor == address(0) || spec.actor.code.length != 0) {
            revert UnsupportedDirectActor(spec.actor);
        }

        string memory outputPath = vm.envString("SENTINEL_DIRECT_CAPTURE_PATH");

        require(bytes(outputPath).length != 0, "Sentinel: missing capture path");

        string memory key = "sentinel_portable_direct_raw";

        vm.serializeString(key, "format", "protocol-sentinel-direct-capture-v1");
        vm.serializeString(key, "chain_id", vm.toString(block.chainid));

        vm.serializeBytes32(key, "scenario_id", scenarioId);
        vm.serializeAddress(key, "actor", spec.actor);
        vm.serializeAddress(key, "target", spec.target);
        vm.serializeAddress(key, "candidate", spec.candidate);
        vm.serializeBytes(key, "expected_revert", spec.expectedRevert);
        vm.serializeString(key, "policy", _policyName(spec.policy));

        vm.serializeBytes(
            key,
            "canonical_calldata",
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", spec.candidate, bytes(""))
        );

        _serializeStage(key, "before", beforeStage, result.beforeEvaluation);
        _serializeStage(key, "after", afterStage, result.afterEvaluation);

        vm.serializeBytes32(key, "comparison_scenario_key", result.scenarioKey);

        vm.serializeString(key, "comparison_verdict", _verdictName(result.verdict));

        string memory raw = vm.serializeString(key, "comparison_reason", _comparisonReasonName(result.reason));

        vm.writeJson(raw, outputPath);
    }
}

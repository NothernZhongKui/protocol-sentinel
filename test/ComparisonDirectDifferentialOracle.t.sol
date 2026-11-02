// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "../src/ComparativeAuthorityProbe.sol";

/// @notice Frozen Solidity oracle over an existing Evidence 1.0 input.
/// @dev Test-only: no EVM execution provenance is established.
contract ComparisonDirectDifferentialOracleTest is ComparativeAuthorityProbe {
    function _specFromJson(string memory json) internal returns (UpgradeCheck memory spec) {
        spec.actor = vm.parseJsonAddress(json, ".scenario.spec.actor");
        spec.target = vm.parseJsonAddress(json, ".scenario.spec.target");
        spec.candidate = vm.parseJsonAddress(json, ".scenario.spec.candidate");
        spec.expectedRevert = vm.parseJsonBytes(json, ".scenario.spec.expectedRevert");

        string memory name = vm.parseJsonString(json, ".scenario.spec.policy");
        bytes32 digest = keccak256(bytes(name));

        if (digest == keccak256("NO_IMPLEMENTATION_REPLACEMENT")) {
            spec.policy = UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT;
        } else if (digest == keccak256("NO_SUCCESSFUL_UPGRADE_CALL")) {
            spec.policy = UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL;
        } else {
            revert("Oracle: invalid policy");
        }
    }

    function _stageFromJson(string memory json, string memory name) internal returns (DirectStage memory stage) {
        string memory prefix = string.concat(".stages.", name);
        string memory path = string.concat(prefix, ".observation");

        stage.expectedActiveImplementation =
            vm.parseJsonAddress(json, string.concat(prefix, ".expectedActiveImplementation"));

        Observation memory obs;

        obs.actor = vm.parseJsonAddress(json, string.concat(path, ".actor"));
        obs.txOrigin = vm.parseJsonAddress(json, string.concat(path, ".txOrigin"));
        obs.target = vm.parseJsonAddress(json, string.concat(path, ".target"));
        obs.success = vm.parseJsonBool(json, string.concat(path, ".success"));
        obs.returnData = vm.parseJsonBytes(json, string.concat(path, ".returnData"));
        obs.observedSlot = vm.parseJsonBytes32(json, string.concat(path, ".observedSlot"));
        obs.implementationBefore = vm.parseJsonBytes32(json, string.concat(path, ".implementationBefore"));
        obs.implementationAfter = vm.parseJsonBytes32(json, string.concat(path, ".implementationAfter"));
        obs.callData = vm.parseJsonBytes(json, string.concat(path, ".callData"));

        obs.candidateValidAtObservation = vm.parseJsonBool(json, string.concat(path, ".candidateValidAtObservation"));

        obs.targetValidAtObservation = vm.parseJsonBool(json, string.concat(path, ".targetValidAtObservation"));

        stage.observation = obs;
    }

    function _copyStage(DirectStage memory original) internal pure returns (DirectStage memory) {
        // ABI roundtrip prevents memory aliasing between mutation cases.
        return abi.decode(abi.encode(original), (DirectStage));
    }

    function _mutate(uint256 index, DirectStage memory originalBefore, DirectStage memory originalAfter)
        internal
        pure
        returns (DirectStage memory beforeStage, DirectStage memory afterStage)
    {
        beforeStage = _copyStage(originalBefore);
        afterStage = _copyStage(originalAfter);

        if (index == 1) {
            // INVALID_SLOT precedes CONTEXT_MISMATCH.
            beforeStage.observation.observedSlot = bytes32(0);
            beforeStage.observation.actor = address(0xBEEF);
        } else if (index == 2) {
            // INVALID_TARGET precedes INVALID_CANDIDATE.
            beforeStage.observation.targetValidAtObservation = false;
            beforeStage.observation.candidateValidAtObservation = false;
        } else if (index == 3) {
            beforeStage.observation.returnData = hex"deadbeef";
        } else if (index == 4) {
            afterStage.expectedActiveImplementation = address(0xBEEF);
        } else if (index == 5) {
            // Both evaluations change; comparison detects scenario mismatch.
            beforeStage.observation.targetValidAtObservation = false;
            afterStage.observation.callData = hex"deadbeef";
        } else if (index == 6) {
            // ERC-1967 implementation address ignores the upper 96 bits.
            beforeStage.observation.implementationBefore |= bytes32(uint256(1) << 200);
            afterStage.observation.implementationBefore |= bytes32(uint256(1) << 201);
        } else if (index == 7) {
            // Both stages bind to the same active implementation.
            afterStage.expectedActiveImplementation = beforeStage.expectedActiveImplementation;
            afterStage.observation.implementationBefore = beforeStage.observation.implementationBefore;
        } else {
            require(index == 0, "Oracle: invalid mutation index");
        }
    }

    function _caseName(uint256 index) internal pure returns (string memory) {
        if (index == 0) return "baseline";
        if (index == 1) return "slot_context";
        if (index == 2) return "invalid_target";
        if (index == 3) return "wrong_revert";
        if (index == 4) return "stage_binding";
        if (index == 5) return "scenario_precedence";
        if (index == 6) return "upper_bits";
        if (index == 7) return "same_impl";
        revert("Oracle: invalid case index");
    }

    function _record(string memory key, string memory name, DirectComparisonResult memory result)
        internal
        returns (string memory)
    {
        vm.serializeUint(key, string.concat(name, "_before_status"), uint256(result.beforeEvaluation.status));

        vm.serializeUint(key, string.concat(name, "_before_reason"), uint256(result.beforeEvaluation.reason));

        vm.serializeUint(key, string.concat(name, "_after_status"), uint256(result.afterEvaluation.status));

        vm.serializeUint(key, string.concat(name, "_after_reason"), uint256(result.afterEvaluation.reason));

        vm.serializeUint(key, string.concat(name, "_verdict"), uint256(result.verdict));

        return vm.serializeUint(key, string.concat(name, "_comparison_reason"), uint256(result.reason));
    }

    function test_DirectDifferentialOracle() public {
        string memory evidencePath = vm.envOr("DIRECT_DIFFERENTIAL_EVIDENCE", string(""));

        // This oracle runs only when external evidence is supplied.
        // The regular Foundry suite must remain independently runnable.
        if (bytes(evidencePath).length == 0) {
            vm.skip(true);
        }

        string memory json = vm.readFile(evidencePath);

        UpgradeCheck memory spec = _specFromJson(json);

        bytes32 scenarioId = vm.parseJsonBytes32(json, ".scenario.scenarioId");

        DirectStage memory beforeStage = _stageFromJson(json, "before");
        DirectStage memory afterStage = _stageFromJson(json, "after");

        // Ensure the imported real C2 evidence is a valid baseline
        // for this oracle before applying any mutations.
        DirectComparisonResult memory baseline = _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(baseline.beforeEvaluation.status), uint256(PolicyStatus.PASS));
        assertEq(uint256(baseline.afterEvaluation.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(baseline.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));

        assertEq(baseline.scenarioKey, vm.parseJsonBytes32(json, ".comparison.scenarioKey"));

        string memory key = "sentinel_c4_direct_differential";

        vm.serializeString(key, "format", "protocol-sentinel-direct-differential-v1");
        vm.serializeBytes32(key, "scenario_key", baseline.scenarioKey);

        string memory output;

        for (uint256 i = 0; i < 8; ++i) {
            (DirectStage memory b, DirectStage memory a) = _mutate(i, beforeStage, afterStage);

            DirectComparisonResult memory comparison = _compareDirectUpgrade(scenarioId, spec, b, a);

            output = _record(key, _caseName(i), comparison);
        }

        vm.writeJson(output, vm.envString("DIRECT_DIFFERENTIAL_OUTPUT"));
    }
}

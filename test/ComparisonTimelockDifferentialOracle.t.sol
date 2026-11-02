// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

/// @notice Differential oracle for frozen oz-timelock-single-v1.
/// @dev Reads existing Evidence 1.0; never authenticates execution provenance.
contract ComparisonTimelockDifferentialOracleTest is TimelockAuthorityProbe {
    uint256 internal constant CASES = 21;

    function _field(string memory prefix, string memory name) internal pure returns (string memory) {
        return string.concat(prefix, ".", name);
    }

    function _specFromJson(string memory json) internal returns (TimelockScenario memory spec) {
        string memory prefix = ".scenario.spec";

        spec.timelock = vm.parseJsonAddress(json, _field(prefix, "timelock"));
        spec.proposer = vm.parseJsonAddress(json, _field(prefix, "proposer"));
        spec.executor = vm.parseJsonAddress(json, _field(prefix, "executor"));
        spec.proxyAdmin = vm.parseJsonAddress(json, _field(prefix, "proxyAdmin"));
        spec.proxy = vm.parseJsonAddress(json, _field(prefix, "proxy"));
        spec.candidate = vm.parseJsonAddress(json, _field(prefix, "candidate"));
        spec.predecessor = vm.parseJsonBytes32(json, _field(prefix, "predecessor"));
        spec.salt = vm.parseJsonBytes32(json, _field(prefix, "salt"));

        bytes32 propertyName = keccak256(bytes(vm.parseJsonString(json, _field(prefix, "property"))));

        if (propertyName == keccak256("READY_UPGRADE_SUCCEEDS")) {
            spec.property = TimelockProperty.READY_UPGRADE_SUCCEEDS;
        } else if (propertyName == keccak256("NOT_READY_EXECUTION_REJECTED")) {
            spec.property = TimelockProperty.NOT_READY_EXECUTION_REJECTED;
        } else {
            revert("Oracle: unsupported property");
        }
    }

    function _operationState(string memory value) internal pure returns (TimelockController.OperationState) {
        bytes32 name = keccak256(bytes(value));

        if (name == keccak256("Unset")) return TimelockController.OperationState.Unset;
        if (name == keccak256("Waiting")) return TimelockController.OperationState.Waiting;
        if (name == keccak256("Ready")) return TimelockController.OperationState.Ready;
        if (name == keccak256("Done")) return TimelockController.OperationState.Done;

        revert("Oracle: invalid operation state");
    }

    function _stageFromJson(string memory json, string memory name) internal returns (RoutedStage memory stage) {
        string memory root = string.concat(".stages.", name);
        string memory p = _field(root, "observation");

        stage.expectedActiveImplementation = vm.parseJsonAddress(json, _field(root, "expectedActiveImplementation"));

        RoutedObservation memory o;

        o.executor = vm.parseJsonAddress(json, _field(p, "executor"));
        o.txOrigin = vm.parseJsonAddress(json, _field(p, "txOrigin"));
        o.executorEOAObserved = vm.parseJsonBool(json, _field(p, "executorEOAObserved"));
        o.executorEOAValid = vm.parseJsonBool(json, _field(p, "executorEOAValid"));
        o.outerTarget = vm.parseJsonAddress(json, _field(p, "outerTarget"));
        o.outerCallData = vm.parseJsonBytes(json, _field(p, "outerCallData"));
        o.outerSuccess = vm.parseJsonBool(json, _field(p, "outerSuccess"));
        o.returnData = vm.parseJsonBytes(json, _field(p, "returnData"));

        o.timelock = vm.parseJsonAddress(json, _field(p, "timelock"));
        o.proxyAdmin = vm.parseJsonAddress(json, _field(p, "proxyAdmin"));
        o.operationId = vm.parseJsonBytes32(json, _field(p, "operationId"));

        o.operationStateBefore = _operationState(vm.parseJsonString(json, _field(p, "operationStateBefore")));

        o.operationStateBeforeObserved = vm.parseJsonBool(json, _field(p, "operationStateBeforeObserved"));

        o.operationDoneBefore = vm.parseJsonBool(json, _field(p, "operationDoneBefore"));
        o.operationDoneAfter = vm.parseJsonBool(json, _field(p, "operationDoneAfter"));
        o.predecessor = vm.parseJsonBytes32(json, _field(p, "predecessor"));

        o.predecessorStateObserved = vm.parseJsonBool(json, _field(p, "predecessorStateObserved"));

        o.predecessorDoneBefore = vm.parseJsonBool(json, _field(p, "predecessorDoneBefore"));

        o.observedTimestamp = vm.parseUint(vm.parseJsonString(json, _field(p, "observedTimestamp")));

        o.readyAt = vm.parseUint(vm.parseJsonString(json, _field(p, "readyAt")));

        o.observedSlot = vm.parseJsonBytes32(json, _field(p, "observedSlot"));

        o.implementationBefore = vm.parseJsonBytes32(json, _field(p, "implementationBefore"));

        o.implementationAfter = vm.parseJsonBytes32(json, _field(p, "implementationAfter"));

        o.proxyCodeObserved = vm.parseJsonBool(json, _field(p, "proxyCodeObserved"));
        o.proxyHasCode = vm.parseJsonBool(json, _field(p, "proxyHasCode"));
        o.candidateCodeObserved = vm.parseJsonBool(json, _field(p, "candidateCodeObserved"));
        o.candidateHasCode = vm.parseJsonBool(json, _field(p, "candidateHasCode"));

        o.proxyAdminOwnershipObserved = vm.parseJsonBool(json, _field(p, "proxyAdminOwnershipObserved"));

        o.proxyAdminOwnedByTimelock = vm.parseJsonBool(json, _field(p, "proxyAdminOwnedByTimelock"));

        o.executorRolesObserved = vm.parseJsonBool(json, _field(p, "executorRolesObserved"));

        o.executorHasRole = vm.parseJsonBool(json, _field(p, "executorHasRole"));
        o.openExecutorRole = vm.parseJsonBool(json, _field(p, "openExecutorRole"));

        stage.observation = o;
    }

    function _withPredecessor(
        TimelockScenario memory spec,
        RoutedStage memory beforeStage,
        RoutedStage memory afterStage
    ) internal pure {
        spec.predecessor = bytes32(uint256(0x1234));

        bytes32 operationId = _timelockOperationId(spec);
        bytes memory calldata_ = _timelockExecutePayload(spec);

        beforeStage.observation.predecessor = spec.predecessor;
        afterStage.observation.predecessor = spec.predecessor;

        beforeStage.observation.operationId = operationId;
        afterStage.observation.operationId = operationId;

        beforeStage.observation.outerCallData = calldata_;
        afterStage.observation.outerCallData = calldata_;

        beforeStage.observation.predecessorStateObserved = true;
        afterStage.observation.predecessorStateObserved = true;

        beforeStage.observation.predecessorDoneBefore = true;
        afterStage.observation.predecessorDoneBefore = true;

        if (spec.property == TimelockProperty.NOT_READY_EXECUTION_REJECTED) {
            bytes memory revertData = abi.encodeWithSelector(
                TimelockController.TimelockUnexpectedOperationState.selector, operationId, bytes32(uint256(4))
            );

            beforeStage.observation.returnData = revertData;
            afterStage.observation.returnData = revertData;
        }
    }

    function _mutate(
        uint256 index,
        TimelockScenario memory spec,
        RoutedStage memory beforeStage,
        RoutedStage memory afterStage
    ) internal pure {
        RoutedObservation memory b = beforeStage.observation;
        RoutedObservation memory a = afterStage.observation;

        if (index == 0) {
            return;
        } else if (index == 1) {
            // Context mismatch takes precedence over missing evidence.
            b.outerTarget = address(0xBEEF);
            b.executorRolesObserved = false;
        } else if (index == 2) {
            // Missing evidence takes precedence over invalid EOA.
            b.executorRolesObserved = false;
            b.executorEOAValid = false;
        } else if (index == 3) {
            // Inconsistent timing takes precedence over eligibility.
            b.readyAt = spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS
                ? b.observedTimestamp + 10
                : b.observedTimestamp;

            b.executorHasRole = false;
            b.openExecutorRole = false;
        } else if (index == 4) {
            b.operationDoneBefore = true;
        } else if (index == 5) {
            a.openExecutorRole = !a.openExecutorRole;
        } else if (index == 6) {
            a.readyAt += 10;

            if (spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS) {
                a.observedTimestamp = a.readyAt;
            }
        } else if (index == 7) {
            // PREPARATION_MISMATCH precedes INDETERMINATE.
            b.executorRolesObserved = false;
            a.readyAt += 10;

            if (spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS) {
                a.observedTimestamp = a.readyAt;
            }
        } else if (index == 8) {
            b.returnData = hex"deadbeef";
        } else if (index == 9) {
            b.implementationBefore |= bytes32(uint256(1) << 200);
            a.implementationBefore |= bytes32(uint256(1) << 201);
        } else if (index == 10) {
            afterStage.expectedActiveImplementation = address(0xBEEF);
        } else if (index == 11) {
            // Valid timing for the WRONG operation state.
            if (spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS) {
                b.operationStateBefore = TimelockController.OperationState.Waiting;
                b.readyAt = b.observedTimestamp + 100;
            } else {
                b.operationStateBefore = TimelockController.OperationState.Ready;
                b.readyAt = b.observedTimestamp;
            }

            b.executorHasRole = false;
            b.openExecutorRole = false;
        } else if (index == 12) {
            b.executorEOAValid = false;
        } else if (index == 13) {
            b.executorHasRole = false;
            b.openExecutorRole = false;
        } else if (index == 14) {
            b.proxyAdminOwnedByTimelock = false;
        } else if (index == 15) {
            _withPredecessor(spec, beforeStage, afterStage);
            b.predecessorDoneBefore = false;
        } else if (index == 16) {
            b.implementationBefore = bytes32(uint256(uint160(spec.candidate)));
        } else if (index == 17) {
            b.candidateHasCode = false;
        } else if (index == 18) {
            b.proxyHasCode = false;
        } else if (index == 19) {
            _withPredecessor(spec, beforeStage, afterStage);
        } else if (index == 20) {
            afterStage.expectedActiveImplementation = beforeStage.expectedActiveImplementation;
            a.implementationBefore = b.implementationBefore;
            a.implementationAfter = b.implementationAfter;
        } else {
            revert("Oracle: unknown mutation");
        }
    }

    function _caseName(uint256 index) internal pure returns (string memory) {
        if (index == 0) return "baseline";
        if (index == 1) return "context_precedence";
        if (index == 2) return "missing_evidence";
        if (index == 3) return "timing_precedence";
        if (index == 4) return "inconsistent_done";
        if (index == 5) return "role_drift";
        if (index == 6) return "reschedule";
        if (index == 7) return "unknown_vs_preparation";
        if (index == 8) return "wrong_return_data";
        if (index == 9) return "upper_bits";
        if (index == 10) return "stage_binding";
        if (index == 11) return "wrong_state";
        if (index == 12) return "invalid_eoa";
        if (index == 13) return "ineligible_executor";
        if (index == 14) return "invalid_admin";
        if (index == 15) return "predecessor_unfinished";
        if (index == 16) return "no_implementation_change";
        if (index == 17) return "invalid_candidate";
        if (index == 18) return "invalid_proxy";
        if (index == 19) return "predecessor_completed";
        if (index == 20) return "same_impl";

        revert("Oracle: unknown case");
    }

    function _expectsPreparationError(uint256 index, TimelockProperty property) internal pure returns (bool) {
        return ((index >= 11 && index <= 15) || (index == 16 && property == TimelockProperty.READY_UPGRADE_SUCCEEDS)
                || index == 17 || index == 18);
    }

    /// @dev External call permits try/catch of frozen internal comparator errors.
    function oracleCompare(
        bytes32 scenarioId,
        TimelockScenario memory spec,
        RoutedStage memory beforeStage,
        RoutedStage memory afterStage
    ) external pure returns (RoutedComparisonResult memory) {
        return _compareTimelockRoute(scenarioId, spec, beforeStage, afterStage);
    }

    function _recordComparison(string memory key, string memory prefix, RoutedComparisonResult memory result)
        internal
        returns (string memory)
    {
        vm.serializeString(key, string.concat(prefix, "_kind"), "COMPARED");

        vm.serializeUint(key, string.concat(prefix, "_before_status"), uint256(result.beforeEvaluation.status));

        vm.serializeUint(key, string.concat(prefix, "_before_reason"), uint256(result.beforeEvaluation.reason));

        vm.serializeUint(key, string.concat(prefix, "_after_status"), uint256(result.afterEvaluation.status));

        vm.serializeUint(key, string.concat(prefix, "_after_reason"), uint256(result.afterEvaluation.reason));

        vm.serializeUint(key, string.concat(prefix, "_verdict"), uint256(result.verdict));

        return vm.serializeUint(key, string.concat(prefix, "_comparison_reason"), uint256(result.reason));
    }

    function _recordPreparation(string memory key, string memory prefix, bytes memory revertData)
        internal
        returns (string memory)
    {
        require(revertData.length == 36, "Oracle: unexpected revert size");

        bytes4 errorSelector;
        uint256 failure;

        assembly {
            errorSelector := mload(add(revertData, 0x20))
            failure := mload(add(revertData, 0x24))
        }

        require(errorSelector == InvalidTimelockPreparation.selector, "Oracle: unexpected error selector");

        require(failure <= uint256(PreparationFailure.INVALID_EOA_EXECUTOR), "Oracle: invalid failure enum");

        vm.serializeString(key, string.concat(prefix, "_kind"), "INVALID_PREPARATION");

        return vm.serializeUint(key, string.concat(prefix, "_failure"), failure);
    }

    function _executeCase(
        string memory key,
        string memory label,
        bytes32 scenarioId,
        TimelockScenario memory baselineSpec,
        RoutedStage memory baselineBefore,
        RoutedStage memory baselineAfter,
        uint256 index
    ) internal returns (string memory) {
        // Avoid sharing mutated memory between cases.
        TimelockScenario memory spec = abi.decode(abi.encode(baselineSpec), (TimelockScenario));

        RoutedStage memory beforeStage = abi.decode(abi.encode(baselineBefore), (RoutedStage));

        RoutedStage memory afterStage = abi.decode(abi.encode(baselineAfter), (RoutedStage));

        _mutate(index, spec, beforeStage, afterStage);

        string memory prefix = string.concat(label, "_", _caseName(index));

        bool expectError = _expectsPreparationError(index, spec.property);

        try this.oracleCompare(scenarioId, spec, beforeStage, afterStage) returns (
            RoutedComparisonResult memory result
        ) {
            require(!expectError, "Oracle: expected preparation error");
            return _recordComparison(key, prefix, result);
        } catch (bytes memory reason) {
            require(expectError, "Oracle: unexpected comparison revert");
            return _recordPreparation(key, prefix, reason);
        }
    }

    function _produce(string memory json, string memory label, string memory key)
        internal
        returns (string memory output)
    {
        TimelockScenario memory spec = _specFromJson(json);

        bool ready = spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS;

        require(ready == (keccak256(bytes(label)) == keccak256("ready")), "Oracle: fixture/property mismatch");

        bytes32 scenarioId = vm.parseJsonBytes32(json, ".scenario.scenarioId");

        RoutedStage memory beforeStage = _stageFromJson(json, "before");
        RoutedStage memory afterStage = _stageFromJson(json, "after");

        RoutedComparisonResult memory baseline = _compareTimelockRoute(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(baseline.beforeEvaluation.status), uint256(PolicyStatus.PASS));
        assertEq(uint256(baseline.afterEvaluation.status), uint256(PolicyStatus.PASS));
        assertEq(uint256(baseline.verdict), uint256(ComparisonVerdict.STILL_SATISFIED));

        assertEq(baseline.scenarioKey, vm.parseJsonBytes32(json, ".comparison.scenarioKey"));

        vm.serializeBytes32(key, string.concat(label, "_scenario_key"), baseline.scenarioKey);

        for (uint256 i = 0; i < CASES; ++i) {
            output = _executeCase(key, label, scenarioId, spec, beforeStage, afterStage, i);
        }
    }

    function test_TimelockDifferentialOracle() public {
        string memory readyPath = vm.envOr("ROUTED_DIFFERENTIAL_READY_EVIDENCE", string(""));

        string memory waitingPath = vm.envOr("ROUTED_DIFFERENTIAL_WAITING_EVIDENCE", string(""));

        if (bytes(readyPath).length == 0 && bytes(waitingPath).length == 0) {
            vm.skip(true);
            return;
        }

        require(
            bytes(readyPath).length != 0 && bytes(waitingPath).length != 0, "Oracle: both evidence paths are required"
        );

        string memory key = "sentinel_c4_routed_differential";

        vm.serializeString(key, "format", "protocol-sentinel-routed-differential-v1");

        _produce(vm.readFile(readyPath), "ready", key);

        string memory output = _produce(vm.readFile(waitingPath), "waiting", key);

        vm.writeJson(output, vm.envString("ROUTED_DIFFERENTIAL_OUTPUT"));
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "../src/ComparativeAuthorityProbe.sol";

import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {RoleVaultV1, RoleVaultV2Risky, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract DirectComparisonEvidenceCaptureTest is ComparativeAuthorityProbe {
    address internal governor;
    address internal operator;

    ERC1967Proxy internal proxy;
    RoleVaultV1 internal vault;

    function setUp() public {
        governor = makeAddr("c2-governor");
        operator = makeAddr("c2-operator");

        RoleVaultV1 original = new RoleVaultV1();

        bytes memory initialization = abi.encodeCall(RoleVaultV1.initialize, (governor, operator));

        proxy = new ERC1967Proxy(address(original), initialization);
        vault = RoleVaultV1(address(proxy));
    }

    function _activeImplementation() internal view returns (address) {
        return address(uint160(uint256(vm.load(address(proxy), ERC1967_IMPL_SLOT))));
    }

    function _observe(UpgradeCheck memory spec) internal returns (DirectStage memory stage) {
        address active = _activeImplementation();

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", spec.candidate, bytes(""));

        Observation memory obs = _observeIsolatedCall(spec.actor, spec.target, payload, ERC1967_IMPL_SLOT);

        stage = DirectStage({expectedActiveImplementation: active, observation: obs});

        assertEq(_activeImplementation(), active, "probe must restore implementation");
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

    function test_CaptureRealDirectComparison() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(proxy),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        bytes32 scenarioId = keccak256("sentinel-c2-real-direct-comparison");

        DirectStage memory beforeStage = _observe(spec);

        assertFalse(beforeStage.observation.success);

        // Install the intentionally vulnerable implementation
        // through the real, authorized governance route.
        vm.prank(governor, governor);
        vault.upgradeToAndCall(address(risky), bytes(""));

        DirectStage memory afterStage = _observe(spec);

        assertTrue(afterStage.observation.success);

        DirectComparisonResult memory result = _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));
        assertEq(uint256(result.reason), uint256(ComparisonReason.NONE));

        // No file is written during normal forge test.
        if (!vm.envOr("EXPORT_DIRECT_CAPTURE", false)) return;

        string memory key = "sentinel_c2_direct_raw";

        vm.serializeString(key, "format", "protocol-sentinel-direct-capture-v1");
        vm.serializeString(key, "chain_id", vm.toString(block.chainid));

        vm.serializeBytes32(key, "scenario_id", scenarioId);
        vm.serializeAddress(key, "actor", spec.actor);
        vm.serializeAddress(key, "target", spec.target);
        vm.serializeAddress(key, "candidate", spec.candidate);
        vm.serializeBytes(key, "expected_revert", spec.expectedRevert);
        vm.serializeString(key, "policy", "NO_IMPLEMENTATION_REPLACEMENT");

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

        vm.writeJson(
            raw, vm.envOr("DIRECT_COMPARISON_CAPTURE_PATH", string("./artifacts/demo/direct-comparison-capture.json"))
        );

        // Test-only fault injection: prove that writing a file
        // cannot publish evidence when the producing test fails.
        if (vm.envOr("DIRECT_COMPARISON_FAIL_AFTER_WRITE", false)) {
            revert("Sentinel: deliberate post-write failure");
        }
    }
}

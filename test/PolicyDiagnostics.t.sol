// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";

contract PolicyDiagnosticsTest is AuthorityProbe {
    address internal constant ACTOR = address(0xA11CE);
    address internal constant TARGET = address(0xBEEF);
    address internal constant CANDIDATE = address(0xC0FFEE);

    bytes4 internal constant EXPECTED_ERROR = 0xdeadbeef;

    function _baseline() internal pure returns (Observation memory obs) {
        obs.actor = ACTOR;
        obs.txOrigin = ACTOR;
        obs.target = TARGET;
        obs.success = false;
        obs.returnData = abi.encodePacked(EXPECTED_ERROR);
        obs.observedSlot = ERC1967_IMPL_SLOT;

        bytes32 initial = bytes32(uint256(uint160(address(0x1001))));

        obs.implementationBefore = initial;
        obs.implementationAfter = initial;

        obs.callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", CANDIDATE, bytes(""));

        obs.candidateValidAtObservation = true;
    }

    function _verify(
        Observation memory obs,
        UpgradePolicy policy,
        PolicyStatus expectedStatus,
        PolicyReason expectedReason
    ) internal {
        bytes32 expectedImplementation = bytes32(uint256(uint160(CANDIDATE)));

        bytes memory expectedRevert = abi.encodePacked(EXPECTED_ERROR);

        PolicyEvaluation memory result =
            _evaluateUpgradePolicyDetailed(obs, policy, expectedImplementation, expectedRevert, ACTOR, TARGET);

        assertEq(uint256(result.status), uint256(expectedStatus), "Diagnostic status mismatch");

        assertEq(uint256(result.reason), uint256(expectedReason), "Diagnostic reason mismatch");

        PolicyStatus legacy = _evaluateUpgradePolicy(obs, policy, expectedImplementation, expectedRevert, ACTOR, TARGET);

        assertEq(uint256(legacy), uint256(expectedStatus), "Backward compatibility broken");
    }

    function test_ExpectedRejectionPass() public {
        _verify(_baseline(), UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.PASS, PolicyReason.NONE);
    }

    function test_EmptyExpectedRevertCannotPass() public {
        Observation memory obs = _baseline();
        obs.returnData = bytes("");

        bytes32 candidateWord = bytes32(uint256(uint160(CANDIDATE)));

        PolicyEvaluation memory evaluation = _evaluateUpgradePolicyDetailed(
            obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, candidateWord, bytes(""), ACTOR, TARGET
        );

        assertEq(uint256(evaluation.status), uint256(PolicyStatus.UNKNOWN));
        assertEq(uint256(evaluation.reason), uint256(PolicyReason.UNEXPECTED_REVERT));

        PolicyStatus legacy = _evaluateUpgradePolicy(
            obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, candidateWord, bytes(""), ACTOR, TARGET
        );

        assertEq(uint256(legacy), uint256(PolicyStatus.UNKNOWN));
    }

    function test_InvalidSlot() public {
        Observation memory obs = _baseline();
        obs.observedSlot = bytes32(0);

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.INVALID_SLOT);
    }

    function test_ContextMismatch() public {
        Observation memory obs = _baseline();

        obs.actor = address(0x1234);

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.CONTEXT_MISMATCH);

        obs = _baseline();
        obs.txOrigin = address(0x1234);

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.CONTEXT_MISMATCH);

        obs = _baseline();
        obs.target = address(0x1234);

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.CONTEXT_MISMATCH);
    }

    function test_NonCanonicalCalldata() public {
        Observation memory obs = _baseline();
        obs.callData = hex"12345678";

        _verify(
            obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.NON_CANONICAL_CALLDATA
        );
    }

    function test_InvalidCandidate() public {
        Observation memory obs = _baseline();
        obs.candidateValidAtObservation = false;

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.INVALID_CANDIDATE);
    }

    function test_UnexpectedRevert() public {
        Observation memory obs = _baseline();
        obs.returnData = hex"abcdef12";

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.UNEXPECTED_REVERT);

        obs = _baseline();
        obs.implementationAfter = bytes32(uint256(uint160(CANDIDATE)));

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.UNEXPECTED_REVERT);
    }

    function test_SuccessWithoutReplacement() public {
        Observation memory obs = _baseline();
        obs.success = true;
        obs.returnData = hex"";

        _verify(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            PolicyStatus.UNKNOWN,
            PolicyReason.SUCCESS_WITHOUT_REPLACEMENT
        );
    }

    function test_SuccessfulReplacementFails() public {
        Observation memory obs = _baseline();
        obs.success = true;
        obs.returnData = hex"";
        obs.implementationAfter = bytes32(uint256(uint160(CANDIDATE)));

        // Successful replacement is FAIL even if candidate
        // validation was unsuccessful.
        obs.candidateValidAtObservation = false;

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.FAIL, PolicyReason.NONE);

        _verify(obs, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, PolicyStatus.FAIL, PolicyReason.NONE);
    }

    function test_SuccessfulCallWithoutReplacementFailsForStrictPolicy() public {
        Observation memory obs = _baseline();
        obs.success = true;
        obs.returnData = hex"";

        _verify(obs, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, PolicyStatus.FAIL, PolicyReason.NONE);
    }

    function test_InvalidSlotTakesPrecedence() public {
        Observation memory obs = _baseline();

        obs.observedSlot = bytes32(0);
        obs.actor = address(0x1234);
        obs.callData = hex"";

        _verify(obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.UNKNOWN, PolicyReason.INVALID_SLOT);
    }

    function _exportReason(string memory label, Observation memory obs, PolicyReason expectedReason) internal {
        bytes32 candidateWord = bytes32(uint256(uint160(CANDIDATE)));

        bytes memory expectedRevert = abi.encodePacked(EXPECTED_ERROR);

        PolicyEvaluation memory evaluation = _evaluateUpgradePolicyDetailed(
            obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, candidateWord, expectedRevert, ACTOR, TARGET
        );

        assertEq(uint256(evaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(evaluation.reason), uint256(expectedReason));

        if (!vm.envOr("EXPORT_POLICY_REASON_MATRIX", false)) {
            return;
        }

        string memory key = string.concat("reason_", label);

        vm.serializeString(key, "schema_version", "0.3");
        vm.serializeString(key, "policy_rule", "NO_IMPLEMENTATION_REPLACEMENT");

        vm.serializeAddress(key, "actor", obs.actor);
        vm.serializeAddress(key, "tx_origin", obs.txOrigin);
        vm.serializeAddress(key, "target", obs.target);
        vm.serializeAddress(key, "expected_actor", ACTOR);
        vm.serializeAddress(key, "expected_target", TARGET);

        vm.serializeBytes32(key, "observed_slot", obs.observedSlot);
        vm.serializeBytes32(key, "implementation_before", obs.implementationBefore);
        vm.serializeBytes32(key, "implementation_after", obs.implementationAfter);
        vm.serializeBytes32(key, "expected_implementation", candidateWord);

        vm.serializeBool(key, "call_success", obs.success);
        vm.serializeBool(key, "candidate_valid_at_observation", obs.candidateValidAtObservation);

        vm.serializeBytes(key, "calldata", obs.callData);
        vm.serializeBytes(key, "return_data", obs.returnData);
        vm.serializeBytes(key, "expected_revert", expectedRevert);
        vm.serializeString(key, "result", "UNKNOWN");

        string memory reasonName;

        if (expectedReason == PolicyReason.INVALID_SLOT) {
            reasonName = "INVALID_SLOT";
        } else if (expectedReason == PolicyReason.CONTEXT_MISMATCH) {
            reasonName = "CONTEXT_MISMATCH";
        } else if (expectedReason == PolicyReason.NON_CANONICAL_CALLDATA) {
            reasonName = "NON_CANONICAL_CALLDATA";
        } else if (expectedReason == PolicyReason.INVALID_CANDIDATE) {
            reasonName = "INVALID_CANDIDATE";
        } else if (expectedReason == PolicyReason.UNEXPECTED_REVERT) {
            reasonName = "UNEXPECTED_REVERT";
        } else if (expectedReason == PolicyReason.SUCCESS_WITHOUT_REPLACEMENT) {
            reasonName = "SUCCESS_WITHOUT_REPLACEMENT";
        } else {
            revert("Unexpected diagnostic reason");
        }

        string memory json = vm.serializeString(key, "reason", reasonName);

        vm.writeJson(json, string.concat("./artifacts/demo/policy-reason-", label, ".json"));
    }

    function test_ExportDiagnosticReasonMatrix() public {
        Observation memory obs = _baseline();

        obs.observedSlot = bytes32(0);
        _exportReason("invalid-slot", obs, PolicyReason.INVALID_SLOT);

        obs = _baseline();
        obs.txOrigin = address(0x1234);
        _exportReason("context-mismatch", obs, PolicyReason.CONTEXT_MISMATCH);

        obs = _baseline();
        obs.callData = hex"12345678";
        _exportReason("noncanonical-calldata", obs, PolicyReason.NON_CANONICAL_CALLDATA);

        obs = _baseline();
        obs.candidateValidAtObservation = false;
        _exportReason("invalid-candidate", obs, PolicyReason.INVALID_CANDIDATE);

        obs = _baseline();
        obs.returnData = hex"abcdef12";
        _exportReason("unexpected-revert", obs, PolicyReason.UNEXPECTED_REVERT);

        obs = _baseline();
        obs.success = true;
        obs.returnData = bytes("");
        _exportReason("success-no-replacement", obs, PolicyReason.SUCCESS_WITHOUT_REPLACEMENT);
    }
}

// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {RoleAuthorityRegressionTest} from "./RoleAuthorityRegression.t.sol";
import {RoleVaultV2Risky, RoleVaultV2Fixed, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract PolicyReplayMatrixTest is RoleAuthorityRegressionTest {
    function _statusName(PolicyStatus status) internal pure returns (string memory) {
        if (status == PolicyStatus.PASS) return "PASS";
        if (status == PolicyStatus.FAIL) return "FAIL";
        if (status == PolicyStatus.UNKNOWN) return "UNKNOWN";
        return "ERROR";
    }

    function _reasonName(PolicyReason reason) internal pure returns (string memory) {
        if (reason == PolicyReason.NONE) return "NONE";
        if (reason == PolicyReason.INVALID_SLOT) return "INVALID_SLOT";
        if (reason == PolicyReason.CONTEXT_MISMATCH) return "CONTEXT_MISMATCH";
        if (reason == PolicyReason.NON_CANONICAL_CALLDATA) return "NON_CANONICAL_CALLDATA";
        if (reason == PolicyReason.INVALID_CANDIDATE) return "INVALID_CANDIDATE";
        if (reason == PolicyReason.UNEXPECTED_REVERT) return "UNEXPECTED_REVERT";
        if (reason == PolicyReason.SUCCESS_WITHOUT_REPLACEMENT) {
            return "SUCCESS_WITHOUT_REPLACEMENT";
        }

        revert("Sentinel: unknown policy reason");
    }

    function _record(
        string memory label,
        Observation memory obs,
        address candidate,
        UpgradePolicy policy,
        PolicyStatus expected
    ) internal {
        bytes32 expectedImplementation = _word(candidate);

        bytes memory expectedRevert = abi.encodeWithSignature(
            "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
        );

        PolicyEvaluation memory evaluation = _evaluateUpgradePolicyDetailed(
            obs, policy, expectedImplementation, expectedRevert, operator, address(roleProxy)
        );

        PolicyStatus actual = evaluation.status;

        assertEq(uint256(actual), uint256(expected), label);

        string memory key = string.concat("matrix_", label);

        vm.serializeString(key, "schema_version", "0.3");
        vm.serializeString(key, "fixture_id", "role_uups_replay");
        vm.serializeString(
            key,
            "policy_rule",
            policy == UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
                ? "NO_IMPLEMENTATION_REPLACEMENT"
                : "NO_SUCCESSFUL_UPGRADE_CALL"
        );

        vm.serializeAddress(key, "actor", obs.actor);
        vm.serializeAddress(key, "tx_origin", obs.txOrigin);
        vm.serializeAddress(key, "target", obs.target);

        vm.serializeAddress(key, "expected_actor", operator);
        vm.serializeAddress(key, "expected_target", address(roleProxy));

        vm.serializeBytes32(key, "observed_slot", obs.observedSlot);
        vm.serializeBytes32(key, "implementation_before", obs.implementationBefore);
        vm.serializeBytes32(key, "implementation_after", obs.implementationAfter);
        vm.serializeBytes32(key, "expected_implementation", expectedImplementation);

        vm.serializeBool(key, "call_success", obs.success);
        vm.serializeBool(key, "candidate_valid_at_observation", obs.candidateValidAtObservation);

        vm.serializeBytes(key, "calldata", obs.callData);
        vm.serializeBytes(key, "return_data", obs.returnData);
        vm.serializeBytes(key, "expected_revert", expectedRevert);

        vm.serializeString(key, "reason", _reasonName(evaluation.reason));
        string memory json = vm.serializeString(key, "result", _statusName(actual));

        if (vm.envOr("EXPORT_POLICY_MATRIX", false)) {
            vm.writeJson(json, string.concat("./artifacts/demo/policy-replay-", label, ".json"));
        }
    }

    function test_ExportPolicyReplayMatrix() public {
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        // 1. Baseline: operator is denied.
        Observation memory baseline = _probe(address(candidate));

        _record(
            "baseline", baseline, address(candidate), UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.PASS
        );

        // 2. Risky: operator replaces implementation.
        RoleVaultV2Risky risky = new RoleVaultV2Risky();
        _install(address(risky));

        Observation memory riskyObs = _probe(address(candidate));

        _record("risky", riskyObs, address(candidate), UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.FAIL);

        // 3 and 4. Same implementation, two different policies.
        Observation memory selfObs = _probe(address(risky));

        _record(
            "self-replacement",
            selfObs,
            address(risky),
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            PolicyStatus.UNKNOWN
        );

        _record("self-call", selfObs, address(risky), UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, PolicyStatus.FAIL);

        // 5. Fixed: operator is denied again.
        RoleVaultV2Fixed fixedVersion = new RoleVaultV2Fixed();
        _install(address(fixedVersion));

        Observation memory fixedObs = _probe(address(candidate));

        _record("fixed", fixedObs, address(candidate), UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, PolicyStatus.PASS);
    }
}

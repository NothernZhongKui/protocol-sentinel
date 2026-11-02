// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "./AuthorityProbe.sol";

/// @notice Pure comparison of declared direct EOA upgrade scenarios.
/// @dev Observations are supplied by the caller; provenance is not authenticated.
abstract contract ComparativeAuthorityProbe is AuthorityProbe {
    bytes32 internal constant DIRECT_COMPARISON_DOMAIN = keccak256("protocol-sentinel/direct-eoa/comparison/v1");

    enum ComparisonVerdict {
        STILL_SATISFIED,
        CHANGED_TO_VIOLATION,
        CHANGED_TO_SATISFIED,
        STILL_VIOLATED,
        INDETERMINATE,
        INCOMPARABLE
    }

    enum ComparisonReason {
        NONE,
        SCENARIO_MISMATCH,
        STAGE_BINDING_MISMATCH,
        SAME_IMPLEMENTATION_STAGE,
        INDETERMINATE_POLICY
    }

    struct DirectStage {
        address expectedActiveImplementation;
        Observation observation;
    }

    struct DirectComparisonResult {
        bytes32 scenarioKey;
        PolicyEvaluation beforeEvaluation;
        PolicyEvaluation afterEvaluation;
        ComparisonVerdict verdict;
        ComparisonReason reason;
    }

    error InvalidComparisonPolicyStatus();

    function _compareDirectUpgrade(
        bytes32 scenarioId,
        UpgradeCheck memory spec,
        DirectStage memory beforeStage,
        DirectStage memory afterStage
    ) internal pure returns (DirectComparisonResult memory result) {
        result.scenarioKey = _directScenarioKey(scenarioId, spec);

        bytes32 expectedCandidate = bytes32(uint256(uint160(spec.candidate)));

        // Always evaluate both stages, even when they are incomparable.
        result.beforeEvaluation = _evaluateUpgradePolicyDetailed(
            beforeStage.observation, spec.policy, expectedCandidate, spec.expectedRevert, spec.actor, spec.target
        );

        result.afterEvaluation = _evaluateUpgradePolicyDetailed(
            afterStage.observation, spec.policy, expectedCandidate, spec.expectedRevert, spec.actor, spec.target
        );

        PolicyStatus beforeStatus = result.beforeEvaluation.status;
        PolicyStatus afterStatus = result.afterEvaluation.status;

        // Infrastructure errors belong to the caller/runner.
        // A future evaluator returning ERROR must not be compared.
        if (beforeStatus == PolicyStatus.ERROR || afterStatus == PolicyStatus.ERROR) {
            revert InvalidComparisonPolicyStatus();
        }

        if (
            !_matchesDirectScenario(beforeStage.observation, spec)
                || !_matchesDirectScenario(afterStage.observation, spec)
        ) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = ComparisonReason.SCENARIO_MISMATCH;
            return result;
        }

        // ERC-1967 implementation identity uses the lower 160 bits.
        address actualBefore = address(uint160(uint256(beforeStage.observation.implementationBefore)));

        address actualAfter = address(uint160(uint256(afterStage.observation.implementationBefore)));

        if (
            actualBefore != beforeStage.expectedActiveImplementation
                || actualAfter != afterStage.expectedActiveImplementation
        ) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = ComparisonReason.STAGE_BINDING_MISMATCH;
            return result;
        }

        if (beforeStage.expectedActiveImplementation == afterStage.expectedActiveImplementation) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = ComparisonReason.SAME_IMPLEMENTATION_STAGE;
            return result;
        }

        if (beforeStatus == PolicyStatus.UNKNOWN || afterStatus == PolicyStatus.UNKNOWN) {
            result.verdict = ComparisonVerdict.INDETERMINATE;
            result.reason = ComparisonReason.INDETERMINATE_POLICY;
            return result;
        }

        if (beforeStatus == PolicyStatus.PASS) {
            result.verdict = afterStatus == PolicyStatus.PASS
                ? ComparisonVerdict.STILL_SATISFIED
                : ComparisonVerdict.CHANGED_TO_VIOLATION;
        } else {
            result.verdict = afterStatus == PolicyStatus.PASS
                ? ComparisonVerdict.CHANGED_TO_SATISFIED
                : ComparisonVerdict.STILL_VIOLATED;
        }

        result.reason = ComparisonReason.NONE;
    }

    function _matchesDirectScenario(Observation memory obs, UpgradeCheck memory spec) internal pure returns (bool) {
        bytes memory canonicalPayload =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", spec.candidate, bytes(""));

        return obs.actor == spec.actor && obs.txOrigin == spec.actor && obs.target == spec.target
            && obs.observedSlot == ERC1967_IMPL_SLOT && keccak256(obs.callData) == keccak256(canonicalPayload);
    }

    function _directScenarioKey(bytes32 scenarioId, UpgradeCheck memory spec) internal pure returns (bytes32) {
        bytes memory canonicalPayload =
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", spec.candidate, bytes(""));

        return keccak256(
            abi.encode(
                DIRECT_COMPARISON_DOMAIN,
                scenarioId,
                spec.actor,
                spec.target,
                spec.candidate,
                canonicalPayload,
                spec.expectedRevert,
                spec.policy,
                ERC1967_IMPL_SLOT
            )
        );
    }
}

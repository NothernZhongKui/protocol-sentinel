// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "protocol-sentinel/ComparativeAuthorityProbe.sol";

/// @notice External consumer of the v0.4-A comparison API.
/// @dev Synthetic observations test API integration, not EVM provenance.
contract SentinelComparativeConsumerTest is ComparativeAuthorityProbe {
    address internal constant ACTOR = address(0xBEEF);
    address internal constant TARGET = address(0xCAFE);
    address internal constant CANDIDATE = address(0xA11CE);

    address internal constant OLD_IMPL = address(0x1111);
    address internal constant NEW_IMPL = address(0x2222);

    function _rejection() internal pure returns (bytes memory) {
        return abi.encodeWithSignature("Denied(address)", ACTOR);
    }

    function _spec() internal pure returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: ACTOR,
            target: TARGET,
            candidate: CANDIDATE,
            expectedRevert: _rejection(),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _stage(address active, bool succeeds) internal pure returns (DirectStage memory) {
        Observation memory obs = Observation({
            actor: ACTOR,
            txOrigin: ACTOR,
            target: TARGET,
            success: succeeds,
            returnData: succeeds ? bytes("") : _rejection(),
            observedSlot: ERC1967_IMPL_SLOT,
            implementationBefore: _word(active),
            implementationAfter: succeeds ? _word(CANDIDATE) : _word(active),
            callData: abi.encodeWithSignature("upgradeToAndCall(address,bytes)", CANDIDATE, bytes("")),
            candidateValidAtObservation: true,
            targetValidAtObservation: true
        });

        return DirectStage({expectedActiveImplementation: active, observation: obs});
    }

    function test_ConsumerDetectsNewViolation() public pure {
        DirectComparisonResult memory result = _compareDirectUpgrade(
            keccak256("external-consumer-regression"), _spec(), _stage(OLD_IMPL, false), _stage(NEW_IMPL, true)
        );

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));

        assertEq(uint256(result.reason), uint256(ComparisonReason.NONE));
    }

    function test_ConsumerPreservesFailOnIncomparable() public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, true);
        DirectStage memory afterStage = _stage(NEW_IMPL, false);

        beforeStage.expectedActiveImplementation = address(0xDEAD);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("external-consumer-mismatch"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.STAGE_BINDING_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";

contract AuthorityPropertyFuzzTest is AuthorityProbe {
    address internal constant ACTOR = address(0xA11CE);
    address internal constant TARGET = address(0xBEEF);
    address internal constant CANDIDATE = address(0xC0FFEE);

    function _baseline() internal pure returns (Observation memory obs) {
        obs.actor = ACTOR;
        obs.txOrigin = ACTOR;
        obs.target = TARGET;

        obs.success = false;
        obs.returnData = hex"deadbeef";
        obs.observedSlot = ERC1967_IMPL_SLOT;

        obs.implementationBefore = bytes32(uint256(0x1001));
        obs.implementationAfter = obs.implementationBefore;

        obs.callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", CANDIDATE, bytes(""));

        obs.candidateValidAtObservation = true;
        obs.targetValidAtObservation = true;
    }

    function _check(
        Observation memory obs,
        UpgradePolicy policy,
        bytes memory expectedRevert,
        PolicyStatus expectedStatus,
        PolicyReason expectedReason
    ) internal pure {
        bytes32 candidateWord = bytes32(uint256(uint160(CANDIDATE)));

        PolicyEvaluation memory result =
            _evaluateUpgradePolicyDetailed(obs, policy, candidateWord, expectedRevert, ACTOR, TARGET);

        assertEq(uint256(result.status), uint256(expectedStatus), "Status invariant");

        assertEq(uint256(result.reason), uint256(expectedReason), "Reason invariant");

        PolicyStatus legacy = _evaluateUpgradePolicy(obs, policy, candidateWord, expectedRevert, ACTOR, TARGET);

        assertEq(uint256(legacy), uint256(expectedStatus), "Legacy API invariant");
    }

    function testFuzz_HighBitsCannotCreateReplacement(uint96 highBefore, uint96 highAfter) public pure {
        Observation memory obs = _baseline();

        obs.success = true;

        obs.implementationBefore = bytes32((uint256(highBefore) << 160) | 0x1001);

        obs.implementationAfter = bytes32((uint256(highAfter) << 160) | 0x1001);

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.SUCCESS_WITHOUT_REPLACEMENT
        );

        _check(obs, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, hex"deadbeef", PolicyStatus.FAIL, PolicyReason.NONE);
    }

    function testFuzz_ContextMismatchNeverPasses(uint160 seed) public pure {
        Observation memory obs = _baseline();

        obs.actor = address(uint160(ACTOR) ^ (seed | 1));

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.CONTEXT_MISMATCH
        );

        obs = _baseline();
        obs.txOrigin = address(uint160(ACTOR) ^ (seed | 1));

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.CONTEXT_MISMATCH
        );

        obs = _baseline();
        obs.target = address(uint160(TARGET) ^ (seed | 1));

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.CONTEXT_MISMATCH
        );
    }

    function testFuzz_InvalidSlotTakesPrecedence(uint256 mask) public pure {
        Observation memory obs = _baseline();

        obs.observedSlot = ERC1967_IMPL_SLOT ^ bytes32(mask | 1);

        obs.actor = address(0x1234);
        obs.targetValidAtObservation = false;
        obs.callData = hex"";

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.INVALID_SLOT
        );
    }

    function testFuzz_InvalidTargetTakesPrecedence(bool callSucceeded, uint256 arbitraryWord) public pure {
        Observation memory obs = _baseline();

        obs.targetValidAtObservation = false;
        obs.success = callSucceeded;
        obs.callData = abi.encodePacked(arbitraryWord);

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.INVALID_TARGET
        );
    }

    function testFuzz_RejectionRequiresAllEvidence(
        bool validCandidate,
        bool expectedNonempty,
        bool matchingRevert,
        bool implementationChanged
    ) public pure {
        Observation memory obs = _baseline();

        obs.candidateValidAtObservation = validCandidate;

        if (!matchingRevert) {
            obs.returnData = hex"cafebabe";
        }

        if (implementationChanged) {
            obs.implementationAfter = bytes32(uint256(0x2002));
        }

        bytes memory expectedRevert = hex"deadbeef";

        if (!expectedNonempty) {
            expectedRevert = bytes("");
        }

        if (!validCandidate) {
            _check(
                obs,
                UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
                expectedRevert,
                PolicyStatus.UNKNOWN,
                PolicyReason.INVALID_CANDIDATE
            );
        } else if (expectedNonempty && matchingRevert && !implementationChanged) {
            _check(
                obs, UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT, expectedRevert, PolicyStatus.PASS, PolicyReason.NONE
            );
        } else {
            _check(
                obs,
                UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
                expectedRevert,
                PolicyStatus.UNKNOWN,
                PolicyReason.UNEXPECTED_REVERT
            );
        }
    }

    function testFuzz_SuccessfulCallPolicy(bool candidateValid, bool implementationChanged) public pure {
        Observation memory obs = _baseline();

        obs.success = true;
        obs.candidateValidAtObservation = candidateValid;

        if (implementationChanged) {
            obs.implementationAfter = bytes32(uint256(0x2002));
        }

        _check(obs, UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL, hex"deadbeef", PolicyStatus.FAIL, PolicyReason.NONE);

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            implementationChanged ? PolicyStatus.FAIL : PolicyStatus.UNKNOWN,
            implementationChanged ? PolicyReason.NONE : PolicyReason.SUCCESS_WITHOUT_REPLACEMENT
        );
    }

    function testFuzz_NoncanonicalCallCannotPass(uint256 arbitraryWord) public pure {
        Observation memory obs = _baseline();

        obs.callData = abi.encodePacked(arbitraryWord);

        _check(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            hex"deadbeef",
            PolicyStatus.UNKNOWN,
            PolicyReason.NON_CANONICAL_CALLDATA
        );
    }
}

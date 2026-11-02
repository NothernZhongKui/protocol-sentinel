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
}

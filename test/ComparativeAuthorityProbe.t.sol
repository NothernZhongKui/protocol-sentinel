// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "../src/ComparativeAuthorityProbe.sol";

contract ComparativeAuthorityProbeTest is ComparativeAuthorityProbe {
    address internal constant ACTOR = address(0xBEEF);
    address internal constant TARGET = address(0xCAFE);
    address internal constant CANDIDATE = address(0xA11CE);

    address internal constant BEFORE_IMPL = address(0x1111);
    address internal constant AFTER_IMPL = address(0x2222);

    function _implementationWord(address implementation) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(implementation)));
    }

    function _expectedRevert() internal pure returns (bytes memory) {
        return abi.encodeWithSignature("Forbidden(address)", ACTOR);
    }

    function _spec() internal pure returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: ACTOR,
            target: TARGET,
            candidate: CANDIDATE,
            expectedRevert: _expectedRevert(),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function _stage(address implementation, bool upgradeSucceeds) internal pure returns (DirectStage memory) {
        Observation memory obs = Observation({
            actor: ACTOR,
            txOrigin: ACTOR,
            target: TARGET,
            success: upgradeSucceeds,
            returnData: upgradeSucceeds ? bytes("") : _expectedRevert(),
            observedSlot: ERC1967_IMPL_SLOT,
            implementationBefore: _implementationWord(implementation),
            implementationAfter: upgradeSucceeds ? _implementationWord(CANDIDATE) : _implementationWord(implementation),
            callData: abi.encodeWithSignature("upgradeToAndCall(address,bytes)", CANDIDATE, bytes("")),
            candidateValidAtObservation: true,
            targetValidAtObservation: true
        });

        return DirectStage({expectedActiveImplementation: implementation, observation: obs});
    }

    function _compare(bool beforeSucceeds, bool afterSucceeds) internal pure returns (DirectComparisonResult memory) {
        return _compareDirectUpgrade(
            keccak256("authority-transition-test"),
            _spec(),
            _stage(BEFORE_IMPL, beforeSucceeds),
            _stage(AFTER_IMPL, afterSucceeds)
        );
    }

    function _assertResult(
        DirectComparisonResult memory result,
        PolicyStatus expectedBefore,
        PolicyStatus expectedAfter,
        ComparisonVerdict expectedVerdict
    ) internal pure {
        assertEq(uint256(result.beforeEvaluation.status), uint256(expectedBefore));

        assertEq(uint256(result.afterEvaluation.status), uint256(expectedAfter));

        assertEq(uint256(result.verdict), uint256(expectedVerdict));

        assertEq(uint256(result.reason), uint256(ComparisonReason.NONE));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.NONE));

        assertEq(uint256(result.afterEvaluation.reason), uint256(PolicyReason.NONE));
    }

    function test_PassToPass() public pure {
        DirectComparisonResult memory result = _compare(false, false);

        _assertResult(result, PolicyStatus.PASS, PolicyStatus.PASS, ComparisonVerdict.STILL_SATISFIED);
    }

    function test_PassToFail() public pure {
        DirectComparisonResult memory result = _compare(false, true);

        _assertResult(result, PolicyStatus.PASS, PolicyStatus.FAIL, ComparisonVerdict.CHANGED_TO_VIOLATION);
    }

    function test_FailToPass() public pure {
        DirectComparisonResult memory result = _compare(true, false);

        _assertResult(result, PolicyStatus.FAIL, PolicyStatus.PASS, ComparisonVerdict.CHANGED_TO_SATISFIED);
    }

    function test_FailToFail() public pure {
        DirectComparisonResult memory result = _compare(true, true);

        _assertResult(result, PolicyStatus.FAIL, PolicyStatus.FAIL, ComparisonVerdict.STILL_VIOLATED);
    }

    function test_UnknownBefore() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        beforeStage.observation.returnData = hex"deadbeef";

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("unknown-before"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
        assertEq(uint256(result.reason), uint256(ComparisonReason.INDETERMINATE_POLICY));
    }

    function test_UnknownAfter() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, true);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        afterStage.observation.returnData = hex"deadbeef";

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("unknown-after"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));
        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_WrongActorIsIncomparable() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        beforeStage.observation.actor = address(0xBAD);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("wrong-actor"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
        assertEq(uint256(result.reason), uint256(ComparisonReason.SCENARIO_MISMATCH));

        // Evaluations must still contain actual policy results.
        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));
    }

    function test_WrongOriginIsIncomparable() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        afterStage.observation.txOrigin = address(0xBAD);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("wrong-origin"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
        assertEq(uint256(result.reason), uint256(ComparisonReason.SCENARIO_MISMATCH));
    }

    function test_WrongTargetIsIncomparable() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        afterStage.observation.target = address(0xBAD);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("wrong-target"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
    }

    function test_NonCanonicalCalldataIsIncomparable() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        afterStage.observation.callData = abi.encodeWithSignature("upgradeTo(address)", CANDIDATE);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("wrong-calldata"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));
        assertEq(uint256(result.afterEvaluation.reason), uint256(PolicyReason.NON_CANONICAL_CALLDATA));
    }

    function test_InvalidSlotIsIncomparable() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        afterStage.observation.observedSlot = bytes32(uint256(123));

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("wrong-slot"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
        assertEq(uint256(result.afterEvaluation.reason), uint256(PolicyReason.INVALID_SLOT));
    }

    function test_StageMismatchRetainsRealFail() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, true);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        beforeStage.expectedActiveImplementation = CANDIDATE;

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("stage-mismatch"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));
        assertEq(uint256(result.reason), uint256(ComparisonReason.STAGE_BINDING_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.FAIL));
        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function test_UpperBitsIgnoredForAddressBinding() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        beforeStage.observation.implementationBefore =
            beforeStage.observation.implementationBefore | bytes32(uint256(1) << 200);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("upper-bits-binding"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function test_UpperBitsCannotFakeVersionChange() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(BEFORE_IMPL, false);

        afterStage.observation.implementationBefore =
            afterStage.observation.implementationBefore | bytes32(uint256(1) << 200);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("upper-bits-version"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.SAME_IMPLEMENTATION_STAGE));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function test_WrongExpectedRevertIsIndeterminate() public pure {
        UpgradeCheck memory spec = _spec();

        spec.expectedRevert = hex"deadbeef";

        DirectComparisonResult memory result = _compareDirectUpgrade(
            keccak256("wrong-revert"), spec, _stage(BEFORE_IMPL, false), _stage(AFTER_IMPL, true)
        );

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.UNEXPECTED_REVERT));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_ScenarioKeyBindsPolicy() public pure {
        UpgradeCheck memory first = _spec();
        UpgradeCheck memory second = _spec();

        bytes32 scenarioId = keccak256("scenario-identity");

        bytes32 firstKey = _directScenarioKey(scenarioId, first);

        second.policy = UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL;

        bytes32 secondKey = _directScenarioKey(scenarioId, second);

        assertTrue(firstKey != secondKey);

        second = _spec();
        second.actor = address(0xBAD);

        assertTrue(firstKey != _directScenarioKey(scenarioId, second));

        second = _spec();
        second.expectedRevert = hex"deadbeef";

        assertTrue(firstKey != _directScenarioKey(scenarioId, second));

        assertTrue(firstKey != _directScenarioKey(keccak256("another-scenario"), first));
    }

    function test_RevertedCallWithChangedImplementation() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        // Contradictory evidence: the call reverted,
        // but the observed implementation address changed.
        afterStage.observation.implementationAfter = _implementationWord(CANDIDATE);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("revert-with-change"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.afterEvaluation.reason), uint256(PolicyReason.UNEXPECTED_REVERT));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_SuccessWithoutImplementationChange() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        // A successful call is not necessarily
        // a successful implementation replacement.
        afterStage.observation.implementationAfter = _implementationWord(AFTER_IMPL);

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("success-without-change"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.afterEvaluation.reason), uint256(PolicyReason.SUCCESS_WITHOUT_REPLACEMENT));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_InvalidTargetCannotProducePass() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        beforeStage.observation.targetValidAtObservation = false;

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("invalid-target"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.INVALID_TARGET));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_InvalidCandidateCannotProducePass() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, false);

        beforeStage.observation.candidateValidAtObservation = false;

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("invalid-candidate"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.INVALID_CANDIDATE));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function test_IncomparablePreservesUnknownEvaluation() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        // The observed revert differs from the declared one.
        beforeStage.observation.returnData = hex"deadbeef";

        // The declared stage implementation is also incorrect.
        beforeStage.expectedActiveImplementation = CANDIDATE;

        DirectComparisonResult memory result =
            _compareDirectUpgrade(keccak256("mismatch-and-unknown"), _spec(), beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.STAGE_BINDING_MISMATCH));

        // Even with INCOMPARABLE, neither evaluation
        // may be silently replaced by default PASS.
        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.UNEXPECTED_REVERT));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));
    }

    function test_DifferentPoliciesTreatSuccessDifferently() public pure {
        DirectStage memory beforeStage = _stage(BEFORE_IMPL, false);
        DirectStage memory afterStage = _stage(AFTER_IMPL, true);

        // The call succeeds without replacing the implementation.
        afterStage.observation.implementationAfter = _implementationWord(AFTER_IMPL);

        UpgradeCheck memory spec = _spec();

        bytes32 scenarioId = keccak256("policy-semantics");

        DirectComparisonResult memory replacementPolicy =
            _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(replacementPolicy.verdict), uint256(ComparisonVerdict.INDETERMINATE));

        spec.policy = UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL;

        DirectComparisonResult memory callPolicy = _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(callPolicy.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(callPolicy.afterEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(callPolicy.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));

        // A different policy is a different scenario.
        assertTrue(replacementPolicy.scenarioKey != callPolicy.scenarioKey);
    }
}
